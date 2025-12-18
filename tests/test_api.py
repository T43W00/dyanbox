from fastapi.testclient import TestClient
from src.api.main import app
import os

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert "Welcome to Dyanbox API" in response.json()["message"]

def test_file_upload(tmp_path):
    # Create a dummy file
    file_content = b"MZ\x90\x00\x03\x00\x00\x00"  # Minimal DOS header signature
    file_path = tmp_path / "test_malware.exe"
    file_path.write_bytes(file_content)
    
    with open(file_path, "rb") as f:
        response = client.post(
            "/submit/",
            files={"file": ("test_malware.exe", f, "application/octet-stream")}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["filename"] == "test_malware.exe"
    assert data["status"] == "uploaded"

    # Cleanup is handled by tmp_path usually, but files in storage might remain
    # In a real test, we might want to mock the storage part too.
