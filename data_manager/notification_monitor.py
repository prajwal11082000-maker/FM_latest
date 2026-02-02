"""
Notification Monitor for device log files.
Monitors device-specific CSV files for changes and generates system notifications.
"""
import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from utils.logger import setup_logger
from data_manager.csv_handler import CSVHandler


class NotificationMonitor:
    """
    Monitors device log files for changes and generates system notifications.
    
    Responsibilities:
    - Track file modifications using line counts
    - Parse new entries from monitored CSV files
    - Update devices.csv when battery/charging status changes
    - Generate notification objects for dashboard display
    """
    
    def __init__(self, csv_handler: CSVHandler = None):
        self.logger = setup_logger('notification_monitor')
        self.csv_handler = csv_handler or CSVHandler()
        self.data_dir = Path('data/device_logs')
        self.devices_csv_path = Path('data/devices.csv')
        
        # Track file states: {file_path: last_line_count}
        self.file_states: Dict[str, int] = {}
        
        # Pending notifications to display
        self.notifications: List[Dict] = []
        
        self.logger.info("NotificationMonitor initialized")
    
    def scan_for_notifications(self) -> List[Dict]:
        """
        Scan all device log files for new entries.
        
        Returns:
            List of notification dicts with keys:
            - device_id: Device identifier
            - message: Notification message
            - alert_type: 'warning', 'error', 'info', 'success'
            - timestamp: When the event occurred
        """
        self.notifications = []
        
        try:
            # Get list of all devices
            devices = self._get_device_ids()
            
            for device_id in devices:
                # Process each type of log file
                self._process_battery_status(device_id)
                self._process_charging_status(device_id)
                self._process_alarm_status(device_id)
                self._process_obstacle(device_id)
                self._process_emergency_status(device_id)
                
        except Exception as e:
            self.logger.error(f"Error scanning for notifications: {e}")
        
        return self.notifications
    
    def _get_device_ids(self) -> List[str]:
        """Get list of all device IDs from devices.csv"""
        try:
            devices = self.csv_handler.read_csv('devices')
            return [d.get('device_id', '') for d in devices if d.get('device_id')]
        except Exception as e:
            self.logger.error(f"Error reading devices: {e}")
            return []
    
    def _get_new_entries(self, file_path: Path) -> List[Dict]:
        """
        Get new entries from a CSV file since last scan.
        
        Args:
            file_path: Path to the CSV file
            
        Returns:
            List of new row dictionaries
        """
        if not file_path.exists():
            return []
        
        try:
            with open(file_path, 'r', newline='', encoding='utf-8') as f:
                reader = list(csv.DictReader(f))
            
            current_count = len(reader)
            file_key = str(file_path)
            
            # Get last known line count
            last_count = self.file_states.get(file_key, 0)
            
            # Update state
            self.file_states[file_key] = current_count
            
            # Return only new entries
            if current_count > last_count:
                return reader[last_count:]
            
            return []
            
        except Exception as e:
            self.logger.error(f"Error reading {file_path}: {e}")
            return []
    
    def _process_battery_status(self, device_id: str):
        """
        Process battery status file and update devices.csv battery_level.
        
        File: {device_id}_Battery_status.csv
        Columns: battery_percentage, timestamp
        
        Always syncs the latest battery_percentage value to devices.csv
        """
        file_path = self.data_dir / f"{device_id}_Battery_status.csv"
        
        if not file_path.exists():
            return
        
        try:
            with open(file_path, 'r', newline='', encoding='utf-8') as f:
                reader = list(csv.DictReader(f))
            
            if not reader:
                return
            
            # Always get the latest entry and sync it
            latest = reader[-1]
            battery_percentage = latest.get('battery_percentage', '')
            
            if battery_percentage:
                try:
                    battery_level = int(float(battery_percentage))
                    self._update_device_field(device_id, 'battery_level', battery_level)
                except ValueError:
                    self.logger.warning(f"Invalid battery percentage for {device_id}: {battery_percentage}")
                    
        except Exception as e:
            self.logger.error(f"Error processing battery status for {device_id}: {e}")
    
    def _process_charging_status(self, device_id: str):
        """
        Process charging status file and update devices.csv status when charging.
        
        File: {device_id}_Charging_Status.csv
        Columns: Charging_type (or charging_status), timestamp
        
        When value is '1' or '1.0', update status to 'charging'
        When value is '0', '0.0' or other, update status to 'working'
        Always syncs the latest charging status to devices.csv
        """
        file_path = self.data_dir / f"{device_id}_Charging_Status.csv"
        
        if not file_path.exists():
            return
        
        try:
            with open(file_path, 'r', newline='', encoding='utf-8') as f:
                reader = list(csv.DictReader(f))
            
            if not reader:
                return
            
            # Helper to check if value indicates charging
            def is_charging_value(val):
                if not val:
                    return False
                try:
                    return float(val) == 1.0
                except ValueError:
                    return False

            # Helper to check if value indicates stopped charging (0)
            def is_stopped_value(val):
                if not val:
                    return False
                try:
                    return float(val) == 0.0
                except ValueError:
                    return False

            # Get the latest entry for status sync
            latest = reader[-1]
            # Handle both column names
            charging_type = latest.get('Charging_type') or latest.get('charging_status') or ''
            charging_type = charging_type.strip()
            timestamp = latest.get('timestamp', '')
            
            # Always update status based on latest charging type
            if is_charging_value(charging_type):
                self._update_device_field(device_id, 'status', 'charging')
            else:
                self._update_device_field(device_id, 'status', 'working')
            
            # Process new entries for notifications
            new_entries = self._get_new_entries(file_path)
            for entry in new_entries:
                entry_val = entry.get('Charging_type') or entry.get('charging_status') or ''
                entry_val = entry_val.strip()
                entry_timestamp = entry.get('timestamp', '')
                
                if is_charging_value(entry_val):
                    self.notifications.append({
                        'device_id': device_id,
                        'message': f"{device_id} started charging at {self._format_timestamp(entry_timestamp)}",
                        'alert_type': 'info',
                        'timestamp': entry_timestamp
                    })
                elif is_stopped_value(entry_val):
                    self.notifications.append({
                        'device_id': device_id,
                        'message': f"{device_id} stopped charging at {self._format_timestamp(entry_timestamp)}",
                        'alert_type': 'info',
                        'timestamp': entry_timestamp
                    })
                    
        except Exception as e:
            self.logger.error(f"Error processing charging status for {device_id}: {e}")
    
    def _process_alarm_status(self, device_id: str):
        """
        Process alarm status file and generate notifications for specific alarms.
        
        File: {device_id}_Alarm_status.csv
        Columns: alarmRM, alarmLM, timestamp
        
        Shows notification with actual error code values from alarmRM and alarmLM.
        Format: "{device_id} detected right_alarm/left_alarm with error code {value} at {timestamp}"
        No notification when alarmRM=0 or alarmLM=0
        """
        file_path = self.data_dir / f"{device_id}_Alarm_status.csv"
        
        if not file_path.exists():
            return
        
        try:
            with open(file_path, 'r', newline='', encoding='utf-8') as f:
                reader = list(csv.DictReader(f))
            
            if not reader:
                return
            
            # Get the LATEST entry to determine current alarm state
            latest = reader[-1]
            alarm_rm = latest.get('alarmRM', '').strip()
            alarm_lm = latest.get('alarmLM', '').strip()
            timestamp = latest.get('timestamp', '')
            
            # Check for right motor alarm (alarmRM)
            # Show notification with error code if value is not '0' and not empty
            if alarm_rm and alarm_rm != '0':
                self.notifications.append({
                    'device_id': device_id,
                    'message': f"{device_id} detected right_alarm with error code {alarm_rm} at {self._format_timestamp(timestamp)}",
                    'alert_type': 'warning',
                    'timestamp': timestamp
                })
            
            # Check for left motor alarm (alarmLM)
            # Show notification with error code if value is not '0' and not empty
            if alarm_lm and alarm_lm != '0':
                self.notifications.append({
                    'device_id': device_id,
                    'message': f"{device_id} detected left_alarm with error code {alarm_lm} at {self._format_timestamp(timestamp)}",
                    'alert_type': 'warning',
                    'timestamp': timestamp
                })
            # Value '0' or empty = no notification (alarm cleared)
                
        except Exception as e:
            self.logger.error(f"Error processing alarm status for {device_id}: {e}")
    
    def _process_obstacle(self, device_id: str):
        """
        Process obstacle file and generate notifications when obstacle detected.
        
        File: {device_id}_obstacle.csv
        Columns: obstacle, timestamp
        
        Shows persistent notification while obstacle value is '1'
        Notification disappears when value changes to '0' or other
        """
        file_path = self.data_dir / f"{device_id}_obstacle.csv"
        
        if not file_path.exists():
            return
        
        try:
            with open(file_path, 'r', newline='', encoding='utf-8') as f:
                reader = list(csv.DictReader(f))
            
            if not reader:
                return
            
            # Get the LATEST entry to determine current obstacle state
            latest = reader[-1]
            obstacle = latest.get('obstacle', '').strip()
            timestamp = latest.get('timestamp', '')
            
            # Show notification only if current obstacle value is '1'
            if obstacle == '1':
                self.notifications.append({
                    'device_id': device_id,
                    'message': f"{device_id} detected obstacle at {self._format_timestamp(timestamp)}",
                    'alert_type': 'error',
                    'timestamp': timestamp
                })
            # Value '0' or other = no notification (obstacle cleared)
                
        except Exception as e:
            self.logger.error(f"Error processing obstacle for {device_id}: {e}")

    def _process_emergency_status(self, device_id: str):
        """
        Process emergency status file and generate notifications when emergency stop detected.
        
        File: {device_id}_emergency_status.csv
        Columns: switch_status, timestamp
        
        Shows notification when switch_status value is '1' or '1.0'
        Notification disappears when value changes to '0' or other
        """
        file_path = self.data_dir / f"{device_id}_emergency_status.csv"
        
        if not file_path.exists():
            return
        
        try:
            with open(file_path, 'r', newline='', encoding='utf-8') as f:
                reader = list(csv.DictReader(f))
            
            if not reader:
                return
            
            # Get the LATEST entry to determine current emergency status
            latest = reader[-1]
            switch_status = latest.get('switch_status', '').strip()
            timestamp = latest.get('timestamp', '')
            
            # Check if switch_status indicates emergency stop (1 or 1.0)
            is_emergency = False
            if switch_status:
                try:
                    is_emergency = float(switch_status) == 1.0
                except ValueError:
                    is_emergency = False
            
            # Show notification if emergency stop is detected
            if is_emergency:
                self.notifications.append({
                    'device_id': device_id,
                    'message': f"{device_id} detected emergency stop at {self._format_timestamp(timestamp)}",
                    'alert_type': 'error',
                    'timestamp': timestamp
                })
            # Value '0' or other = no notification (emergency cleared)
                
        except Exception as e:
            self.logger.error(f"Error processing emergency status for {device_id}: {e}")
    
    def _update_device_field(self, device_id: str, field: str, value) -> bool:
        """
        Update a specific field in devices.csv for the given device_id.
        
        Args:
            device_id: Device identifier
            field: Column name to update
            value: New value for the field
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Read current devices
            devices = self.csv_handler.read_csv('devices')
            
            # Find and update the device
            updated = False
            for device in devices:
                if device.get('device_id') == device_id:
                    device[field] = value
                    device['updated_at'] = datetime.now().isoformat()
                    updated = True
                    break
            
            if updated:
                # Write back to CSV
                self.csv_handler.write_csv('devices', devices)
                return True
            else:
                self.logger.warning(f"Device {device_id} not found in devices.csv")
                return False
                
        except Exception as e:
            self.logger.error(f"Error updating device {device_id} field {field}: {e}")
            return False
    
    def _format_timestamp(self, timestamp: str) -> str:
        """Format timestamp for display in notifications."""
        if not timestamp:
            return "unknown time"
        
        try:
            # Parse ISO format timestamp
            if 'T' in timestamp:
                dt = datetime.fromisoformat(timestamp.replace('Z', ''))
                return dt.strftime('%H:%M:%S')
            return timestamp
        except Exception:
            return timestamp
    
    def reset_file_states(self):
        """Reset file state tracking. Useful when restarting monitoring."""
        self.file_states = {}
        self.logger.info("File states reset")
