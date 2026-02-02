#!/usr/bin/env python3
"""
Device Location Sync Utility

This script synchronizes the device management table (devices.csv) with the latest
location data from individual device CSV log files.
"""

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging

from utils.logger import setup_logger
from data_manager.device_data_handler import DeviceDataHandler


class DeviceLocationSyncer:
    def __init__(self, devices_csv_path: str = 'data/devices.csv', 
                 device_logs_dir: str = 'data/device_logs'):
        """
        Initialize the device location syncer.
        
        Args:
            devices_csv_path: Path to the main devices CSV file
            device_logs_dir: Path to the directory containing device log files
        """
        self.logger = setup_logger('device_location_syncer')
        self.devices_csv_path = Path(devices_csv_path)
        self.device_logs_dir = Path(device_logs_dir)
        self.device_data_handler = DeviceDataHandler(device_logs_dir)
        
        # Ensure directories exist
        self.devices_csv_path.parent.mkdir(parents=True, exist_ok=True)
        self.device_logs_dir.mkdir(parents=True, exist_ok=True)
    
    def get_latest_location_from_log(self, device_id: str) -> Optional[int]:
        """
        Get the latest location from a device's log file.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Latest location as integer, or None if not found
        """
        try:
            log_file = self.device_logs_dir / f"{device_id}.csv"
            if not log_file.exists():
                self.logger.warning(f"No log file found for device {device_id}")
                return None
            
            with open(log_file, 'r', encoding='utf-8') as f:
                reader = list(csv.DictReader(f))
                if not reader:
                    return None
                
                # Get the latest entry
                latest_entry = reader[-1]
                location = latest_entry.get('current_location')
                
                if location is not None:
                    return int(location)
                    
        except Exception as e:
            self.logger.error(f"Error reading location from log for device {device_id}: {e}")
            
        return None
    
    def get_latest_distance_from_log(self, device_id: str) -> float:
        """
        Get the latest distance (right drive value) from a device's log file.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Latest right drive value as distance, or 0.0 if not found
        """
        try:
            log_file = self.device_logs_dir / f"{device_id}.csv"
            if not log_file.exists():
                self.logger.warning(f"No log file found for device {device_id}")
                return 0.0
            
            with open(log_file, 'r', encoding='utf-8') as f:
                reader = list(csv.DictReader(f))
                if not reader:
                    return 0.0
                
                # Get the latest entry
                latest_entry = reader[-1]
                right_drive = latest_entry.get('right_drive')
                
                if right_drive is not None:
                    return float(right_drive)
                    
        except Exception as e:
            self.logger.error(f"Error reading distance from log for device {device_id}: {e}")
            
        return 0.0
    
    def read_devices_csv(self) -> List[Dict]:
        """
        Read the current devices CSV file.
        
        Returns:
            List of device dictionaries
        """
        devices = []
        
        if not self.devices_csv_path.exists():
            self.logger.warning(f"Devices CSV file not found: {self.devices_csv_path}")
            return devices
        
        try:
            with open(self.devices_csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                devices = list(reader)
                
        except Exception as e:
            self.logger.error(f"Error reading devices CSV: {e}")
            
        return devices
    
    def write_devices_csv(self, devices: List[Dict]) -> bool:
        """
        Write devices data back to CSV file.
        
        Args:
            devices: List of device dictionaries
            
        Returns:
            True if successful, False otherwise
        """
        if not devices:
            self.logger.warning("No devices to write")
            return False
        
        try:
            # Create backup before modifying
            backup_path = self.devices_csv_path.parent / 'backup' / f"devices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            if self.devices_csv_path.exists():
                import shutil
                shutil.copy2(self.devices_csv_path, backup_path)
                self.logger.info(f"Created backup: {backup_path}")
            
            # Write updated data
            fieldnames = devices[0].keys() if devices else []
            
            with open(self.devices_csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(devices)
            
            self.logger.info(f"Successfully updated devices CSV with {len(devices)} devices")
            return True
            
        except Exception as e:
            self.logger.error(f"Error writing devices CSV: {e}")
            return False
    
    def sync_device_locations(self) -> Dict:
        """
        Synchronize device locations from log files to the main devices CSV.
        
        Returns:
            Dictionary with sync results
        """
        result = {
            'total_devices': 0,
            'updated_devices': 0,
            'unchanged_devices': 0,
            'error_devices': 0,
            'updated_device_ids': [],
            'errors': []
        }
        
        try:
            # Read current devices
            devices = self.read_devices_csv()
            if not devices:
                result['errors'].append("No devices found in CSV file")
                return result
            
            result['total_devices'] = len(devices)
            
            # Add distance column if it doesn't exist
            if devices and 'distance' not in devices[0]:
                for device in devices:
                    device['distance'] = '0.0'  # Default distance
                self.logger.info("Added distance column to devices table")
            
            # Process each device
            for device in devices:
                device_id = device.get('device_id')
                current_location = device.get('current_location')
                current_distance = device.get('distance', '0.0')
                
                if not device_id:
                    result['error_devices'] += 1
                    result['errors'].append(f"Device missing device_id: {device}")
                    continue
                
                try:
                    # Get latest location and distance from log file
                    latest_location = self.get_latest_location_from_log(device_id)
                    latest_distance = self.get_latest_distance_from_log(device_id)
                    
                    location_changed = False
                    distance_changed = False
                    
                    # Check if location needs updating
                    if latest_location is not None and str(current_location) != str(latest_location):
                        device['current_location'] = str(latest_location)
                        location_changed = True
                        self.logger.info(f"Updated device {device_id}: location {current_location} -> {latest_location}")
                    
                    # Check if distance needs updating
                    if abs(float(current_distance) - latest_distance) > 0.01:  # Small tolerance for float comparison
                        device['distance'] = f"{latest_distance:.2f}"
                        distance_changed = True
                        self.logger.info(f"Updated device {device_id}: distance {current_distance} -> {latest_distance:.2f}")
                    
                    # Update timestamp if any changes were made
                    if location_changed or distance_changed:
                        device['updated_at'] = datetime.now().isoformat()
                        result['updated_devices'] += 1
                        result['updated_device_ids'].append(device_id)
                    else:
                        result['unchanged_devices'] += 1
                        
                except Exception as e:
                    result['error_devices'] += 1
                    error_msg = f"Error processing device {device_id}: {e}"
                    result['errors'].append(error_msg)
                    self.logger.error(error_msg)
            
            # Write back updated devices if any changes were made
            if result['updated_devices'] > 0:
                if self.write_devices_csv(devices):
                    self.logger.info(f"Sync completed successfully. Updated {result['updated_devices']} devices.")
                else:
                    result['errors'].append("Failed to write updated devices to CSV")
            else:
                self.logger.info("Sync completed. No location updates needed.")
                
        except Exception as e:
            error_msg = f"Critical error during sync: {e}"
            result['errors'].append(error_msg)
            self.logger.error(error_msg)
        
        return result
    
    def get_sync_status(self) -> Dict:
        """
        Get the current synchronization status between devices CSV and log files.
        
        Returns:
            Dictionary with sync status information
        """
        status = {
            'devices_in_csv': 0,
            'devices_with_logs': 0,
            'devices_out_of_sync': [],
            'devices_missing_logs': [],
            'last_sync_check': datetime.now().isoformat()
        }
        
        try:
            devices = self.read_devices_csv()
            status['devices_in_csv'] = len(devices)
            
            for device in devices:
                device_id = device.get('device_id')
                if not device_id:
                    continue
                
                current_location = device.get('current_location')
                log_file = self.device_logs_dir / f"{device_id}.csv"
                
                if log_file.exists():
                    status['devices_with_logs'] += 1
                    latest_location = self.get_latest_location_from_log(device_id)
                    latest_distance = self.get_latest_distance_from_log(device_id)
                    
                    current_distance = device.get('distance', '0.0')
                    location_out_of_sync = latest_location is not None and str(current_location) != str(latest_location)
                    distance_out_of_sync = abs(float(current_distance) - latest_distance) > 0.01
                    
                    if location_out_of_sync or distance_out_of_sync:
                        status['devices_out_of_sync'].append({
                            'device_id': device_id,
                            'csv_location': current_location,
                            'log_location': latest_location,
                            'csv_distance': current_distance,
                            'log_distance': f"{latest_distance:.2f}",
                            'location_sync': not location_out_of_sync,
                            'distance_sync': not distance_out_of_sync
                        })
                else:
                    status['devices_missing_logs'].append(device_id)
                    
        except Exception as e:
            self.logger.error(f"Error getting sync status: {e}")
        
        return status


def main():
    """Main function to run the sync utility."""
    syncer = DeviceLocationSyncer()
    

    status = syncer.get_sync_status()
    

    if status['devices_out_of_sync']:

        for device in status['devices_out_of_sync']:
            device_id = device['device_id']
            location_status = "✓" if device.get('location_sync', True) else "✗"
            distance_status = "✓" if device.get('distance_sync', True) else "✗"
            
            
    if status['devices_missing_logs']:
        print(f"\nDevices missing log files: {', '.join(status['devices_missing_logs'])}")
    
    # Perform sync

    result = syncer.sync_device_locations()
    

    if result['updated_device_ids']:
        print(f"  Updated device IDs: {', '.join(result['updated_device_ids'])}")
    
    if result['errors']:

        for error in result['errors']:
            print(f"  - {error}")
    



if __name__ == "__main__":
    main()
