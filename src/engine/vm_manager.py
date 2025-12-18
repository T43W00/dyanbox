import libvirt
import time
import logging
from config.settings import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VMManager:
    def __init__(self, vm_name: str = settings.VM_NAME):
        self.vm_name = vm_name
        self.conn = None
        self.dom = None

    def connect(self):
        """Connect to the local QEMU/KVM hypervisor."""
        try:
            self.conn = libvirt.open(settings.VM_URI)
            if self.conn is None:
                raise Exception(f"Failed to open connection to {settings.VM_URI}")
            logger.info("Connected to QEMU/KVM")
        except libvirt.libvirtError as e:
            logger.error(f"Connection error: {e}")
            raise

    def _get_domain(self):
        """Helper to get the domain object."""
        if not self.conn:
            self.connect()
        try:
            self.dom = self.conn.lookupByName(self.vm_name)
            return self.dom
        except libvirt.libvirtError as e:
            logger.error(f"Could not find VM '{self.vm_name}': {e}")
            raise

    def start_vm(self):
        """Start the VM if it's not running."""
        dom = self._get_domain()
        if not dom.isActive():
            dom.create()
            logger.info(f"VM '{self.vm_name}' started.")
            return True
        else:
            logger.info(f"VM '{self.vm_name}' is already running.")
            return False

    def stop_vm(self):
        """Forcefully stop the VM (like pulling the plug)."""
        dom = self._get_domain()
        if dom.isActive():
            dom.destroy()
            logger.info(f"VM '{self.vm_name}' stopped.")
        else:
            logger.info(f"VM '{self.vm_name}' is not running.")

    def revert_to_snapshot(self, snapshot_name: str):
        """Revert VM to a clean state snapshot."""
        dom = self._get_domain()
        try:
            snap = dom.snapshotLookupByName(snapshot_name)
            dom.revertToSnapshot(snap)
            logger.info(f"Reverted '{self.vm_name}' to snapshot '{snapshot_name}'.")
        except libvirt.libvirtError as e:
            logger.error(f"Snapshot revert error: {e}")
            raise

    def close(self):
        """Close the connection."""
        if self.conn:
            self.conn.close()
            logger.info("Connection closed.")

# Example usage
if __name__ == "__main__":
    vm = VMManager()
    # vm.start_vm()
    vm.close()
