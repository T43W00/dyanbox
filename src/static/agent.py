import os
import subprocess
import time
import urllib.request
import urllib.parse
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import json
import sys

# Configuration
HOST_API_URL = "http://192.168.122.1:8000"  
AGENT_PORT = 5000
ANALYSIS_TIMEOUT = 60  # seconds

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DyanboxAgent")

def install_dependencies():
    """Check and install required packages from Host API."""
    packages = {
        "psutil": "psutil-6.1.1-cp37-abi3-win_amd64.whl",
        "watchdog": "watchdog-6.0.0-py3-none-win_amd64.whl"
    }
    
    for package_name, whl_file in packages.items():
        try:
            __import__(package_name)
            logger.info(f"{package_name} is already installed.")
        except ImportError:
            logger.info(f"Installing {package_name}...")
            try:
                url = f"{HOST_API_URL}/static/{whl_file}"
                whl_path = os.path.join(os.environ.get('TEMP', '.'), whl_file)
                
                logger.info(f"Downloading {url}...")
                urllib.request.urlretrieve(url, whl_path)
                
                subprocess.check_call([sys.executable, "-m", "pip", "install", whl_path])
                logger.info(f"Successfully installed {package_name}")
            except Exception as e:
                logger.error(f"Failed to install {package_name}: {e}")

# Try to install dependencies on startup
install_dependencies()

try:
    import psutil
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    logger.warning("Monitoring libraries (psutil, watchdog) not found. Advanced monitoring disabled.")
    psutil = None
    Observer = None
    FileSystemEventHandler = object 

class FileMonitor(FileSystemEventHandler):
    def __init__(self):
        self.events = []
        
    def on_created(self, event):
        self.events.append(f"[FILE_CREATED] {event.src_path}")
        
    def on_modified(self, event):
        self.events.append(f"[FILE_MODIFIED] {event.src_path}")
        
    def on_deleted(self, event):
        self.events.append(f"[FILE_DELETED] {event.src_path}")

class AnalysisExecutor:
    def __init__(self):
        self.is_running = False
        self.current_process = None
        self.process_list = []
        self.network_conns = []
        self.file_events = []
        
    def start_monitoring(self):
        # File Monitoring
        if Observer:
            self.file_monitor = FileMonitor()
            self.observer = Observer()
            # Monitor Desktop and Documents
            target_path = os.path.join(os.environ.get('USERPROFILE', 'C:\\'), 'Desktop')
            self.observer.schedule(self.file_monitor, target_path, recursive=False)
            self.observer.start()
            
    def stop_monitoring(self):
        if Observer and hasattr(self, 'observer'):
            self.observer.stop()
            self.observer.join()
            self.file_events = self.file_monitor.events

        # Process & Network Snapshot
        if psutil:
            # Capture all running processes
            for proc in psutil.process_iter(['pid', 'name', 'username', 'cmdline']):
                try:
                    self.process_list.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
                    
            # Capture network connections
            for conn in psutil.net_connections(kind='inet'):
                try:
                    laddr = f"{conn.laddr.ip}:{conn.laddr.port}"
                    raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else ""
                    self.network_conns.append({
                        "fd": conn.fd,
                        "family": conn.family,
                        "type": conn.type,
                        "laddr": laddr,
                        "raddr": raddr,
                        "status": conn.status,
                        "pid": conn.pid
                    })
                except:
                    pass

    def execute_sample(self, file_path):
        """Executes the malware sample."""
        try:
            self.start_monitoring()
            logger.info(f"Executing sample: {file_path}")
            self.current_process = subprocess.Popen([file_path], shell=True)
            self.is_running = True
            
            time.sleep(ANALYSIS_TIMEOUT)
            
            self.terminate_sample()
            self.stop_monitoring()
        except Exception as e:
            logger.error(f"Execution failed: {e}")

    def terminate_sample(self):
        """Terminates the malware sample."""
        if self.current_process:
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.current_process.pid)])
                logger.info("Sample terminated.")
            except Exception as e:
                logger.error(f"Failed to terminate sample: {e}")
        self.is_running = False

    def collect_artifacts(self):
        """Collects logs."""
        return {
            "status": "completed",
            "logs": f"Analysis finished at {time.ctime()}.\nSample executed for {ANALYSIS_TIMEOUT}s.",
            "processes": self.process_list,
            "network": self.network_conns,
            "files": self.file_events
        }

executor = AnalysisExecutor()

class AgentHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/analyze":
            try:
                task_id = self.headers.get('X-Task-ID', 'unknown')
                content_length = int(self.headers.get('Content-Length', 0))
                file_data = self.rfile.read(content_length)
                
                # Save to Desktop
                save_dir = os.path.join(os.environ.get('USERPROFILE', 'C:\\'), 'Desktop')
                if not os.path.exists(save_dir):
                    os.makedirs(save_dir)
                    
                sample_path = os.path.join(save_dir, "malware_sample.exe")
                with open(sample_path, "wb") as f:
                    f.write(file_data)
                
                logger.info(f"Sample saved to {sample_path}")

                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Analysis started")
                
                threading.Thread(target=self._run_analysis, args=(sample_path, task_id)).start()

            except Exception as e:
                logger.error(f"Error: {e}")
                self.send_error(500, str(e))

    def _run_analysis(self, sample_path, task_id):
        executor.execute_sample(sample_path)
        results = executor.collect_artifacts()
        results['task_id'] = task_id
        
        # Send Report via urllib (No requests lib needed)
        try:
            data = json.dumps(results).encode('utf-8')
            req = urllib.request.Request(
                f"{HOST_API_URL}/report", 
                data=data, 
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req) as response:
                logger.info(f"Report sent. Host response: {response.status}")
        except Exception as e:
            logger.error(f"Failed to send report: {e}")

def run_agent():
    server_address = ('0.0.0.0', AGENT_PORT)
    httpd = HTTPServer(server_address, AgentHandler)
    logger.info(f"Dyanbox Agent running on port {AGENT_PORT}...")
    httpd.serve_forever()

if __name__ == "__main__":
    run_agent()
