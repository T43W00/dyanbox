import pytest
from unittest.mock import MagicMock, patch
from src.engine.vm_manager import VMManager
import libvirt

@patch("libvirt.open")
def test_vm_connection(mock_libvirt_open):
    # Setup mock
    mock_conn = MagicMock()
    mock_libvirt_open.return_value = mock_conn
    
    vm = VMManager()
    vm.connect()
    
    mock_libvirt_open.assert_called_once()
    assert vm.conn == mock_conn

@patch("libvirt.open")
def test_start_vm(mock_libvirt_open):
    # Setup mock connection and domain
    mock_conn = MagicMock()
    mock_dom = MagicMock()
    mock_libvirt_open.return_value = mock_conn
    mock_conn.lookupByName.return_value = mock_dom
    
    # Case 1: VM is inactive, should start
    mock_dom.isActive.return_value = 0 
    
    vm = VMManager()
    vm.start_vm()
    
    mock_dom.create.assert_called_once()

@patch("libvirt.open")
def test_revert_snapshot(mock_libvirt_open):
    mock_conn = MagicMock()
    mock_dom = MagicMock()
    mock_snap = MagicMock()
    
    mock_libvirt_open.return_value = mock_conn
    mock_conn.lookupByName.return_value = mock_dom
    mock_dom.snapshotLookupByName.return_value = mock_snap
    
    vm = VMManager()
    vm.revert_to_snapshot("clean_state")
    
    mock_dom.snapshotLookupByName.assert_called_with("clean_state")
    mock_dom.revertToSnapshot.assert_called_with(mock_snap)
