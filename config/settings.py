import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Dyanbox"
    API_VERSION: str = "v1"
    
    # Storage settings
    UPLOAD_DIR: str = os.path.join(os.getcwd(), "storage", "uploads")
    ARTIFACTS_DIR: str = os.path.join(os.getcwd(), "storage", "artifacts")
    
    # VM Settings (Default values)
    VM_NAME: str = "dyanbox-win10"
    VM_URI: str = "qemu:///system"  # Connect to local system QEMU instance
    
    class Config:
        env_file = ".env"

settings = Settings()

# Ensure directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.ARTIFACTS_DIR, exist_ok=True)
