import os
import csv
import json
import glob
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from PyQt5.QtCore import QTimer

from data_manager.csv_handler import CSVHandler
from data_manager.device_data_handler import DeviceDataHandler
from ui.tasks.distance_calculator import DistanceCalculator
from services.path_planner_service import plan_and_write_picking_path, plan_and_write_picking_path_4stops
from utils.logger import setup_logger

class AutomaticTaskService:
    def __init__(self, csv_handler: CSVHandler, device_data_handler: DeviceDataHandler):
        self.csv_handler = csv_handler
        self.device_data_handler = device_data_handler
        self.distance_calculator = DistanceCalculator(csv_handler)
        self.logger = setup_logger('automatic_task_service')
        self.data_dir = Path('data')

    def monitor_and_process(self):
        """Scan for create_pickup_task and charging_task_automation CSV files and process them."""
        # 1. Handle creation of new pickup tasks
        pattern = str(self.data_dir / "*_create_pickup_task.csv")
        files = glob.glob(pattern)
        for file_path in files:
            try:
                self._process_csv(file_path)
            except Exception as e:
                self.logger.error(f"Error processing {file_path}: {e}")
        
        # 2. Handle creation of new charging tasks
        charging_pattern = str(self.data_dir / "*_create_charging_task.csv")
        charging_files = glob.glob(charging_pattern)
        for file_path in charging_files:
            try:
                self._process_charging_csv(file_path)
            except Exception as e:
                self.logger.error(f"Error processing charging CSV {file_path}: {e}")
        
        # 3. Sync statuses for active tasks (handles both auto and manual tasks feedback)
        self.sync_task_statuses()

    def sync_task_statuses(self):
        """Synchronize task statuses from device logs to tasks.csv."""
        try:
            tasks = self.csv_handler.read_csv('tasks')
            active_tasks = [t for t in tasks if str(t.get('status')).lower() in ['pending', 'running', 'processing']]
            
            if not active_tasks:
                return

            for task in active_tasks:
                task_id = task.get('task_id')
                # Primary device for monitoring. 
                # For multi-device tasks, we typically use assigned_device_id as primary reporter.
                device_ref = task.get('assigned_device_id')
                if not device_ref or not task_id:
                    continue

                curr_status = str(task.get('status')).lower()
                
                # Check device log for feedback
                latest_feedback = self.device_data_handler.get_latest_task_status_for_task(device_ref, task_id)
                if not latest_feedback:
                    continue
                
                latest_feedback = str(latest_feedback).lower()
                
                # Update status based on device feedback
                if curr_status == 'pending' and latest_feedback == 'executing_task':
                    self.logger.info(f"Sync: Task {task_id} on {device_ref} is now EXECUTING")
                    task['status'] = 'running'
                    task['started_at'] = datetime.now().isoformat()
                    self.csv_handler.update_csv_row('tasks', task.get('id'), task)
                
                elif curr_status in ['running', 'processing'] and latest_feedback == 'task_completed':
                    self.logger.info(f"Sync: Task {task_id} on {device_ref} is COMPLETED")
                    task['status'] = 'completed'
                    task['completed_at'] = datetime.now().isoformat()
                    
                    # Calculate duration
                    try:
                        started = datetime.fromisoformat(task.get('started_at', '').replace('Z', ''))
                        now = datetime.now()
                        task['actual_duration'] = int((now - started).total_seconds())
                    except Exception:
                        task['actual_duration'] = 0
                        
                    self.csv_handler.update_csv_row('tasks', task.get('id'), task)
                    
                    # Check battery and create charging task if needed
                    # Skip this for charging tasks themselves to avoid infinite charging loops
                    if str(task.get('task_type', '')).lower() != 'charging':
                        self._check_battery_and_create_charging_task(device_ref, task.get('map_id'))
        except Exception as e:
            self.logger.error(f"Error in sync_task_statuses: {e}")

    def _process_csv(self, file_path: str):
        file_path_obj = Path(file_path)
        filename = file_path_obj.name
        # Extract map_id from filename (e.g., 15_create_pickup_task.csv)
        try:
            map_id = filename.split('_')[0]
        except Exception:
            self.logger.warning(f"Could not extract map_id from filename: {filename}")
            return

        rows = []
        reserved_this_cycle = set()
        updated = False
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if row.get('action') == 'create_task':
                    success = self._handle_create_task(map_id, row, reserved_this_cycle)
                    if success:
                        row['action'] = 'task_created'
                        updated = True
                rows.append(row)

        if updated:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            self.logger.info(f"Updated {filename} with task_created status.")

    def _handle_create_task(self, map_id: str, row: Dict, reserved_this_cycle: set) -> bool:
        # Support both old format (stop_id, drop_zone) and new format (Pickup_stopid, check_stop_id, drop_stop_id, end_stop_id, end_zone)
        pickup_stop_id = row.get('Pickup_stopid') or row.get('stop_id')
        check_stop_id = row.get('check_stop_id')
        drop_stop_id = row.get('drop_stop_id')
        end_stop_id = row.get('end_stop_id')
        end_zone = row.get('end_zone') or row.get('drop_zone')

        if not pickup_stop_id or not end_zone:
            self.logger.warning(f"Incomplete data in CSV: pickup_stop_id={pickup_stop_id}, end_zone={end_zone}")
            return False
        
        # New 4-stop format requires all stops
        use_4stop_format = bool(check_stop_id and drop_stop_id and end_stop_id)
        
        if use_4stop_format and not (check_stop_id and drop_stop_id and end_stop_id):
            self.logger.warning(f"Incomplete 4-stop data: check={check_stop_id}, drop={drop_stop_id}, end={end_stop_id}")
            return False

        # 1. Find eligible devices (battery > 20, not running/pending task, not reserved this cycle)
        eligible_devices = self._get_eligible_devices(map_id, excluded_device_ids=reserved_this_cycle)
        if not eligible_devices:
            self.logger.info(f"No eligible devices found for move {stop_id} -> {drop_zone} on map {map_id}")
            return False

        # 2. Select nearest device
        selected_device = self._select_nearest_device(map_id, eligible_devices, pickup_stop_id)
        if not selected_device:
            self.logger.warning(f"Could not calculate proximity or select device.")
            return False

        # 3. Create task
        if use_4stop_format:
            task_data = self._build_task_data_4stops(map_id, selected_device, pickup_stop_id, check_stop_id, drop_stop_id, end_stop_id, end_zone)
        else:
            task_data = self._build_task_data(map_id, selected_device, pickup_stop_id, end_zone)
            
        if self.csv_handler.append_to_csv('tasks', task_data):
            self.logger.info(f"Automatically created task {task_data['task_id']} for device {selected_device['device_id']}")
            
            # Add to reservation for this cycle
            reserved_this_cycle.add(str(selected_device['id']))
            
            # 4. Generate Path Planning
            try:
                if use_4stop_format:
                    plan_and_write_picking_path_4stops(
                        device_id=selected_device['device_id'],
                        map_id=map_id,
                        pickup_stop_id=pickup_stop_id,
                        check_stop_id=check_stop_id,
                        drop_stop_id=drop_stop_id,
                        end_stop_id=end_stop_id,
                        end_zone=end_zone
                    )
                else:
                    plan_and_write_picking_path(
                        device_id=selected_device['device_id'],
                        map_id=map_id,
                        pickup_stops=[pickup_stop_id],
                        drop_zone=end_zone
                    )
                self.logger.info(f"Generated path planning for device {selected_device['device_id']}")
                
                # Update device task status to pending_task in its local CSV
                device_id_str = self.device_data_handler._resolve_device_id_str(selected_device['id'])
                if device_id_str:
                    self.device_data_handler.append_task_to_device(device_id_str, task_data['task_id'], 'pending_task')
                
                # New logic: Auto trigger picking tasks after 7 seconds
                if task_data.get('task_type') == 'picking':
                    self.logger.info(f"Scheduling auto-run for task {task_data['task_id']} in 7 seconds")
                    # Capture current values in lambda
                    device_ref = selected_device['id']
                    tid = task_data['task_id']
                    QTimer.singleShot(7000, lambda: self._trigger_automatic_execution(device_ref, tid))
                
                return True
            except Exception as e:
                self.logger.error(f"Failed to generate path planning: {e}")
                return True 
        
        return False

    def _get_eligible_devices(self, map_id: str, excluded_device_ids: set = None) -> List[Dict]:
        all_devices = self.csv_handler.read_csv('devices')
        tasks = self.csv_handler.read_csv('tasks')
        
        if excluded_device_ids is None:
            excluded_device_ids = set()

        unavailable_device_ids = set(excluded_device_ids)
        for t in tasks:
            status = t.get('status', '').lower()
            if status in ['running', 'pending']:
                did = t.get('assigned_device_id')
                if did: unavailable_device_ids.add(str(did))
                dids = t.get('assigned_device_ids', '')
                if dids:
                    for d in str(dids).split(','):
                        if d.strip(): unavailable_device_ids.add(d.strip())

        eligible = []
        for d in all_devices:
            # battery_level > 30
            try:
                battery = float(d.get('battery_level', 0))
            except ValueError:
                battery = 0
            
            # Should be in the right map
            if str(d.get('current_map')) != str(map_id):
                continue
                
            if battery > 30 and str(d.get('id')) not in unavailable_device_ids:
                eligible.append(d)
        
        return eligible

    def _select_nearest_device(self, map_id: str, devices: List[Dict], target_stop_id: str) -> Optional[Dict]:
        if not devices:
            return None
        
        # Get target stop zone
        stops = self.csv_handler.read_csv('stops')
        target_stop = next((s for s in stops if str(s.get('stop_id')) == str(target_stop_id) and str(s.get('map_id')) == str(map_id)), None)
        if not target_stop:
            self.logger.warning(f"Stop {target_stop_id} not found in map {map_id}")
            return None
        
        # We need a zone info for distance calculator
        zones = self.csv_handler.read_csv('zones')
        conn_id = target_stop.get('zone_connection_id')
        target_zone_row = next((z for z in zones if str(z.get('id')) == str(conn_id)), None)
        if not target_zone_row:
            return None
        
        target_zone = target_zone_row.get('from_zone') # Heuristic

        best_device = None
        min_dist = float('inf')

        for d in devices:
            curr_loc = d.get('current_location')
            if not curr_loc:
                dist = 999999.0 # Penalty
            else:
                # Use distance calculator to find path distance
                dist = self.distance_calculator.calculate_path_distance(
                    map_id, str(curr_loc), str(target_zone), include_all_stops=False
                )
                if dist == 0 and str(curr_loc) != str(target_zone):
                    dist = 999999.0 # unreachable
            
            if dist < min_dist:
                min_dist = dist
                best_device = d
        
        return best_device

    def _build_task_data(self, map_id: str, device: Dict, stop_id: str, drop_zone: str) -> Dict:
        task_id = f"TASK{self.csv_handler.get_next_id('tasks'):04d}"
        current_time = datetime.now().isoformat()
        
        details = {
            'pickup_map_id': str(map_id),
            'pickup_stops': [stop_id],
            'drop_zone': str(drop_zone),
            'automatic': True
        }

        return {
            'id': '',
            'task_id': task_id,
            'task_name': f"Auto Pickup - {stop_id}",
            'task_type': 'picking',
            'status': 'pending',
            'assigned_device_id': str(device['id']),
            'assigned_device_ids': str(device['id']),
            'assigned_user_id': '',
            'description': f"Automatically created from CSV for stop {stop_id}",
            'estimated_duration': '',
            'actual_duration': '',
            'created_at': current_time,
            'started_at': '',
            'completed_at': '',
            'map_id': str(map_id),
            'zone_ids': '',
            'stop_ids': str(stop_id),
            'task_details': json.dumps(details)
        }

    def _build_task_data_4stops(self, map_id: str, device: Dict, pickup_stop_id: str, check_stop_id: str, drop_stop_id: str, end_stop_id: str, end_zone: str) -> Dict:
        task_id = f"TASK{self.csv_handler.get_next_id('tasks'):04d}"
        current_time = datetime.now().isoformat()
        
        details = {
            'pickup_map_id': str(map_id),
            'pickup_stops': [pickup_stop_id],
            'pickup_stop_id': pickup_stop_id,
            'check_stop_id': check_stop_id,
            'drop_stop_id': drop_stop_id,
            'end_stop_id': end_stop_id,
            'end_zone': str(end_zone),
            'drop_zone': str(end_zone),  # For backward compatibility
            'automatic': True
        }

        return {
            'id': '',
            'task_id': task_id,
            'task_name': f"Auto Pickup 4-Stop - {pickup_stop_id}",
            'task_type': 'picking',
            'status': 'pending',
            'assigned_device_id': str(device['id']),
            'assigned_device_ids': str(device['id']),
            'assigned_user_id': '',
            'description': f"Automatically created from CSV: pickup={pickup_stop_id}, check={check_stop_id}, drop={drop_stop_id}, end={end_stop_id}",
            'estimated_duration': '',
            'actual_duration': '',
            'created_at': current_time,
            'started_at': '',
            'completed_at': '',
            'map_id': str(map_id),
            'zone_ids': '',
            'stop_ids': f"{pickup_stop_id},{check_stop_id},{drop_stop_id},{end_stop_id}",
            'task_details': json.dumps(details)
        }

    def _trigger_automatic_execution(self, device_ref: str, task_id: str):
        """Automatically trigger task execution in the device task CSV."""
        try:
            device_id_str = self.device_data_handler._resolve_device_id_str(device_ref)
            if device_id_str:
                success = self.device_data_handler.append_task_to_device(device_id_str, task_id, 'run_task')
                if success:
                    self.logger.info(f"Automatically triggered execution (run_task) for task {task_id} on device {device_id_str}")
                else:
                    self.logger.warning(f"Failed to automatically trigger execution for task {task_id}")
        except Exception as e:
            self.logger.error(f"Error in automatic task trigger: {e}")

    def _check_battery_and_create_charging_task(self, device_ref: str, map_id: Optional[str]):
        """
        Check device battery and queue after task completion.
        
        Rules:
        1. If battery < 20%, always create charging task (even if pickup queue exists).
        2. If battery >= 20% and there is no pickup queue for this map, create charging task
           so the device moves to nearest idle charging zone.
        """
        try:
            device_id_str = self.device_data_handler._resolve_device_id_str(device_ref)
            if not device_id_str or not map_id:
                return

            # If device is already in charging state, do not create another charging task
            try:
                devices = self.csv_handler.read_csv('devices')
                device_row = next((d for d in devices if str(d.get('id')) == str(device_ref)), None)
                if device_row and str(device_row.get('status', '')).strip().lower() == 'charging':
                    self.logger.info(f"Device {device_id_str} is already in charging state; skipping auto charging task creation.")
                    return
            except Exception:
                # If we can't read device status, fall back to normal logic
                pass
            
            # Read battery status from device_id_Battery_status.csv
            battery_file = self.data_dir / 'device_logs' / f"{device_id_str}_Battery_status.csv"
            if not battery_file.exists():
                self.logger.warning(f"Battery file not found for {device_id_str}")
                return
            
            battery_percentage = None
            with open(battery_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if rows:
                    try:
                        battery_percentage = float(rows[-1].get('battery_percentage', 0))
                    except (ValueError, IndexError):
                        pass
            
            if battery_percentage is None:
                self.logger.warning(f"Could not read battery percentage for {device_id_str}")
                return

            # Check if there is any pending pickup task in the map-specific queue CSV
            has_pickup_queue = False
            pickup_file = self.data_dir / f"{map_id}_create_pickup_task.csv"
            if pickup_file.exists():
                try:
                    with open(pickup_file, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if row.get('action') == 'create_task':
                                has_pickup_queue = True
                                break
                except Exception as e:
                    self.logger.error(f"Error reading pickup queue CSV {pickup_file}: {e}")

            if battery_percentage < 20:
                # Rule 2: low battery, create charging task regardless of queue
                self.logger.info(f"Device {device_id_str} battery is {battery_percentage}% - creating charging task (low battery)")
                self._create_charging_task_automation(device_id_str, map_id)
            elif not has_pickup_queue:
                # Rule 1: no pickup queue, send device to charging while keeping it generally available
                self.logger.info(f"Device {device_id_str} has no queued pickup tasks on map {map_id} - creating charging task")
                self._create_charging_task_automation(device_id_str, map_id)
        except Exception as e:
            self.logger.error(f"Error checking battery for device {device_ref}: {e}")

    def _create_charging_task_automation(self, device_id: str, map_id: str):
        """Append entry to map-specific create_charging_task CSV for automatic charging task creation."""
        try:
            # Get device's current location to determine charging zone and end zone
            devices = self.csv_handler.read_csv('devices')
            device = next((d for d in devices if str(d.get('device_id')) == str(device_id)), None)
            if not device:
                self.logger.warning(f"Device {device_id} not found")
                return
            
            # Get charging zones for this map
            charging_zones = self.csv_handler.read_csv('charging_zones')
            map_charging_zones = [cz for cz in charging_zones if str(cz.get('map_id')) == str(map_id)]
            if not map_charging_zones:
                self.logger.warning(f"No charging zones found for map {map_id}")
                return
            
            # Select first available charging zone
            charging_zone = None
            for cz in map_charging_zones:
                if str(cz.get('occupied', '')).lower() == 'no':
                    charging_zone = str(cz.get('zone'))
                    break
            
            if not charging_zone:
                charging_zone = str(map_charging_zones[0].get('zone'))

            # Create or migrate and append to map-specific create_charging_task CSV
            charging_file = self.data_dir / f"{map_id}_create_charging_task.csv"
            file_exists = charging_file.exists()

            # If file exists but is in the old 2-column format, migrate it to include device_id
            if file_exists:
                try:
                    with open(charging_file, 'r', encoding='utf-8') as f:
                        reader = csv.reader(f)
                        rows = list(reader)
                    if rows:
                        header = [h.strip() for h in rows[0]]
                        if 'device_id' not in header:
                            # Migrate to new header: device_id, charging_zone, action
                            data_rows = rows[1:]
                            with open(charging_file, 'w', newline='', encoding='utf-8') as f:
                                writer = csv.writer(f)
                                writer.writerow(['device_id', 'charging_zone', 'action'])
                                # Preserve existing entries with empty device_id
                                for r in data_rows:
                                    # Best-effort mapping based on original positions
                                    cz = r[0] if len(r) > 0 else ''
                                    act = r[1] if len(r) > 1 else ''
                                    writer.writerow(['', cz, act])
                            file_exists = True
                except Exception as e:
                    self.logger.error(f"Error migrating charging CSV {charging_file}: {e}")

            # Append new entry with device_id
            with open(charging_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if not file_exists or charging_file.stat().st_size == 0:
                    writer.writerow(['device_id', 'charging_zone', 'action'])
                writer.writerow([device_id, charging_zone, 'create_task'])
            
            self.logger.info(f"Created charging task automation entry: {charging_zone} for map {map_id}")
        except Exception as e:
            self.logger.error(f"Error creating charging task automation: {e}")

    def _process_charging_csv(self, file_path: str):
        """Process charging_task_automation CSV files."""
        file_path_obj = Path(file_path)
        filename = file_path_obj.name
        try:
            map_id = filename.split('_')[0]
        except Exception:
            self.logger.warning(f"Could not extract map_id from filename: {filename}")
            return

        rows = []
        reserved_this_cycle = set()
        updated = False
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if row.get('action') == 'create_task':
                    success = self._handle_create_charging_task(map_id, row, reserved_this_cycle)
                    if success:
                        row['action'] = 'task_created'
                        updated = True
                rows.append(row)

        if updated:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            self.logger.info(f"Updated {filename} with task_created status.")

    def _handle_create_charging_task(self, map_id: str, row: Dict, reserved_this_cycle: set) -> bool:
        """Handle creation of charging task from automation CSV."""
        charging_zone = row.get('charging_zone')
        if not charging_zone:
            self.logger.warning(f"Incomplete charging data: charging_zone={charging_zone}")
            return False

        # Prefer explicit device_id from CSV so the same device that requested charging goes there
        device_identifier = (row.get('device_id') or '').strip()
        selected_device: Optional[Dict] = None

        if device_identifier:
            all_devices = self.csv_handler.read_csv('devices')
            selected_device = next(
                (d for d in all_devices if str(d.get('device_id')) == device_identifier),
                None
            )
            if not selected_device:
                self.logger.warning(f"Device with device_id={device_identifier} not found for charging on map {map_id}")
                return False
        else:
            # Fallback: find device that needs charging (battery < 20) and is not busy
            eligible_devices = self._get_eligible_devices_for_charging(map_id, excluded_device_ids=reserved_this_cycle)
            if not eligible_devices:
                self.logger.info(f"No eligible devices found for charging on map {map_id}")
                return False

            # Select device with lowest battery
            selected_device = min(eligible_devices, key=lambda d: float(d.get('battery_level', 100)))
        
        # Check if device already has a charging task
        tasks = self.csv_handler.read_csv('tasks')
        device_tasks = [t for t in tasks if str(t.get('assigned_device_id')) == str(selected_device['id']) and str(t.get('status')).lower() in ['pending', 'running']]
        if device_tasks:
            self.logger.info(f"Device {selected_device['device_id']} already has active task")
            return False

        # Create charging task
        task_data = self._build_charging_task_data(map_id, selected_device, charging_zone)
        if self.csv_handler.append_to_csv('tasks', task_data):
            self.logger.info(f"Automatically created charging task {task_data['task_id']} for device {selected_device['device_id']}")
            reserved_this_cycle.add(str(selected_device['id']))
            
            # Generate path
            try:
                from services.path_planner_service import plan_and_write_path
                # Get device's current location
                current_zone = str(selected_device.get('current_location', '1'))
                # Build zone sequence: current -> charging_zone
                zone_sequence = []
                if current_zone != charging_zone:
                    zone_sequence.append((current_zone, charging_zone))
                
                plan_and_write_path(
                    device_id=selected_device['device_id'],
                    map_id=map_id,
                    zone_sequence=zone_sequence,
                    initial_direction='north',
                    task_type='charging',
                    drop_zone=charging_zone  # End at charging zone
                )
                
                device_id_str = self.device_data_handler._resolve_device_id_str(selected_device['id'])
                if device_id_str:
                    self.device_data_handler.append_task_to_device(device_id_str, task_data['task_id'], 'pending_task')
                
                QTimer.singleShot(7000, lambda: self._trigger_automatic_execution(selected_device['id'], task_data['task_id']))
                return True
            except Exception as e:
                self.logger.error(f"Failed to generate charging path: {e}")
                return True
        
        return False

    def _get_eligible_devices_for_charging(self, map_id: str, excluded_device_ids: set = None) -> List[Dict]:
        """Get devices eligible for charging (battery < 20, not busy)."""
        all_devices = self.csv_handler.read_csv('devices')
        tasks = self.csv_handler.read_csv('tasks')
        
        if excluded_device_ids is None:
            excluded_device_ids = set()

        unavailable_device_ids = set(excluded_device_ids)
        for t in tasks:
            status = t.get('status', '').lower()
            if status in ['running', 'pending']:
                did = t.get('assigned_device_id')
                if did: unavailable_device_ids.add(str(did))

        eligible = []
        for d in all_devices:
            if str(d.get('current_map')) != str(map_id):
                continue
            if str(d.get('id')) in unavailable_device_ids:
                continue
            
            # Check battery from Battery_status.csv
            device_id = str(d.get('device_id', ''))
            battery_file = self.data_dir / 'device_logs' / f"{device_id}_Battery_status.csv"
            battery_percentage = 100
            if battery_file.exists():
                try:
                    with open(battery_file, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        rows = list(reader)
                        if rows:
                            battery_percentage = float(rows[-1].get('battery_percentage', 100))
                except Exception:
                    pass
            
            if battery_percentage < 20:
                eligible.append(d)
        
        return eligible

    def _build_charging_task_data(self, map_id: str, device: Dict, charging_zone: str) -> Dict:
        task_id = f"TASK{self.csv_handler.get_next_id('tasks'):04d}"
        current_time = datetime.now().isoformat()
        
        details = {
            'charging_map_id': str(map_id),
            'charging_station': str(charging_zone),
            'automatic': True
        }

        return {
            'id': '',
            'task_id': task_id,
            'task_name': f"Auto Charging - {device['device_id']}",
            'task_type': 'charging',
            'status': 'pending',
            'assigned_device_id': str(device['id']),
            'assigned_device_ids': str(device['id']),
            'assigned_user_id': '',
            'description': f"Automatically created charging task to {charging_zone}",
            'estimated_duration': '',
            'actual_duration': '',
            'created_at': current_time,
            'started_at': '',
            'completed_at': '',
            'map_id': str(map_id),
            'zone_ids': str(charging_zone),
            'stop_ids': '',
            'task_details': json.dumps(details)
        }
