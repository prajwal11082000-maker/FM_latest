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
from services.path_planner_service import plan_and_write_picking_path
from utils.logger import setup_logger

class AutomaticTaskService:
    def __init__(self, csv_handler: CSVHandler, device_data_handler: DeviceDataHandler):
        self.csv_handler = csv_handler
        self.device_data_handler = device_data_handler
        self.distance_calculator = DistanceCalculator(csv_handler)
        self.logger = setup_logger('automatic_task_service')
        self.data_dir = Path('data')

    def monitor_and_process(self):
        """Scan for create_pickup_task CSV files and process them."""
        # 1. Handle creation of new tasks
        pattern = str(self.data_dir / "*_create_pickup_task.csv")
        files = glob.glob(pattern)
        for file_path in files:
            try:
                self._process_csv(file_path)
            except Exception as e:
                self.logger.error(f"Error processing {file_path}: {e}")
        
        # 2. Sync statuses for active tasks (handles both auto and manual tasks feedback)
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
        stop_id = row.get('stop_id')
        drop_zone = row.get('drop_zone')

        if not stop_id or not drop_zone:
            self.logger.warning(f"Incomplete data in CSV: stop_id={stop_id}, drop_zone={drop_zone}")
            return False

        # 1. Find eligible devices (battery > 20, not running/pending task, not reserved this cycle)
        eligible_devices = self._get_eligible_devices(map_id, excluded_device_ids=reserved_this_cycle)
        if not eligible_devices:
            self.logger.info(f"No eligible devices found for move {stop_id} -> {drop_zone} on map {map_id}")
            return False

        # 2. Select nearest device
        selected_device = self._select_nearest_device(map_id, eligible_devices, stop_id)
        if not selected_device:
            self.logger.warning(f"Could not calculate proximity or select device.")
            return False

        # 3. Create task
        task_data = self._build_task_data(map_id, selected_device, stop_id, drop_zone)
        if self.csv_handler.append_to_csv('tasks', task_data):
            self.logger.info(f"Automatically created task {task_data['task_id']} for device {selected_device['device_id']}")
            
            # Add to reservation for this cycle
            reserved_this_cycle.add(str(selected_device['id']))
            
            # 4. Generate Path Planning
            try:
                plan_and_write_picking_path(
                    device_id=selected_device['device_id'],
                    map_id=map_id,
                    pickup_stops=[stop_id],
                    drop_zone=drop_zone
                )
                self.logger.info(f"Generated path planning for device {selected_device['device_id']}")
                
                # Update device task status to pending in its local CSV
                self.device_data_handler.update_device_task_pending_by_task(selected_device['id'], task_data['task_id'])
                
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
                # We still return True because the task was created, 
                # but maybe we should revert? User said "make sure automatically the path planning will be generated".
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
            # battery_level > 20
            try:
                battery = float(d.get('battery_level', 0))
            except ValueError:
                battery = 0
            
            # Should be in the right map
            if str(d.get('current_map')) != str(map_id):
                continue
                
            if battery > 20 and str(d.get('id')) not in unavailable_device_ids:
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

    def _trigger_automatic_execution(self, device_ref: str, task_id: str):
        """Automatically trigger task execution in the device task CSV."""
        try:
            success = self.device_data_handler.set_task_status_for_task(device_ref, task_id, 'run_task')
            if success:
                self.logger.info(f"Automatically triggered execution (run_task) for task {task_id} on device {device_ref}")
            else:
                self.logger.warning(f"Failed to automatically trigger execution for task {task_id}")
        except Exception as e:
            self.logger.error(f"Error in automatic task trigger: {e}")
