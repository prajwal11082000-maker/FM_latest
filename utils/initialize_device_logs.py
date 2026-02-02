"""
Utility script to initialize device log files for existing devices
"""

from data_manager.device_data_handler import DeviceDataHandler
from data_manager.csv_handler import CSVHandler

def initialize_device_logs():
    # Initialize handlers
    device_handler = DeviceDataHandler()
    csv_handler = CSVHandler()
    
    # Read existing devices
    devices = csv_handler.read_csv('devices')
    
    # Create log files for each device
    for device in devices:
        device_id = device.get('device_id')
        if device_id:
            print(f"Creating log file for device: {device_id}")
            device_handler.create_device_log_file(device_id)

if __name__ == "__main__":
    
    initialize_device_logs()
    