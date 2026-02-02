"""
Smart Device Filtering Module

Filters devices based on battery level, status, distance requirements, and position.
Includes stop distance calculations.
"""
from typing import Dict, List, Optional, Tuple
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QListWidgetItem

from data_manager.csv_handler import CSVHandler
from utils.logger import setup_logger
from .battery_mapper import BatteryMapper
from .distance_calculator import DistanceCalculator


class DeviceFilter:
    """Filters and ranks devices based on task requirements"""
    
    def __init__(self, csv_handler: CSVHandler, distance_calculator: DistanceCalculator):
        self.csv_handler = csv_handler
        self.distance_calculator = distance_calculator
        self.battery_mapper = BatteryMapper()
        self.logger = setup_logger('device_filter')
    
    def filter_devices(self, task_type: str, map_id: Optional[str] = None,
                      from_zone: Optional[str] = None, to_zone: Optional[str] = None,
                      required_distance: Optional[float] = None,
                      selected_stops: Optional[List[str]] = None) -> List[Dict]:
        """
        Filter devices based on task requirements.
        
        Args:
            task_type: 'picking', 'storing', or 'auditing'
            map_id: Map identifier for distance calculations
            from_zone: Starting zone (for picking/storing)
            to_zone: Destination zone (for picking/storing)
            required_distance: Pre-calculated required distance (if available)
            selected_stops: List of selected stop IDs (for picking/storing)
            
        Returns:
            List of filtered device dictionaries with selectability info
        """
        try:
            devices = self.csv_handler.read_csv('devices')
            
            # Calculate required distance if not provided
            if required_distance is None and map_id:
                required_distance = self.distance_calculator.get_required_distance_for_task(
                    task_type, map_id, from_zone, to_zone, selected_stops
                )
            
            candidates = []
            seen_ids = set()
            
            # Pre-read tasks for busy check
            tasks = self.csv_handler.read_csv('tasks') if task_type == 'charging' else []
            running_tasks = [t for t in tasks if t.get('status', '').lower() == 'running']
            
            for device in devices:
                device_id = device.get('id')
                if not device_id or str(device_id) in seen_ids:
                    continue
                seen_ids.add(str(device_id))
                
                # Parse device properties
                battery = self.battery_mapper.parse_battery(device.get('battery_level', '0'))
                status = (device.get('status', '') or '').strip().lower()
                current_location = device.get('current_location', '')
                device_map = str(device.get('current_map', ''))

                # Strict Map Filtering
                if map_id and device_map != str(map_id):
                    continue
                
                # Check basic selectability
                if task_type == 'charging':
                    # Special eligibility for charging: battery < 20% and not currently charging
                    # Also must not be running a task
                    battery_eligible = battery < 20
                    status_eligible = status != 'charging'
                    
                    # Check if device is already running a task
                    device_id_str = str(device.get('id'))
                    is_busy = False
                    for t in running_tasks:
                        sid = str(t.get('assigned_device_id') or '').strip()
                        mids = [s.strip() for s in str(t.get('assigned_device_ids') or '').split(',') if s.strip()]
                        if sid == device_id_str or device_id_str in mids:
                            is_busy = True
                            break
                    
                    basic_selectable = battery_eligible and status_eligible and not is_busy
                else:
                    # Original logic for other tasks: battery > 20% and status working/charging
                    basic_selectable = battery > 20 and status in ['working', 'charging']
                
                # Check distance requirements
                distance_selectable = True
                distance_info = ""
                position_info = ""
                
                if required_distance and required_distance > 0:
                    # Get device's maximum travel distance based on battery
                    max_travel_distance = self.battery_mapper.get_max_travel_distance(battery)
                    
                    # Calculate distance from device location to map/start point
                    device_to_start = 0.0
                    if map_id and current_location:
                        device_to_start = self.distance_calculator.calculate_device_to_map_distance(
                            current_location, map_id
                        )
                    
                    # Total distance needed (travel to start + task distance)
                    total_distance_needed = required_distance + device_to_start
                    
                    # Check if device can handle the distance
                    if max_travel_distance < total_distance_needed:
                        distance_selectable = False
                        distance_info = f" (Range: {int(max_travel_distance)}mm < Required: {int(total_distance_needed)}mm)"
                    
                    # Position check: verify device can reach the starting point
                    if device_to_start > max_travel_distance:
                        distance_selectable = False
                        position_info = f" (Cannot reach start: {int(device_to_start)}mm > {int(max_travel_distance)}mm)"
                
                # Position validation (device must be in a valid location)
                position_valid = self._validate_device_position(device, map_id, task_type, from_zone)
                
                # Final selectability
                selectable = (basic_selectable and 
                             distance_selectable and 
                             position_valid)
                
                candidates.append({
                    'device': device,
                    'battery': battery,
                    'selectable': selectable,
                    'is_busy': is_busy if task_type == 'charging' else False,
                    'status': status,
                    'distance_info': distance_info,
                    'position_info': position_info,
                    'current_location': current_location,
                    'max_range': self.battery_mapper.get_max_travel_distance(battery),
                    'required_distance': total_distance_needed if required_distance else 0.0
                })
            
            # Sort by battery descending, then by selectability
            candidates.sort(key=lambda x: (
                0 if x['selectable'] else 1,  # Selectable first
                -x['battery']  # Higher battery first
            ))
            
            return candidates
            
        except Exception as e:
            self.logger.error(f"Error filtering devices: {e}")
            return []
    
    def _validate_device_position(self, device: Dict, map_id: Optional[str], 
                                  task_type: str, from_zone: Optional[str]) -> bool:
        """
        Validate device position for task execution.
        
        Args:
            device: Device dictionary
            map_id: Target map ID
            task_type: Task type
            from_zone: Starting zone (if applicable)
            
        Returns:
            True if device position is valid for the task
        """
        current_location = device.get('current_location', '')
        
        # Basic check: device must have a location
        if not current_location or str(current_location).strip() == '':
            return False
        
        # For picking/storing tasks, device should ideally be at or near the starting zone
        if task_type in ['picking', 'storing'] and from_zone:
            return True
        
        # For auditing, device can start from anywhere in the map
        if task_type == 'auditing':
            return True
        
        return True
    
    def create_device_list_items(self, candidates: List[Dict], task_type: str) -> List[QListWidgetItem]:
        """
        Create QListWidgetItem objects for device list display.
        
        Args:
            candidates: List of filtered device dictionaries
            
        Returns:
            List of QListWidgetItem objects
        """
        items = []
        
        for candidate in candidates:
            device = candidate['device']
            battery = candidate['battery']
            selectable = candidate['selectable']
            status = candidate['status']
            distance_info = candidate['distance_info']
            position_info = candidate['position_info']
            
            device_name = device.get('device_name', '')
            device_id = device.get('device_id', '')
            device_text = f"{device_name} ({device_id})"
            
            # Build display text with status and battery info
            if selectable:
                if status == 'charging':
                    device_text += f" - {battery}% 🔋"
                else:
                    device_text += f" - {battery}% ⚡"
                icon = "✅"
            else:
                # Add reason for exclusion
                if battery <= 20:
                    if status == 'charging':
                        device_text += f" - {battery}% 🪫 (Low Battery - Charging)"
                    else:
                        device_text += f" - {battery}% 🪫 (Low Battery)"
                elif distance_info:
                    # Distance constraint failed
                    if status == 'charging':
                        device_text += f" - {battery}% 🔋{distance_info}"
                    else:
                        device_text += f" - {battery}% ⚡{distance_info}"
                elif position_info:
                    # Position constraint failed
                    device_text += f" - {battery}% {position_info}"
                elif status in ['issues', 'maintenance']:
                    device_text += f" - {battery}% ({status.title()})"
                elif task_type == 'charging':
                    is_busy = candidate.get('is_busy', False) # Check if we have this info
                    if battery >= 20:
                        device_text += f" - {battery}% (Battery >= 20%)"
                    elif status == 'charging':
                        device_text += f" - {battery}% (Already Charging)"
                    elif is_busy:
                        device_text += f" - {battery}% (Busy)"
                    else:
                        device_text += f" - {battery}% ({status.title()})"
                else:
                    device_text += f" - {battery}% ({status.title()})"
                icon = "❌"
            
            # Create list item
            item = QListWidgetItem(f"{icon} {device_text}")
            item.setData(Qt.UserRole, device.get('id'))
            
            # Disable non-selectable items
            if not selectable:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                tooltip = "Device unavailable: "
                if task_type == 'charging':
                    if battery >= 20:
                        tooltip += "Battery level >= 20%"
                    elif status == 'charging':
                        tooltip += "Device is already charging"
                    else:
                        tooltip += "Device is busy or unavailable"
                elif battery <= 20:
                    tooltip += "Low battery"
                elif distance_info:
                    tooltip += "Insufficient range for task"
                elif position_info:
                    tooltip += "Cannot reach starting point"
                else:
                    tooltip += status.title()
                item.setToolTip(tooltip)
            
            items.append(item)
        
        return items