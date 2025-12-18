# Dyanbox - Dynamic Malware Analysis Sandbox

Automated dynamic analysis platform for Windows PE files using QEMU/KVM.

## Features

- **Automated Analysis**: Submits Windows PE files for execution in a secure sandbox.
- **QEMU/KVM Integration**: Uses hardware-assisted virtualization for isolation.
- **Agent-based Monitoring**: Captures behavior inside the guest OS.

## Project Structure

- `src/api`: REST API for file submission and control.
- `src/engine`: Core logic for VM management (libvirt) and analysis orchestration.
- `src/agent`: Python agent running inside the Guest OS (Windows).
- `src/utils`: Helper utilities.
- `config`: Configuration files.

## Prerequisites

- Linux Host (with KVM support)
- Python 3.10+
- QEMU/KVM & libvirt
- Windows VM Image (qcow2)

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure VM path in `config/settings.py` (to be created).

3. Run the API:
   ```bash
   uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
   ```
