"""
Device data handler for managing individual device CSV files.
"""
import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Dict
from utils.logger import setup_logger
from utils.turn_validator import TurnValidator
from data_manager.csv_handler import CSVHandler

class DeviceDataHandler:
    def __init__(self, data_dir: str = 'data/device_logs'):
        self.logger = setup_logger('device_data_handler')
        self.data_dir = Path(data_dir)
        self.csv_handler = CSVHandler()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # Path to zones.csv (used to load zone connections generically)
        self.zones_csv_path = self.data_dir.parent / 'zones.csv'

    def delete_device_files(self, device_id: str) -> None:
        """Delete all log and status files associated with a device ID."""
        try:
            if not device_id:
                return

            # Find all files starting with device_id (e.g., 'rob1.csv', 'rob1_task.csv')
            # Consistent with how files are created in add_device_dialog.py
            files = list(self.data_dir.glob(f"{device_id}*"))
            deleted_count = 0
            
            for file_path in files:
                try:
                    if file_path.is_file():
                        file_path.unlink()
                        self.logger.info(f"Deleted device file: {file_path}")
                        deleted_count += 1
                except Exception as e:
                    self.logger.error(f"Failed to delete file {file_path}: {e}")
            
            self.logger.info(f"Successfully deleted {deleted_count} files for device {device_id}")
        except Exception as e:
            self.logger.error(f"Error during device file cleanup for {device_id}: {e}")

    # ------------------------------
    # Internal helpers
    # ------------------------------
    def _ensure_zone_connections_loaded(self) -> None:
        """Load zone connections from data/zones.csv into the ZoneNavigationManager.

        This is required so that movement processing can resolve target zones and
        directions without any hardcoding. Safe to call repeatedly.
        """
        try:
            if not self.zones_csv_path.exists():
                # No zones file available; skip silently
                return

            import csv as _csv
            zones_data = []
            with open(self.zones_csv_path, 'r', encoding='utf-8') as f:
                reader = _csv.DictReader(f)
                for row in reader:
                    zones_data.append({
                        'id': row.get('id'),
                        'from_zone': row.get('from_zone'),
                        'to_zone': row.get('to_zone'),
                        'direction': (row.get('direction') or '').lower()
                    })

            from utils.zone_navigation_manager import get_zone_navigation_manager
            nav = get_zone_navigation_manager()
            nav.load_zone_connections_from_csv_data(zones_data)
        except Exception as e:
            # Do not fail movement processing just because zone loading failed
            self.logger.warning(f"Could not load zone connections: {e}")

    def _find_connection_direction(self, from_zone: str, to_zone: str) -> str | None:
        """Return direction string for connection from -> to using zones.csv (generic)."""
        try:
            if not self.zones_csv_path.exists():
                return None
            import csv as _csv
            with open(self.zones_csv_path, 'r', encoding='utf-8') as f:
                reader = _csv.DictReader(f)
                for row in reader:
                    if str(row.get('from_zone')) == str(from_zone) and str(row.get('to_zone')) == str(to_zone):
                        return (row.get('direction') or '').lower() or None
        except Exception as e:
            self.logger.warning(f"Error finding connection direction {from_zone}->{to_zone}: {e}")
        return None

    def _find_to_zone_by_direction(self, from_zone: str, direction: str):
        """Return the to_zone for a given from_zone and direction using zones.csv."""
        try:
            if not self.zones_csv_path.exists():
                return None
            import csv as _csv
            with open(self.zones_csv_path, 'r', encoding='utf-8') as f:
                reader = _csv.DictReader(f)
                for row in reader:
                    if (
                        str(row.get('from_zone')) == str(from_zone)
                        and (row.get('direction') or '').lower() == (direction or '').lower()
                    ):
                        return row.get('to_zone')
        except Exception as e:
            self.logger.warning(f"Error finding to_zone from {from_zone} by direction {direction}: {e}")
        return None

    # ------------------------------
    # Public helpers for UI
    # ------------------------------
    def get_zone_transition_info(self, device_id: str) -> Dict:
        """Compute last/current zone and transition direction from recent CSV rows.

        Returns a dict with keys: last_zone, current_zone, transition_direction,
        current_zone_direction (prefer nav lock if available), locked_direction,
        last_route (e.g., "1 -> 2"), current_route (e.g., "2 -> 3"), target_zone,
        and facing_direction (robot's current orientation).
        """
        info = {
            'last_zone': None,
            'current_zone': None,
            'transition_direction': None,
            'current_zone_direction': None,
            'locked_direction': None,
            'last_route': None,
            'current_route': None,
            'target_zone': None,
            'facing_direction': None,
        }

        try:
            # Ensure zone connections are available for resolution
            self._ensure_zone_connections_loaded()

            # Read a window of recent rows (oldest -> newest)
            recent = self.get_recent_device_rows(device_id, count=50)
            if not recent:
                return info

            # Current zone = zone from the newest non-empty row
            curr_zone = None
            for row in reversed(recent):
                z = str(row.get('current_location', '')).strip()
                if z:
                    curr_zone = z
                    break
            if not curr_zone:
                return info

            # Find the previous DISTINCT zone moving backwards
            prev_distinct = None
            saw_current_once = False
            for row in reversed(recent):
                z = str(row.get('current_location', '')).strip()
                if not z:
                    continue
                if not saw_current_once:
                    # Skip all rows equal to current zone at the tail
                    if z == curr_zone:
                        saw_current_once = True
                        continue
                # First row encountered after the tail that differs from current
                if z != curr_zone:
                    prev_distinct = z
                    break

            info['current_zone'] = curr_zone
            info['last_zone'] = prev_distinct

            if prev_distinct and curr_zone and prev_distinct != curr_zone:
                info['transition_direction'] = self._find_connection_direction(prev_distinct, curr_zone)

            # Compose last route string if possible (previous navigated connection)
            if prev_distinct and curr_zone:
                info['last_route'] = f"{prev_distinct} -> {curr_zone}"

            # Prefer locked direction from navigation manager for current zone direction
            try:
                from utils.zone_navigation_manager import get_zone_navigation_manager
                nav = get_zone_navigation_manager()
                nav_info = nav.get_navigation_info(device_id)
                if nav_info.get('is_locked') and nav_info.get('locked_direction'):
                    info['locked_direction'] = nav_info['locked_direction']
                    info['current_zone_direction'] = nav_info['locked_direction']
                elif info['transition_direction']:
                    info['current_zone_direction'] = info['transition_direction']
                
                # Derive target zone preference: use nav_info.target_zone; else resolve by direction
                target_zone = nav_info.get('target_zone')
                if not target_zone and info['current_zone'] and info['current_zone_direction']:
                    target_zone = self._find_to_zone_by_direction(info['current_zone'], info['current_zone_direction'])
                info['target_zone'] = target_zone
                
                # Compose current route string if we have a target
                if info['current_zone'] and info['target_zone']:
                    info['current_route'] = f"{info['current_zone']} -> {info['target_zone']}"

                # Set facing direction: prefer locked, else current_zone_direction
                info['facing_direction'] = info['locked_direction'] or info['current_zone_direction']
            except Exception:
                # Non-fatal if nav info not available
                pass

            return info
        except Exception as e:
            self.logger.warning(f"Failed to compute zone transition info for {device_id}: {e}")
            return info

    def get_latest_device_data(self, device_id: str) -> Dict:
        """
        Get the latest data from a device's log file.

        Args:
            device_id: Device identifier

        Returns:
            Dictionary containing the latest device data with:
                - current_location: formatted location string for display
                - distance: formatted distance string for display
                - direction: Forward/Backward/Stationary based on motor values
        """
        try:
            file_path = self.data_dir / f"{device_id}.csv"
            if not file_path.exists():
                self.logger.warning(f"No log file found for device {device_id}")
                return None

            # Read the latest data from CSV
            with open(file_path, 'r') as f:
                reader = list(csv.DictReader(f))
                if not reader:
                    return None
                
                latest_data = reader[-1]  # Get the last row
                
                # Extract values with default 0 if missing
                right_drive = float(latest_data.get('right_drive', 0))
                left_drive = float(latest_data.get('left_drive', 0))
                right_motor = float(latest_data.get('right_motor', 0))
                left_motor = float(latest_data.get('left_motor', 0))
                
                # Get current location from CSV
                current_location = latest_data.get('current_location', '0')
                
                # Get distance (right_drive) directly in mm
                distance = right_drive
                
                # Use single zone navigation system (consolidated)
                from utils.zone_navigation_manager import get_zone_navigation_manager
                zone_nav_manager = get_zone_navigation_manager()
                # Ensure zone connections are loaded so navigation can resolve targets
                self._ensure_zone_connections_loaded()
                # Ensure zone connections are loaded so navigation can resolve targets
                self._ensure_zone_connections_loaded()

                # Warm up the navigation state with a recent window of rows so that
                # recent turns (Left/Right/U-Turn) correctly set the locked direction
                # even if the latest row is stationary.
                try:
                    recent_rows = self.get_recent_device_rows(device_id, count=120)
                except Exception:
                    recent_rows = []
                if recent_rows and len(recent_rows) > 1:
                    warmup_dir = None
                    for row in recent_rows[:-1]:
                        try:
                            cz = str(row.get('current_location', ''))
                            rd = float(row.get('right_drive', 0))
                            ld = float(row.get('left_drive', 0))
                            rm = float(row.get('right_motor', 0))
                            lm = float(row.get('left_motor', 0))
                            _is_valid, mtype, _reason, _target = zone_nav_manager.process_movement_and_navigate(
                                device_id, cz, rd, ld, rm, lm, warmup_dir
                            )
                            # Sync warmup_dir with locked direction when a turn occurs
                            if mtype in ["Turning Left", "Turning Right", "U-Turn"]:
                                nav_info = zone_nav_manager.get_navigation_info(device_id)
                                if nav_info.get('locked_direction'):
                                    warmup_dir = nav_info['locked_direction']
                        except Exception:
                            # Ignore malformed rows during warmup
                            pass

                # Get current zone from location data
                current_zone = str(latest_data.get('current_location', '1'))

                # Pre-compute best-guess facing/current direction from recent CSV
                # Prefer transition_direction (last route) to reflect actual travel, else fall back to current lock.
                zinfo_pre = self.get_zone_transition_info(device_id)
                current_dir_arg = (
                    (zinfo_pre.get('transition_direction') or zinfo_pre.get('locked_direction'))
                    if isinstance(zinfo_pre, dict) else None
                )

                # Process movement with zone navigation logic (provide current_dir_arg to avoid ambiguous U-turn base)
                is_valid, movement_type, reason, target_zone = zone_nav_manager.process_movement_and_navigate(
                    device_id, current_zone, right_drive, left_drive, right_motor, left_motor, current_dir_arg
                )
                
                if is_valid:
                    direction = movement_type
                    self.logger.info(f"Device {device_id} Zone {current_zone}: {reason}")
                else:
                    # Movement rejected
                    direction = f"Stationary ({movement_type} Rejected)"
                    self.logger.warning(f"Device {device_id} Zone {current_zone}: {reason}")
                
                # Add generic zone transition info for UI
                zinfo = self.get_zone_transition_info(device_id)

                return {
                    'timestamp': latest_data.get('timestamp', ''),
                    'current_location': f"Location {current_location}",
                    'distance': f"{distance:.2f} mm",
                    'direction': direction,
                    'last_zone': zinfo.get('last_zone'),
                    'current_zone': zinfo.get('current_zone'),
                    'transition_direction': zinfo.get('transition_direction'),
                    'current_zone_direction': zinfo.get('current_zone_direction'),
                    'last_route': zinfo.get('last_route'),
                    'current_route': zinfo.get('current_route'),
                    'target_zone': zinfo.get('target_zone'),
                    'facing_direction': zinfo.get('facing_direction')
                }
                
        except Exception as e:
            self.logger.error(f"Error reading device log for {device_id}: {e}")
            return None
    
    def get_raw_device_positioning_data(self, device_id: str) -> Dict:
        """
        Get raw device positioning data for robot placement calculations.

        Args:
            device_id: Device identifier

        Returns:
            Dictionary containing raw positioning data:
                - current_location_zone: zone number as integer
                - right_drive: distance in mm
                - left_drive: distance in mm  
                - direction: Forward/Backward/Stationary
                - timestamp: when this data was recorded
        """
        try:
            file_path = self.data_dir / f"{device_id}.csv"
            if not file_path.exists():
                self.logger.warning(f"No log file found for device {device_id}")
                return None

            # Read the latest data from CSV
            with open(file_path, 'r') as f:
                reader = list(csv.DictReader(f))
                if not reader:
                    return None
                
                latest_data = reader[-1]  # Get the last row
                
                # Extract raw values
                right_drive = float(latest_data.get('right_drive', 0))
                left_drive = float(latest_data.get('left_drive', 0))
                right_motor = float(latest_data.get('right_motor', 0))
                left_motor = float(latest_data.get('left_motor', 0))
                
                # Get current location as integer (zone number)
                current_location = int(latest_data.get('current_location', 0))
                
                # Use single zone navigation system (consolidated)
                from utils.zone_navigation_manager import get_zone_navigation_manager
                zone_nav_manager = get_zone_navigation_manager()

                # Get current zone from location data
                current_zone = str(latest_data.get('current_location', '1'))

                # Pre-compute best-guess facing/current direction from recent CSV to anchor turn calculation
                zinfo_pre = self.get_zone_transition_info(device_id)
                current_dir_arg = (
                    (zinfo_pre.get('transition_direction') or zinfo_pre.get('locked_direction'))
                    if isinstance(zinfo_pre, dict) else None
                )

                # Process movement with zone navigation logic
                is_valid, movement_type, reason, target_zone = zone_nav_manager.process_movement_and_navigate(
                    device_id, current_zone, right_drive, left_drive, right_motor, left_motor, current_dir_arg
                )
                
                if is_valid:
                    # Map movement types for raw positioning data
                    if movement_type == "Turning Right":
                        direction = "Right Turn"
                    elif movement_type == "Turning Left":
                        direction = "Left Turn"
                    else:
                        direction = movement_type
                    
                    self.logger.info(f"Device {device_id} Zone {current_zone}: {reason}")
                else:
                    # Movement rejected
                    direction = "Stationary"
                    self.logger.warning(f"Device {device_id} Zone {current_zone}: {reason}")
                
                # Attach zone transition information for consumers that need it
                zinfo = self.get_zone_transition_info(device_id)

                return {
                    'current_location_zone': current_location,
                    'right_drive': right_drive,
                    'left_drive': left_drive,
                    'right_motor': right_motor,
                    'left_motor': left_motor,
                    'direction': direction,
                    'timestamp': latest_data.get('timestamp', ''),
                    'last_zone': zinfo.get('last_zone'),
                    'current_zone': zinfo.get('current_zone'),
                    'transition_direction': zinfo.get('transition_direction'),
                    'current_zone_direction': zinfo.get('current_zone_direction'),
                    'last_route': zinfo.get('last_route'),
                    'current_route': zinfo.get('current_route'),
                    'target_zone': zinfo.get('target_zone'),
                    'facing_direction': zinfo.get('facing_direction')
                }
                
        except Exception as e:
            self.logger.error(f"Error reading raw positioning data for {device_id}: {e}")
            return None

    def get_recent_device_rows(self, device_id: str, count: int = 10) -> list[Dict]:
        """Return the last N rows from a device's CSV log in chronological order.

        Args:
            device_id: Device identifier
            count: Number of most recent rows to return

        Returns:
            List of dict rows (ordered oldest -> newest) or empty list if none
        """
        try:
            file_path = self.data_dir / f"{device_id}.csv"
            if not file_path.exists():
                self.logger.warning(f"No log file found for device {device_id}")
                return []

            with open(file_path, 'r', encoding='utf-8') as f:
                rows = list(csv.DictReader(f))
                if not rows:
                    return []
                # Slice last N rows and preserve order oldest -> newest
                recent = rows[-count:]
                return recent
        except Exception as e:
            self.logger.error(f"Error reading recent rows for device {device_id}: {e}")
            return []
        
    def create_device_log_file(self, device_id: str) -> bool:
        """Create a new CSV file for a device with the required fields."""
        try:
            file_path = self.data_dir / f"{device_id}.csv"
            
            # Define headers for the device log file
            headers = ['timestamp', 'right_drive', 'left_drive', 'right_motor', 'left_motor', 'current_location']
            
            # Create file with headers if it doesn't exist
            if not file_path.exists():
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                self.logger.info(f"Created device log file for device {device_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating device log file for {device_id}: {e}")
            return False

    def create_device_task_file(self, device_id: str) -> bool:
        """Create '<device_id>_task.csv' with headers ['task_id','task_status'] if it doesn't exist."""
        try:
            file_path = self.data_dir / f"{device_id}_task.csv"
            headers = ['task_id', 'task_status']

            if not file_path.exists():
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                self.logger.info(f"Created device task file for device {device_id}: {file_path}")

            return True
        except Exception as e:
            self.logger.error(f"Error creating device task file for {device_id}: {e}")
            return False

    def _resolve_device_id_str(self, assigned_device_ref) -> str | None:
        """Resolve the string device_id from either a numeric devices.id or an existing device_id string."""
        try:
            if assigned_device_ref is None:
                return None
            ref = str(assigned_device_ref).strip()
            # If it looks like a non-numeric device_id, return as-is
            if not ref.isdigit():
                return ref

            # Otherwise map devices.id -> devices.device_id via CSV
            csvh = CSVHandler()
            devices = csvh.read_csv('devices')
            for row in devices:
                if str(row.get('id', '')).strip() == ref:
                    dev_id = (row.get('device_id') or '').strip()
                    return dev_id if dev_id else None
            return None
        except Exception as e:
            self.logger.error(f"Error resolving device id for {assigned_device_ref}: {e}")
            return None

    def append_task_to_device(self, device_id: str, task_id: str, task_status: str = 'pending_task') -> bool:
        """Append a task entry to '<device_id>_task.csv', creating the file if needed."""
        try:
            if not device_id:
                return False
            # Ensure task file exists
            self.create_device_task_file(device_id)

            file_path = self.data_dir / f"{device_id}_task.csv"
            with open(file_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([str(task_id), str(task_status)])
            self.logger.info(f"Appended task {task_id} ({task_status}) to {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error appending task {task_id} for device {device_id}: {e}")
            return False

    def update_device_task_pending_by_task(self, assigned_device_id, task_id: str) -> bool:
        """Given a task with an assigned_device_id (numeric id or device_id), append it as pending in the device task CSV."""
        try:
            device_id_str = self._resolve_device_id_str(assigned_device_id)
            if not device_id_str:
                self.logger.warning(f"Could not resolve device_id string for assigned_device_id={assigned_device_id}; skipping device task update for task {task_id}")
                return False
            return self.append_task_to_device(device_id_str, task_id, 'pending_task')
        except Exception as e:
            self.logger.error(f"Error updating device task file for task {task_id} (assigned_device_id={assigned_device_id}): {e}")
            return False

    def set_task_status_for_task(self, assigned_device_ref, task_id: str, task_status: str) -> bool:
        """Resolve device id and append a status command row for the given task in '<device_id>_task.csv'.

        This does not rewrite existing rows; it appends a new row [task_id, task_status].
        """
        try:
            device_id_str = self._resolve_device_id_str(assigned_device_ref)
            if not device_id_str:
                self.logger.warning(f"Could not resolve device_id for assigned_device_ref={assigned_device_ref}")
                return False
            return self.append_task_to_device(device_id_str, task_id, task_status)
        except Exception as e:
            self.logger.error(f"Error setting task status '{task_status}' for task {task_id}: {e}")
            return False

    def get_latest_task_status_for_task(self, assigned_device_ref, task_id: str) -> str | None:
        """Resolve device id and read the latest status for a given task_id from '<device_id>_task.csv'.

        Returns the most recent task_status string or None if not found.
        """
        try:
            device_id_str = self._resolve_device_id_str(assigned_device_ref)
            if not device_id_str:
                return None
            file_path = self.data_dir / f"{device_id_str}_task.csv"
            if not file_path.exists():
                return None
            latest_status = None
            with open(file_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if str(row.get('task_id')) == str(task_id):
                        latest_status = row.get('task_status')
            return latest_status
        except Exception as e:
            self.logger.error(f"Error reading latest task status for task {task_id}: {e}")
            return None
            
    def log_device_data(self, device_id: str, right_motor: float, left_motor: float,
                       right_drive: float, left_drive: float, current_location: int = None) -> bool:
        """
        Log device data to its specific CSV file.
        
        Args:
            device_id: Device identifier
            right_motor: Right motor position in millimeters
            left_motor: Left motor position in millimeters
            right_drive: Right drive angle in degrees
            left_drive: Left drive angle in degrees
            current_location: Current location/zone of the device
        """
        try:
            file_path = self.data_dir / f"{device_id}.csv"
            
            # Create file if it doesn't exist
            if not file_path.exists():
                self.create_device_log_file(device_id)
            
            # Add new data row
            with open(file_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                timestamp = datetime.now().isoformat()
                writer.writerow([
                    timestamp,
                    f"{right_drive:.2f}",  # degrees
                    f"{left_drive:.2f}",   # degrees
                    f"{right_motor:.2f}",  # millimeters
                    f"{left_motor:.2f}",   # millimeters
                    str(current_location) if current_location is not None else ''
                ])
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error logging data for device {device_id}: {e}")
            return False
    
    def update_device_location(self, device_id: str, new_location: int) -> bool:
        """
        Update the current location in a device's log file by modifying the latest entry.
        
        Args:
            device_id: Device identifier
            new_location: New location/zone for the device
            
        Returns:
            True if successful, False otherwise
        """
        try:
            file_path = self.data_dir / f"{device_id}.csv"
            
            if not file_path.exists():
                self.logger.warning(f"No log file found for device {device_id}")
                return False
            
            # Read all existing data
            rows = []
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            if not rows:
                self.logger.warning(f"No data found in log file for device {device_id}")
                return False
            
            # Update the location in the latest row
            rows[-1]['current_location'] = str(new_location)
            
            # Write back the updated data
            fieldnames = rows[0].keys() if rows else []
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            
            self.logger.info(f"Updated location for device {device_id} to {new_location}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating location for device {device_id}: {e}")
            return False
    
    def log_location_change(self, device_id: str, new_location: int) -> bool:
        """
        Log a location change for a device by adding a new entry with current motor/drive data.
        
        Args:
            device_id: Device identifier
            new_location: New location/zone for the device
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get the latest data to preserve motor/drive values
            raw_data = self.get_raw_device_positioning_data(device_id)
            
            if raw_data:
                # Use existing motor/drive data with new location
                return self.log_device_data(
                    device_id=device_id,
                    right_motor=raw_data.get('right_motor', 0),
                    left_motor=raw_data.get('left_motor', 0),
                    right_drive=raw_data.get('right_drive', 0),
                    left_drive=raw_data.get('left_drive', 0),
                    current_location=new_location
                )
            else:
                # Create new entry with zeros for motor/drive data
                return self.log_device_data(
                    device_id=device_id,
                    right_motor=0.0,
                    left_motor=0.0,
                    right_drive=0.0,
                    left_drive=0.0,
                    current_location=new_location
                )
                
        except Exception as e:
            self.logger.error(f"Error logging location change for device {device_id}: {e}")
            return False
    
    def get_latest_distance(self, device_id: str) -> float:
        """
        Get the latest distance (right drive value) from a device's log file.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Latest right drive value as distance, or 0.0 if not found
        """
        try:
            file_path = self.data_dir / f"{device_id}.csv"
            if not file_path.exists():
                self.logger.warning(f"No log file found for device {device_id}")
                return 0.0
            
            # Read the latest data from CSV
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = list(csv.DictReader(f))
                if not reader:
                    return 0.0
                
                latest_data = reader[-1]  # Get the last row
                
                # Get right drive value as distance
                right_drive = float(latest_data.get('right_drive', 0))
                return right_drive
                
        except Exception as e:
            self.logger.error(f"Error reading distance for device {device_id}: {e}")
            return 0.0

    def auto_append_run_task_if_pending_call(self, device_id: str, task_id: str) -> bool:
        try:
            call_path = self.data_dir / 'call_requests.csv'
            if not call_path.exists():
                return False
            last_call = None
            with open(call_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    last_call = row
            if not last_call:
                return False
            if str(last_call.get('status', '')).strip().lower() != 'pending':
                return False
            task_path = self.data_dir / f"{device_id}_task.csv"
            if not task_path.exists():
                return False
            last_task = None
            with open(task_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    last_task = row
            if not last_task:
                return False
            if (
                str(last_task.get('task_id')) == str(task_id)
                and str(last_task.get('task_status', '')).strip().lower() == 'task_completed'
            ):
                return self.append_task_to_device(device_id, task_id, 'run_task')
            return False
        except Exception as e:
            self.logger.error(f"Error in auto_append_run_task_if_pending_call for {device_id}/{task_id}: {e}")
            return False
