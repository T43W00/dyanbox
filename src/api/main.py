from fastapi import FastAPI, UploadFile, File, HTTPException
from config.settings import settings
import shutil
import os
import uuid
import requests
import datetime
import threading
import time
from typing import Dict, Any
from sqlalchemy.orm import Session
from fastapi import Depends, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
import libvirt

from fastapi.staticfiles import StaticFiles
from src.engine.models import SessionLocal, AnalysisResult, init_db
from src.engine.vm_manager import VMManager
from config.settings import settings

app = FastAPI(title=settings.PROJECT_NAME, version=settings.API_VERSION)

templates = Jinja2Templates(directory="src/templates")

# Mount static files (For serving Python installer and agent to VM)
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# Initialize DB on startup
@app.on_event("startup")
def startup_event():
    init_db()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/submit/")
async def submit_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Submit a file for analysis.
    """
    try:
        # Generate a unique task ID
        task_id = str(uuid.uuid4())
        file_ext = os.path.splitext(file.filename)[1]
        save_path = os.path.join(settings.UPLOAD_DIR, f"{task_id}{file_ext}")
        
        # Save the uploaded file
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Create DB record
        db_record = AnalysisResult(
            task_id=task_id,
            filename=file.filename,
            status="pending",
            progress=0,
            current_step="Waiting for analysis"
        )
        db.add(db_record)
        db.commit()

        return {
            "task_id": task_id,
            "filename": file.filename,
            "status": "uploaded",
            "message": "File submitted successfully. Analysis pending."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analyses")
def list_analyses(db: Session = Depends(get_db)):
    """
    List all recent analyses.
    """
    results = db.query(AnalysisResult).order_by(AnalysisResult.created_at.desc()).limit(20).all()
    return results

@app.post("/analyze/{task_id}")
def start_analysis(task_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Manually trigger analysis for a specific task.
    """
    record = db.query(AnalysisResult).filter(AnalysisResult.task_id == task_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update status to processing immediately
    record.status = "processing"
    record.progress = 5
    record.current_step = "Initializing..."
    db.commit()
    
    # Start analysis in background
    background_tasks.add_task(run_analysis_logic, task_id)
    
    return {"message": "Analysis started", "task_id": task_id}

VM_IP = "192.168.122.100"

def run_analysis_logic(task_id: str):
    """
    Mock analysis logic (Since we don't have a real VM running in this env).
    In production, this would call VMManager.
    """
    # Re-open session since this runs in a thread
    db = SessionLocal()
    vm = None
    
    # Find file path
    record = db.query(AnalysisResult).filter(AnalysisResult.task_id == task_id).first()
    # We need to reconstruct filepath. In submit_file we used:
    file_path = os.path.join(settings.UPLOAD_DIR, f"{task_id}_{record.filename}") # Wait, in submit we used {task_id}{ext}
    # Let's fix file path resolution properly.
    # Since we don't know extension easily, let's search.
    for f in os.listdir(settings.UPLOAD_DIR):
        if f.startswith(task_id):
            file_path = os.path.join(settings.UPLOAD_DIR, f)
            break

    try:
        # Step 1: VM Boot
        _update_progress(db, task_id, 20, "Booting VM...")
        
        try:
            vm = VMManager()
            vm.connect()
            
            # Start VM and check if it was newly started
            was_started = vm.start_vm()
            
            if was_started:
                # Wait for VM to be fully up only if it was started from off state
                time.sleep(90)
            else:
                print("VM already running. Skipping boot wait.")
                
        except Exception as e:
            _update_progress(db, task_id, 0, f"VM Boot Failed: {e}")
            print(f"VM Error: {e}")
            return

        # Step 2: File Transfer
        _update_progress(db, task_id, 40, "Transferring malware sample...")
        
        try:
            with open(file_path, "rb") as f:
                files = {'file': (record.filename, f)}
                # Send Task ID in headers so Agent knows what to report back
                headers = {'X-Task-ID': task_id}
                response = requests.post(f"http://{VM_IP}:5000/analyze", data=f, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    _update_progress(db, task_id, 60, "Analysis in progress (Agent)...")
                    print(f"File sent to agent. Analysis started for {task_id}")
                    # Note: We do NOT close VM here yet. We wait for report.
                    # But keeping VM open indefinitely is risky.
                    # Ideally, we should have a timeout monitor.
                    # For now, we assume Agent will call back /report within 60s.
                else:
                     raise Exception(f"Agent returned {response.status_code}")

        except Exception as e:
             raise Exception(f"Failed to send file to agent: {e}")

        # Step 3: Done (for this thread). The rest is handled by /report
        
    except Exception as e:
        print(f"Analysis failed: {e}")
        _update_progress(db, task_id, 0, f"Error: {e}")
    finally:
        db.close()

def _update_progress(db, task_id, progress, step):
    record = db.query(AnalysisResult).filter(AnalysisResult.task_id == task_id).first()
    if record:
        record.progress = progress
        record.current_step = step
        db.commit()

@app.get("/status/{task_id}")
def get_status(task_id: str, db: Session = Depends(get_db)):
    """
    Check the status of an analysis task.
    """
    result = db.query(AnalysisResult).filter(AnalysisResult.task_id == task_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Parse logs if it's valid JSON, otherwise return as string
    import json
    logs_data = result.logs
    try:
        logs_data = json.loads(result.logs) if result.logs else None
    except json.JSONDecodeError:
        pass

    return {
        "task_id": task_id,
        "status": result.status,
        "filename": result.filename,
        "created_at": result.created_at,
        "completed_at": result.completed_at,
        "progress": result.progress,
        "current_step": result.current_step,
        "logs": logs_data
    }

@app.delete("/analysis/{task_id}")
def delete_analysis(task_id: str, db: Session = Depends(get_db)):
    """
    Delete an analysis record and its associated file.
    """
    record = db.query(AnalysisResult).filter(AnalysisResult.task_id == task_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Delete file from storage
    try:
        file_path = os.path.join(settings.UPLOAD_DIR, f"{task_id}_{record.filename}")
        # Note: We saved it as task_id + ext in submit_file, but let's check exact logic
        # In submit_file: save_path = os.path.join(settings.UPLOAD_DIR, f"{task_id}{file_ext}")
        # So we need to match that pattern. But we don't store ext in DB easily.
        # Let's try to find the file by glob or store path in DB.
        # For now, let's just attempt to delete by task_id prefix.
        for f in os.listdir(settings.UPLOAD_DIR):
            if f.startswith(task_id):
                os.remove(os.path.join(settings.UPLOAD_DIR, f))
    except Exception as e:
        print(f"Error deleting file: {e}")

    db.delete(record)
    db.commit()
    return {"message": "Analysis deleted successfully"}

@app.post("/report")
async def receive_report(report: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Receive analysis report from the Guest Agent.
    """
    print(f"Received report: {report}")
    
    task_id = report.get("task_id")
    if task_id:
        record = db.query(AnalysisResult).filter(AnalysisResult.task_id == task_id).first()
        if record:
            record.status = "completed"
            record.progress = 100
            record.current_step = "Analysis Completed"
            record.completed_at = datetime.datetime.utcnow()
            
            # Store full JSON report as string
            import json
            record.logs = json.dumps(report, indent=2)
            db.commit()
            
            # Shutdown VM after report received
            # Note: This is a bit quick-and-dirty. Ideally we use a VM pool manager.
            try:
                vm = VMManager()
                vm.stop_vm()
                # vm.revert_to_snapshot("clean_state") # Recommended for next run
                vm.close()
            except Exception as e:
                print(f"Error stopping VM: {e}")

    return {"status": "received"}
