from typing import Dict, List, Optional
from .client import APIClient
from utils.logger import setup_logger
from data_manager.device_data_handler import DeviceDataHandler

# Import the sync utility if it exists, otherwise handle gracefully
try:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from sync_device_locations import DeviceLocationSyncer
except ImportError:
    DeviceLocationSyncer = None


class DevicesAPI:
    def __init__(self, client: APIClient):
        self.client = client
        self.logger = setup_logger('devices_api')
        self.device_data_handler = DeviceDataHandler()
        
        # Initialize sync functionality if available
        self.location_syncer = None
        if DeviceLocationSyncer:
            try:
                self.location_syncer = DeviceLocationSyncer()
                self.logger.info("Device location syncer initialized")
            except Exception as e:
                self.logger.warning(f"Could not initialize location syncer: {e}")

    def list_devices(self, params: Dict = None) -> Dict:
        """Get list of all devices"""
        return self.client.get('/devices/', params=params)

    def get_device(self, device_id: int) -> Dict:
        """Get specific device by ID"""
        return self.client.get(f'/devices/{device_id}/')

    def create_device(self, device_data: Dict) -> Dict:
        """Create new device and initialize its data log file and per-device task file"""
        # Create device through API
        response = self.client.post('/devices/', device_data)
        
        # If device creation was successful, create its log file
        if response and 'device_id' in response:
            device_id = response['device_id']
            self.device_data_handler.create_device_log_file(device_id)
            # Also create per-device task tracking CSV: '<device_id>_task.csv'
            try:
                self.device_data_handler.create_device_task_file(device_id)
            except Exception as e:
                self.logger.warning(f"Could not create per-device task file for {device_id}: {e}")
        
        return response

    def update_device(self, device_id: int, device_data: Dict) -> Dict:
        """Update existing device"""
        return self.client.put(f'/devices/{device_id}/', device_data)

    def delete_device(self, device_id: int) -> Dict:
        """Delete device"""
        return self.client.delete(f'/devices/{device_id}/')

    def get_status_summary(self) -> Dict:
        """Get device status summary"""
        return self.client.get('/devices/status_summary/')
        
    def log_device_data(self, device_id: str, right_motor: float, left_motor: float,
                       right_drive: float, left_drive: float, current_location: int = None) -> bool:
        """Log device motor and drive data with optional location"""
        return self.device_data_handler.log_device_data(
            device_id=device_id,
            right_motor=right_motor,
            left_motor=left_motor,
            right_drive=right_drive,
            left_drive=left_drive,
            current_location=current_location
        )
    
    def update_device_location(self, device_id: str, new_location: int) -> bool:
        """Update device location in its log file"""
        return self.device_data_handler.update_device_location(device_id, new_location)
    
    def log_location_change(self, device_id: str, new_location: int) -> bool:
        """Log a location change for a device"""
        return self.device_data_handler.log_location_change(device_id, new_location)
    
    def get_device_distance(self, device_id: str) -> float:
        """Get the latest distance (right drive value) for a device"""
        return self.device_data_handler.get_latest_distance(device_id)
    
    def sync_device_locations(self) -> Dict:
        """Synchronize device locations from log files to main CSV table"""
        if not self.location_syncer:
            return {
                'error': 'Location syncer not available',
                'total_devices': 0,
                'updated_devices': 0,
                'unchanged_devices': 0,
                'error_devices': 0,
                'updated_device_ids': [],
                'errors': ['Device location syncer not initialized']
            }
        
        try:
            result = self.location_syncer.sync_device_locations()
            self.logger.info(f"Location sync completed. Updated {result.get('updated_devices', 0)} devices.")
            return result
        except Exception as e:
            error_msg = f"Error during location sync: {e}"
            self.logger.error(error_msg)
            return {
                'error': error_msg,
                'total_devices': 0,
                'updated_devices': 0,
                'unchanged_devices': 0,
                'error_devices': 1,
                'updated_device_ids': [],
                'errors': [error_msg]
            }
    
    def get_sync_status(self) -> Dict:
        """Get the current synchronization status between devices CSV and log files"""
        if not self.location_syncer:
            return {
                'error': 'Location syncer not available',
                'devices_in_csv': 0,
                'devices_with_logs': 0,
                'devices_out_of_sync': [],
                'devices_missing_logs': [],
                'last_sync_check': None
            }
        
        try:
            return self.location_syncer.get_sync_status()
        except Exception as e:
            self.logger.error(f"Error getting sync status: {e}")
            return {
                'error': f'Error getting sync status: {e}',
                'devices_in_csv': 0,
                'devices_with_logs': 0,
                'devices_out_of_sync': [],
                'devices_missing_logs': [],
                'last_sync_check': None
            }
