from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QFrame, QScrollArea, QSlider, QCheckBox)
from PyQt5.QtCore import Qt, pyqtSignal, QPointF, QRectF, QTimer
from PyQt5.QtGui import (QPainter, QPen, QBrush, QColor, QFont,
                         QPixmap, QMouseEvent, QWheelEvent, QPolygonF)

from api.client import APIClient
from data_manager.csv_handler import CSVHandler
from utils.logger import setup_logger
from .robot_sprite import RobotSprite
import math
from data_manager.device_data_handler import DeviceDataHandler


class MapCanvas(QWidget):
    """Interactive map canvas for displaying zones, stops, and connections"""

    stop_clicked = pyqtSignal(dict)
    zone_clicked = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setMinimumSize(800, 600)
        self.setMouseTracking(True)
        self.setVisible(True)  # Explicitly set visibility for map canvas
        self.setAttribute(Qt.WA_StyledBackground, True)  # Enable background styling

        # Map data
        self.map_width = int(1000)  # Ensure integer type
        self.map_height = int(800)  # Ensure integer type
        self.zones = []
        self.stops = []
        self.stop_groups = []
        self.racks = []

        
        # Robot representation (single and multi)
        self.robot = None  # legacy single-robot path
        self.robot_active = False
        self.robots = {}   # device_id -> RobotSprite
        
        # Map background image
        self.map_image = None

        # Visual settings
        self.show_zones = True
        self.show_connections = True
        self.show_stops = True
        self.show_labels = True
        self.show_grid = True

        # Interaction state
        self.selected_stop = None
        self.hover_stop = None
        self.selected_zone = None

        # Zoom and pan
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0
        self.pan_offset = QPointF(0, 0)
        self.last_pan_point = QPointF()
        self.is_panning = False

        # Map scale settings
        self.meter_in_pixels = 150  # Default 150 pixels per meter

        # Colors
        self.colors = {
            'background': QColor('#2b2b2b'),
            'grid': QColor('#404040'),
            'zone_storage': QColor('#3B82F6'),
            'zone_picking': QColor('#10B981'),
            'zone_packing': QColor('#F59E0B'),
            'zone_shipping': QColor('#8B5CF6'),
            'zone_default': QColor('#6B7280'),
            'connection': QColor('#10B981'),
            'stop_normal': QColor('#F59E0B'),
            'stop_selected': QColor('#EF4444'),
            'stop_hover': QColor('#ffffff'),
            'text': QColor('#ffffff'),
            'text_secondary': QColor('#cccccc'),
            'rack_color': QColor('#8B5CF6'),  # Distinct purple for racks
            'rack_border': QColor('#ffffff')
        }

        self.setStyleSheet("background-color: #2b2b2b; border: 1px solid #555555;")

    def set_map_data(self, zones, stops, stop_groups, map_width=1000, map_height=800, map_data=None, task_status=None, task_details=None, racks=None):

        """Set map data for display"""

        
        # Initialize state
        self.robot = None
        self.robot_active = False
        self.zones = []
        self.stops = []
        self.stop_groups = stop_groups or []
        self.racks = racks or []
        self.robots = {}   # Clear multi-robot sprites on map change

        # Process task details
        task_type = task_details.get('type', '').lower() if task_details else ''
        task_desc = task_details.get('details', '').lower() if task_details else ''

        # Extract start zone based on task type and details
        task_from_zone = None
        
        if task_type == 'picking':
            # For picking tasks, start at drop zone
            if 'drop zone:' in task_desc:
                task_from_zone = task_desc.split('drop zone:')[1].split('|')[0].strip()

        elif task_type == 'storing':
            # For storing tasks, start at pickup zone
            if 'pickup map:' in task_desc:
                task_from_zone = task_desc.split('pickup map:')[1].split('|')[0].strip()
        elif task_type == 'auditing':
            # For auditing tasks, start at specified zone
            if 'zone:' in task_desc:
                task_from_zone = task_desc.split('zone:')[1].split('|')[0].strip()
        else:
            # Default case - try to extract zone from arrow notation
            if '→' in task_desc:
                task_from_zone = task_desc.split('→')[0].split(':')[-1].strip()
            elif ':' in task_desc:
                task_from_zone = task_desc.split(':')[-1].strip().split()[0]
        
        # Process zones
        if isinstance(zones, list):
            for zone in zones:
                zone_data = zone.copy() if isinstance(zone, dict) else {'from_zone': str(zone)}
                if task_from_zone:
                    zone_data['task_zone'] = True
                    if zone_data.get('from_zone', '').lower() == task_from_zone.lower():
                        zone_data['task_start_zone'] = True
                self.zones.append(zone_data)
        
        # Process stops
        if isinstance(stops, list):
            self.stops = [stop if isinstance(stop, dict) else {'stop_id': str(stop)} for stop in stops]
        
        # Process dimensions
        try:
            w = map_width[0] if isinstance(map_width, (list, tuple)) else map_width
            h = map_height[0] if isinstance(map_height, (list, tuple)) else map_height
            self.map_width = int(float(w)) if w else 1000
            self.map_height = int(float(h)) if h else 800
        except (TypeError, ValueError, IndexError):
            self.map_width = 1000
            self.map_height = 800

        # Set pixel ratio from map data
        if map_data and 'meter_in_pixels' in map_data:
            try:
                self.meter_in_pixels = float(map_data['meter_in_pixels'])
            except (ValueError, TypeError):
                self.meter_in_pixels = 150
        else:
            self.meter_in_pixels = 150

        # Debug output

        
        # Generate coordinates
        self.generate_zone_positions()
        self.generate_stop_positions()

        # Handle robot setup (legacy single robot); multi-robot can be set via set_active_devices
        if task_status == 'running' and self.zones and not self.robots:
            starting_zone = self.get_task_start_zone(task_details)
            if starting_zone:
                try:
                    start_x = float(starting_zone.get('from_x', 0))
                    start_y = float(starting_zone.get('from_y', 0))
                    zone_direction = starting_zone.get('direction', 'north')
                    self.robot = RobotSprite(QPointF(start_x, start_y), direction=zone_direction)
                    self.robot.starting_zone = starting_zone.get('from_zone', '')
                    self.robot.starting_coordinates = QPointF(start_x, start_y)
                    self.robot_active = True
                    self.fit_to_view()
                except (ValueError, TypeError) as e:
                    print(f"DEBUG - Error creating robot: {e}")
            else:
                print("DEBUG - No valid starting zone found")
        else:
            print("DEBUG - Task not running, no zones, or multi-robot active")
        
        self.update()

    def generate_zone_positions(self):
        """Generate positions for zones based on their specified directions"""

        if not self.zones:
            print("DEBUG - No zones to position")
            return

        # Create a mapping of unique zone names to positions
        unique_zones = set()
        for zone in self.zones:
            from_zone = zone.get('from_zone', '')
            to_zone = zone.get('to_zone', '')
            unique_zones.add(from_zone)
            unique_zones.add(to_zone)


        unique_zones = list(unique_zones)
        zone_positions = {}

        # Use directional positioning instead of simple grid
        self.position_zones_by_direction(unique_zones, zone_positions)

        # Store positions in zone data
        for zone in self.zones:
            from_zone = zone.get('from_zone', '')
            to_zone = zone.get('to_zone', '')

            if from_zone in zone_positions:
                zone['from_x'] = zone_positions[from_zone]['x']
                zone['from_y'] = zone_positions[from_zone]['y']
                zone['from_width'] = zone_positions[from_zone]['width']
                zone['from_height'] = zone_positions[from_zone]['height']

            if to_zone in zone_positions:
                zone['to_x'] = zone_positions[to_zone]['x']
                zone['to_y'] = zone_positions[to_zone]['y']
                zone['to_width'] = zone_positions[to_zone]['width']
                zone['to_height'] = zone_positions[to_zone]['height']

    def position_zones_by_direction(self, unique_zones, zone_positions):
        """Position zones based on directional relationships with FIXED CENTER reference point"""
        if not unique_zones:
            return

        # FIXED CENTER COORDINATES - This is the permanent reference point
        center_x = self.map_width / 2
        center_y = self.map_height / 2
        
        # Zone size - configurable for any map scale
        base_size = min(self.map_width, self.map_height) / 25  # Dynamic sizing based on map dimensions
        zone_size = {'width': base_size, 'height': base_size}
        
        # If only one zone, place it at center
        if len(unique_zones) == 1:
            zone_positions[unique_zones[0]] = {
                'x': center_x,
                'y': center_y,
                **zone_size
            }
            return
        
        # Build zone relationship graph from connections
        placed_zones = set()
        zone_connections = {}
        
        # Create connection map with directions
        for zone in self.zones:
            from_zone = zone.get('from_zone', '')
            to_zone = zone.get('to_zone', '')
            # Get actual direction from zone data, don't default to anything
            direction = zone.get('direction', '').lower() 
            magnitude = float(zone.get('magnitude', min(self.map_width, self.map_height) / 10))  # Dynamic default based on map size
            
            if from_zone and to_zone:
                if from_zone not in zone_connections:
                    zone_connections[from_zone] = []
                zone_connections[from_zone].append({
                    'to': to_zone,
                    'direction': direction,
                    'distance': magnitude
                })
        
        # ALWAYS use the FIRST zone chronologically as the center reference point
        # This ensures consistency - the first zone created stays at center forever
        first_zone_created = self.get_first_zone_chronologically()
        
        if first_zone_created and first_zone_created in unique_zones:
            start_zone = first_zone_created
        else:
            # Fallback: Find zone with outgoing connections
            start_zone = None
            for zone_name in unique_zones:
                if zone_name in zone_connections:
                    start_zone = zone_name
                    break
            
            # Final fallback
            if start_zone is None:
                start_zone = unique_zones[0]
        
        # PERMANENTLY PLACE the reference zone at center - this NEVER moves
        zone_positions[start_zone] = {
            'x': center_x,
            'y': center_y,
            **zone_size
        }
        placed_zones.add(start_zone)
        
        # Direction vectors for positioning - CORRECT MAPPING
        # south=down, north=up, east=right, west=left
        direction_vectors = {
            'north': (0, -1),   # UP
            'south': (0, 1),    # DOWN
            'east': (1, 0),     # RIGHT
            'west': (-1, 0),    # LEFT
            'northeast': (0.707, -0.707),
            'northwest': (-0.707, -0.707),
            'southeast': (0.707, 0.707),
            'southwest': (-0.707, 0.707)
        }
        
        # Queue for processing connections
        process_queue = [start_zone]
        
        # For the first connection, immediately place the target zone to establish proper directionality
        if start_zone in zone_connections and zone_connections[start_zone]:
            first_connection = zone_connections[start_zone][0]
            target_zone = first_connection['to']
            direction = first_connection['direction']
            distance = min(first_connection['distance'] * self.meter_in_pixels, 7500)
            
            # Get direction vector for first connection
            dx, dy = direction_vectors.get(direction, (1, 0))
            
            # Calculate position for target zone
            new_x = center_x + dx * distance
            new_y = center_y + dy * distance
            
            # Keep within bounds
            padding = 100
            new_x = max(padding, min(self.map_width - padding, new_x))
            new_y = max(padding, min(self.map_height - padding, new_y))
            
            # Place the target zone
            zone_positions[target_zone] = {
                'x': new_x,
                'y': new_y,
                **zone_size
            }
            placed_zones.add(target_zone)
            process_queue.append(target_zone)
        
        while process_queue and len(placed_zones) < len(unique_zones):
            current_zone = process_queue.pop(0)
            
            if current_zone not in zone_connections:
                continue
                
            current_pos = zone_positions[current_zone]
            
            # Process all connections from this zone
            for connection in zone_connections[current_zone]:
                target_zone = connection['to']
                
                if target_zone in placed_zones:
                    continue
                
                direction = connection['direction']
                distance = min(connection['distance'] * self.meter_in_pixels, 7500)  # Scale and cap distance
                
                # Get direction vector
                dx, dy = direction_vectors.get(direction, (1, 0))
                
                # Calculate new position
                new_x = current_pos['x'] + dx * distance
                new_y = current_pos['y'] + dy * distance
                
                # Keep within map bounds with padding
                padding = 100
                new_x = max(padding, min(self.map_width - padding, new_x))
                new_y = max(padding, min(self.map_height - padding, new_y))
                
                # Check for overlaps with existing zones
                new_x, new_y = self.avoid_zone_overlaps(new_x, new_y, zone_positions, zone_size)
                
                # Place the zone
                zone_positions[target_zone] = {
                    'x': new_x,
                    'y': new_y,
                    **zone_size
                }
                
                placed_zones.add(target_zone)
                process_queue.append(target_zone)
        
        # Place any remaining unconnected zones in a fallback grid
        unplaced_zones = [z for z in unique_zones if z not in placed_zones]
        if unplaced_zones:
            self.place_remaining_zones_in_grid(unplaced_zones, zone_positions, zone_size)
    
    def avoid_zone_overlaps(self, x, y, existing_positions, zone_size):
        """Adjust position to avoid overlapping with existing zones"""
        min_distance = 120  # Minimum distance between zone centers
        
        for existing_zone, pos in existing_positions.items():
            dx = x - pos['x']
            dy = y - pos['y']
            distance = math.sqrt(dx * dx + dy * dy)
            
            if distance < min_distance:
                # Push away from existing zone
                if distance > 0:
                    # Normalize and extend
                    factor = min_distance / distance
                    x = pos['x'] + dx * factor
                    y = pos['y'] + dy * factor
                else:
                    # If exactly overlapping, offset by min distance
                    x += min_distance
        
        return x, y
    
    def get_task_start_zone(self, task_details):
        """Extract and find the starting zone from task details based on task type"""
        if not task_details:
            return None
            
        task_desc = str(task_details.get('details', '')).lower()
        task_type = str(task_details.get('type', '')).lower()
        task_from_zone = None
        

        
        if task_type == 'picking':
            # For picking tasks, start at the drop zone
            if 'drop zone:' in task_desc:
                zone_part = task_desc.split('drop zone:')[1].split('→')[0].strip()
                task_from_zone = zone_part
        elif task_type == 'storing':
            # For storing tasks, start at the pickup zone
            if 'pickup map:' in task_desc:
                pickup_details = task_desc.split('pickup map:')[1].strip()
                if '→' in pickup_details:
                    parts = pickup_details.split('→')
                    if len(parts) > 0:
                        task_from_zone = parts[0].strip()
                elif len(pickup_details) >= 2:
                    task_from_zone = pickup_details[1]  # Get second character as it's the pickup zone
        elif task_type == 'auditing':
            # For auditing tasks, start at the specified zone
            if 'zone:' in task_desc:
                task_from_zone = task_desc.split('zone:')[1].split()[0].strip()
            elif '→' in task_desc:
                # If format is "zone a → b", take the first zone
                task_from_zone = task_desc.split('→')[0].strip().split()[-1]

        else:
            # Default case - try to find any valid starting zone
            if 'drop zone:' in task_desc and '→' in task_desc:
                zone_part = task_desc.split('drop zone:')[1].split('→')[0].strip()
                task_from_zone = zone_part
            elif 'pickup map:' in task_desc:
                pickup_details = task_desc.split('pickup map:')[1].strip()
                if '→' in pickup_details:
                    parts = pickup_details.split('→')
                    if len(parts) > 0:
                        task_from_zone = parts[0].strip()
                elif len(pickup_details) >= 2:
                    task_from_zone = pickup_details[1]
                
        # Find the matching zone object
        if task_from_zone:
            for zone in self.zones:
                if zone.get('from_zone', '').lower() == task_from_zone.lower():
                    return zone
                    
        # Try to find a zone with task_start_zone flag
        for zone in self.zones:
            if zone.get('task_start_zone', False):
                print(f"DEBUG - Found zone with task_start_zone flag: {zone.get('from_zone')}")
                return zone
        
        # Try to find any zone with task_zone flag
        for zone in self.zones:
            if zone.get('task_zone', False):
                print(f"DEBUG - Found zone with task_zone flag: {zone.get('from_zone')}")
                return zone
                
        # Last resort: use first zone with valid coordinates
        for zone in self.zones:
            if zone.get('from_x') is not None:
                print(f"DEBUG - Using first valid zone as fallback: {zone.get('from_zone')}")
                return zone
                    
        return None
    
    def calculate_turn_direction(self, turn_type: str) -> str:
        """
        Calculate the new direction after a turn based on robot's current direction.
        
        Args:
            turn_type: 'left' or 'right'
            
        Returns:
            New direction ('north', 'south', 'east', 'west')
        """
        # Get current robot direction
        current_dir = 'north'  # Default fallback
        if self.robot and hasattr(self.robot, 'direction'):
            current_dir = self.robot.direction
        
        
        # Direction mapping for turns
        turn_map = {
            'north': {'left': 'west', 'right': 'east'},
            'south': {'left': 'east', 'right': 'west'},
            'east': {'left': 'north', 'right': 'south'},
            'west': {'left': 'south', 'right': 'north'}
        }
        
        new_direction = turn_map.get(current_dir, {}).get(turn_type, 'north')
        
        return new_direction
    
    def calculate_robot_position_from_csv_data(self, device_id: str, zones: list) -> QPointF:
        """
        Calculate robot position based on CSV data from device logs.
        
        Args:
            device_id: Device identifier to get CSV data for
            zones: List of zone data to find the current zone
            
        Returns:
            QPointF with calculated robot position or None if calculation fails
        """
        try:
            # Initialize device data handler
            import os
            device_logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'device_logs')
            device_handler = DeviceDataHandler(device_logs_dir)
            
            # Initialize and load zone navigation manager BEFORE any processing
            from utils.zone_navigation_manager import get_zone_navigation_manager
            zone_nav_manager = get_zone_navigation_manager()
            # Load zone connections from current zones data (required for target zone resolution)
            zone_nav_manager.load_zone_connections_from_csv_data(zones)
            
            # Warm up navigation state by processing recent rows sequentially
            try:
                recent_rows = device_handler.get_recent_device_rows(device_id, count=50)
            except Exception:
                recent_rows = []

            if recent_rows and len(recent_rows) > 1:
                # Use current robot direction as initial orientation if available
                warmup_dir = None
                if self.robot and hasattr(self.robot, 'direction'):
                    warmup_dir = self.robot.direction
                # Process all but the last row (latest handled below)
                for idx, row in enumerate(recent_rows[:-1]):
                    try:
                        cz = str(row.get('current_location', ''))
                        rd = float(row.get('right_drive', 0))
                        ld = float(row.get('left_drive', 0))
                        rm = float(row.get('right_motor', 0))
                        lm = float(row.get('left_motor', 0))
                        _is_valid, mtype, _reason, _target = zone_nav_manager.process_movement_and_navigate(
                            device_id, cz, rd, ld, rm, lm, warmup_dir
                        )
                        # Sync warmup_dir with locked direction when a turn occurs (Left/Right/U-Turn)
                        if mtype in ["Turning Left", "Turning Right", "U-Turn"]:
                            nav_info = zone_nav_manager.get_navigation_info(device_id)
                            if nav_info.get('locked_direction') and nav_info.get('turn_type') in ['left', 'right']:
                                warmup_dir = nav_info['locked_direction']
                                if self.robot:
                                    self.robot.set_direction_for_turn_only(nav_info['locked_direction'], nav_info['turn_type'])
                            elif nav_info.get('locked_direction') and nav_info.get('turn_type') == 'u_turn':
                                warmup_dir = nav_info['locked_direction']
                                if self.robot:
                                    self.robot.force_lock_direction(nav_info['locked_direction'], 'u_turn')
                    except Exception as _e:
                        print(f"DEBUG - Warmup row processing error at idx {idx}: {_e}")

            # Get raw positioning data (latest row)
            positioning_data = device_handler.get_raw_device_positioning_data(device_id)
            if not positioning_data:
                print(f"DEBUG - No positioning data found for device {device_id}")
                return None
            
            current_zone_num = positioning_data['current_location_zone']
            right_drive = positioning_data['right_drive']  # in mm
            left_drive = positioning_data['left_drive']    # in mm
            
            # Get motor values for zone-based validation
            right_motor = positioning_data['right_motor']
            left_motor = positioning_data['left_motor']
            
            # Determine a reliable baseline direction for turn mapping
            robot_direction = None
            if self.robot and hasattr(self.robot, 'direction'):
                robot_direction = self.robot.direction

            # Prefer nav manager's current lock; else use last route's transition direction; else sprite direction
            nav_info_pre = zone_nav_manager.get_navigation_info(device_id)
            zinfo_pre = device_handler.get_zone_transition_info(device_id)
            current_dir_arg = (
                nav_info_pre.get('locked_direction')
                or (zinfo_pre.get('transition_direction') if isinstance(zinfo_pre, dict) else None)
                or robot_direction
            )

            # Convert zone number to zone name for navigation
            current_zone_name = str(current_zone_num)
            
            is_valid, movement_type, reason, target_zone = zone_nav_manager.process_movement_and_navigate(
                device_id, current_zone_name, right_drive, left_drive, right_motor, left_motor, current_dir_arg
            )
                
            if is_valid:
                
                # Map movement types to map directions (including zone-based movements)
                if movement_type == "Forward":
                    current_direction = 'forward'
                    is_turning = False
                elif movement_type == "Backward":
                    current_direction = 'backward'
                    is_turning = False
                elif movement_type == "Turning Right":
                    # Prefer nav manager's locked direction; fallback to computed right-turn from current sprite direction
                    nav_info = zone_nav_manager.get_navigation_info(device_id)
                    current_direction = nav_info.get('locked_direction')
                    if not current_direction:
                        current_direction = self.calculate_turn_direction('right')
                    is_turning = True
                elif movement_type == "Turning Left":
                    # Prefer nav manager's locked direction; fallback to computed left-turn from current sprite direction
                    nav_info = zone_nav_manager.get_navigation_info(device_id)
                    current_direction = nav_info.get('locked_direction')
                    if not current_direction:
                        current_direction = self.calculate_turn_direction('left')
                    is_turning = True
                elif movement_type == "U-Turn":
                    # U-turn flips orientation 180°; prefer nav manager's locked direction.
                    nav_info = zone_nav_manager.get_navigation_info(device_id)
                    desired_dir = nav_info.get('locked_direction')
                    if not desired_dir:
                        # Compute fallback: flip current robot direction 180°
                        u_map = {'north': 'south', 'south': 'north', 'east': 'west', 'west': 'east'}
                        base = (self.robot.direction if self.robot and hasattr(self.robot, 'direction') else 'north')
                        desired_dir = u_map.get(base, 'south')
                    current_direction = desired_dir
                    is_turning = True
                    if self.robot and current_direction:
                        self.robot.force_lock_direction(current_direction, 'u_turn')
                elif movement_type.startswith("Moving"):
                    # Zone-based movement (e.g., "Moving East", "Moving West")
                    direction_word = movement_type.split()[1].lower()  # Extract direction
                    current_direction = direction_word
                    is_turning = False
                else:  # Stationary
                    current_direction = 'stationary'
                    is_turning = False
            
            # Store device ID for zone direction lookup
            self._current_device_id = device_id
            
            # Find the zone CONNECTION that starts from the robot's current location
            zone_connection = self.find_zone_connection_from_current_location(current_zone_num, zones)
            if not zone_connection:
                # Fallback: keep previous direction and stay at current zone center
                # Attempt to find the zone's own coordinates
                zone_str = str(current_zone_num)
                zone_center_x = None
                zone_center_y = None
                for z in zones:
                    if str(z.get('from_zone', '')).lower() == zone_str.lower():
                        zone_center_x = z.get('from_x')
                        zone_center_y = z.get('from_y')
                        break
                    if str(z.get('to_zone', '')).lower() == zone_str.lower():
                        # Use 'to_' coords if this zone only appears as a target
                        zone_center_x = z.get('to_x')
                        zone_center_y = z.get('to_y')
                        # do not break to allow an exact 'from_zone' match to override, but practically fine
                if zone_center_x is not None and zone_center_y is not None:
                    if self.robot:
                        # Synchronize with nav manager's lock if present, to preserve last turn
                        nav_info = zone_nav_manager.get_navigation_info(device_id)
                        if nav_info.get('is_locked') and nav_info.get('locked_direction'):
                            desired_dir = nav_info['locked_direction']
                            desired_turn = nav_info.get('turn_type', 'inherited')
                            if (not self.robot.is_direction_locked) or (self.robot.locked_direction != desired_dir):
                                if desired_turn in ['left','right']:
                                    self.robot.set_direction_for_turn_only(desired_dir, desired_turn)
                                else:
                                    self.robot.force_lock_direction(desired_dir, 'inherited')
                                print(f"DEBUG - 🔒 NO-NEXT-ZONE SYNC: Setting sprite to locked direction {desired_dir} (turn_type={desired_turn})")
                        else:
                            # Do not change direction unless locked/turn; just log persistence
                            if not self.robot.is_direction_locked:
                                print(f"DEBUG - No next connection. Retaining previous direction: {self.robot.direction}")
                            else:
                                print(f"DEBUG - No next connection. Direction remains LOCKED: {self.robot.locked_direction}")
                    return QPointF(float(zone_center_x), float(zone_center_y))
                # If no coordinates available at all, return None as last resort
                return None
            
            # Get zone center coordinates (from the starting zone)
            zone_x = zone_connection.get('from_x', 0)
            zone_y = zone_connection.get('from_y', 0)
            

            
            # Handle movement based on validation results
            if current_direction == 'stationary':
                # Movement was rejected or robot is truly stationary - MAINTAIN direction
                if self.robot:
                    # If a prior turn was locked in the nav manager, make sure the sprite reflects it
                    nav_info = zone_nav_manager.get_navigation_info(device_id)
                    if nav_info.get('is_locked') and nav_info.get('locked_direction'):
                        desired_dir = nav_info['locked_direction']
                        desired_turn = nav_info.get('turn_type', 'inherited')
                        if (not self.robot.is_direction_locked) or (self.robot.locked_direction != desired_dir):
                            if desired_turn in ['left','right']:
                                self.robot.set_direction_for_turn_only(desired_dir, desired_turn)
                            else:
                                self.robot.force_lock_direction(desired_dir, 'inherited')
                    maintained_direction = self.robot.maintain_direction_across_zones()
                return QPointF(zone_x, zone_y)
            elif is_turning:
                # Valid turning movement detected - ONLY change direction for actual turns
                if self.robot:
                    # Get navigation info from zone navigation manager
                    nav_info = zone_nav_manager.get_navigation_info(device_id)
                    locked_direction = nav_info.get('locked_direction')
                    turn_type = nav_info.get('turn_type', 'unknown')
                    
                    if locked_direction:
                        # Apply direction based on turn type
                        if turn_type in ['left', 'right']:
                            self.robot.set_direction_for_turn_only(locked_direction, turn_type)
                        elif turn_type == 'u_turn':
                            self.robot.force_lock_direction(locked_direction, 'u_turn')
                        else:
                            # Fallback for any other lock types
                            self.robot.force_lock_direction(locked_direction, 'inherited')

                        # Store target zone information if available
                        if target_zone:
                            self._target_zone = target_zone
                            self._navigation_reason = reason
                    else:
                        # Fallback: calculate direction manually if zone manager failed
                        fallback_direction = self.calculate_turn_direction('right' if 'Right' in movement_type else 'left')
                        self.robot.set_direction_for_turn_only(fallback_direction, turn_type)
                
                return QPointF(zone_x, zone_y)
            else:
                # Valid forward/backward movement OR zone-based movement
                distance_offset = abs(right_drive)  # Use absolute value for distance
                movement_direction = 'forward' if right_drive > 0 else 'backward'
                
                # Handle zone-based navigation - MAINTAIN direction across zones
                if self.robot:
                    # Get navigation info from zone navigation manager
                    nav_info = zone_nav_manager.get_navigation_info(device_id)
                    
                    if nav_info.get('is_locked', False) and nav_info.get('locked_direction'):
                        # Synchronize sprite direction to locked direction from nav manager
                        turn_type = nav_info.get('turn_type')
                        locked_direction = nav_info['locked_direction']
                        target_zone = nav_info.get('target_zone')
                        if not self.robot.is_direction_locked or self.robot.locked_direction != locked_direction:
                            if turn_type in ['left','right']:
                                self.robot.set_direction_for_turn_only(locked_direction, turn_type)
                            else:
                                self.robot.force_lock_direction(locked_direction, 'inherited')
                            print(f"DEBUG - 🔄 Syncing to locked direction: {locked_direction} (turn_type={turn_type})")
                            if target_zone:
                                print(f"DEBUG - Moving towards/at target zone: {target_zone}")
                        # Store target zone for movement calculation if available
                        if target_zone:
                            self._target_zone = target_zone
                            self._navigation_reason = reason
                    else:
                        # No navigation lock - maintain current direction
                        if self.robot:
                            maintained_direction = self.robot.maintain_direction_across_zones()
                
                # Handle direction persistence for non-navigation movements
                if current_direction in ['north', 'south', 'east', 'west'] and self.robot:
                    # Persist previous direction across zone transitions when there is NO turn
                    # Do NOT update sprite direction just because the next zone has a direction.
                    # Direction should only change when a valid turn is detected and lock is applied above.
                    if not self.robot.is_direction_locked:
                        print(f"DEBUG - Direction persists across zone transition (no turn). Keeping: {self.robot.direction}")
                    else:
                        print(f"DEBUG - Robot direction remains LOCKED to: {self.robot.locked_direction}, ignoring direction {current_direction}")
                
                # Calculate position based on movement
                robot_x, robot_y = self.calculate_offset_position(
                    zone_x, zone_y, distance_offset, movement_direction, zone_connection
                )
                

                return QPointF(robot_x, robot_y)
            
        except Exception as e:
            print(f"DEBUG - Error calculating robot position: {e}")
            return None
    
    def find_zone_connection_from_current_location(self, zone_number: int, zones: list) -> dict:
        """
        Find the zone connection that STARTS FROM the robot's current location.
        This ensures we use the correct direction for robot movement.
        When zone direction is locked, prioritize that direction.
        
        Args:
            zone_number: Current zone number where robot is located
            zones: List of zone connection dictionaries
            
        Returns:
            Zone connection dictionary starting from current location, or None if not found
        """
        # Convert zone number to string for comparison
        zone_str = str(zone_number)
        

        
        # Get the locked direction from the consolidated zone navigation manager
        locked_direction = None
        try:
            from utils.zone_navigation_manager import get_zone_navigation_manager
            # Get device ID from the robot context if available
            device_id = getattr(self, '_current_device_id', None)
            if not device_id:
                print(f"DEBUG - No device ID available for zone navigation lookup")
            else:
                nav_manager = get_zone_navigation_manager()
                nav_info = nav_manager.get_navigation_info(device_id)
                if nav_info.get('is_locked') and nav_info.get('locked_direction'):
                    locked_direction = nav_info.get('locked_direction')
                    print(f"DEBUG - Found locked navigation direction: {locked_direction} for device {device_id}")
        except Exception as e:
            print(f"DEBUG - Could not get locked navigation direction: {e}")
        
        # Determine the robot's current orientation if available
        current_direction = None
        if self.robot and hasattr(self.robot, 'direction'):
            current_direction = self.robot.direction
            print(f"DEBUG - Robot's current orientation: {current_direction}")
        
        # Priority 1: Use locked zone direction if available
        if locked_direction:
            print(f"DEBUG - Using locked zone direction: {locked_direction}")
            for zone in zones:
                from_zone = str(zone.get('from_zone', ''))
                to_zone = str(zone.get('to_zone', ''))
                zone_direction = zone.get('direction', '').lower()
                
                print(f"DEBUG - Checking zone connection: {from_zone} -> {to_zone} ({zone_direction})")
                
                if from_zone == zone_str and zone_direction == locked_direction.lower():
                    print(f"DEBUG - Found LOCKED DIRECTION match: {from_zone} -> {to_zone} (direction: {zone_direction})")
                    return zone
        
        # Priority 2: Use robot's current direction if available
        elif current_direction:
            print(f"DEBUG - Using robot's current direction: {current_direction}")
            for zone in zones:
                from_zone = str(zone.get('from_zone', ''))
                to_zone = str(zone.get('to_zone', ''))
                zone_direction = zone.get('direction', '').lower()
                
                print(f"DEBUG - Checking zone connection: {from_zone} -> {to_zone} ({zone_direction})")
                
                if from_zone == zone_str and zone_direction == current_direction.lower():
                    print(f"DEBUG - Found directional match: {from_zone} -> {to_zone}")

                    return zone
        
        # Priority 3: Look for any connection from current zone (fallback only)

        for zone in zones:
            from_zone = str(zone.get('from_zone', ''))
            to_zone = str(zone.get('to_zone', ''))
            
            if from_zone == zone_str:
                return zone
        
        # Priority 4: Try to match just the number part in from_zone
        import re
        for zone in zones:
            from_zone = zone.get('from_zone', '')
            to_zone = zone.get('to_zone', '')
            
            # Extract numbers from zone names if they contain letters
            from_num = re.search(r'\d+', str(from_zone))
            
            if from_num and from_num.group() == zone_str:
                return zone
        
        return None
    
    def calculate_offset_position(self, zone_x: float, zone_y: float, distance: float, 
                                direction: str, zone_data: dict) -> tuple:
        """
        Calculate robot position offset from zone center based on distance and direction.
        
        Args:
            zone_x, zone_y: Zone center coordinates
            distance: Distance in mm from zone center
            direction: Movement direction (Forward/Backward/Stationary)
            zone_data: Zone information for determining movement vector
            
        Returns:
            Tuple of (x, y) coordinates for robot position
        """
        # Convert mm to map pixels based on dynamic ratio
        pixel_scale = self.meter_in_pixels / 1000.0  # 1mm = ratio/1000 pixels
        distance_pixels = distance * pixel_scale
        
        # If stationary or no distance, robot stays at zone center
        if direction.lower() == "stationary" or distance == 0:
            return zone_x, zone_y
        
        # Use robot's current orientation if available, otherwise use zone direction
        if self.robot and hasattr(self.robot, 'direction'):
            current_direction = self.robot.direction
        else:
            current_direction = zone_data.get('direction', 'north').lower()
        
        # Direction vectors for all possible orientations
        direction_vectors = {
            'north': (0, -1),   # UP
            'south': (0, 1),    # DOWN
            'east': (1, 0),     # RIGHT
            'west': (-1, 0),    # LEFT
            'northeast': (0.707, -0.707),
            'northwest': (-0.707, -0.707),
            'southeast': (0.707, 0.707),
            'southwest': (-0.707, 0.707)
        }
        
        # Get movement vector based on robot's current orientation
        dx, dy = direction_vectors.get(current_direction, (0, -1))  # Default to north
        
        
        
        # For backward movement, reverse the direction
        if direction.lower() == "backward":
            dx = -dx
            dy = -dy
        
        # Calculate final position
        robot_x = zone_x + (dx * distance_pixels)
        robot_y = zone_y + (dy * distance_pixels)
        
        return robot_x, robot_y
    
    def update_robot_position_from_csv(self, device_id: str):
        """
        Update robot position based on current CSV data for the device.
        
        Args:
            device_id: Device identifier to get positioning data for
        """
        if not self.robot_active or not self.robot:
            return
            
        try:
            # Store current device ID for zone direction lookup
            self._current_device_id = device_id
            
            # Calculate new robot position from CSV data
            new_position = self.calculate_robot_position_from_csv_data(device_id, self.zones)
            
            if new_position:
                # Update robot position
                self.robot.position = new_position
                
                # CRITICAL: Check if robot is already locked FIRST - if so, skip all direction updates
                if self.robot.is_direction_locked:
                    print(f"DEBUG - Robot direction is LOCKED to {self.robot.locked_direction}, checking nav lock sync...")
                    print(f"DEBUG - Lock info: {self.robot.get_lock_info()}")
                    # Even when locked, synchronize with consolidated nav manager if lock changed (incl. U-turn)
                    try:
                        from utils.zone_navigation_manager import get_zone_navigation_manager
                        nav_manager = get_zone_navigation_manager()
                        nav_info = nav_manager.get_navigation_info(device_id)
                        if nav_info.get('is_locked') and nav_info.get('locked_direction'):
                            desired_dir = nav_info['locked_direction']
                            desired_turn = nav_info.get('turn_type', 'inherited')
                            if self.robot.locked_direction != desired_dir:
                                self.robot.force_lock_direction(desired_dir, desired_turn)

                    except Exception as e:
                        print(f"DEBUG - Error syncing lock while locked: {e}")
                else:
                    # Robot is not locked - proceed with normal direction update logic
                    
                    current_zone_direction = self.get_current_zone_direction(device_id, self.zones)
                    if current_zone_direction:
                        # Check navigation lock status from consolidated manager; only change on ACTIVE turn lock
                        try:
                            from utils.zone_navigation_manager import get_zone_navigation_manager
                            nav_manager = get_zone_navigation_manager()
                            nav_info = nav_manager.get_navigation_info(device_id)
                            if nav_info.get('is_locked') and nav_info.get('locked_direction') and nav_info.get('turn_type') in ['left', 'right', 'u_turn']:
                                self.robot.force_lock_direction(nav_info['locked_direction'], nav_info.get('turn_type', 'zone_inherited'))
                                
                            else:
                                # No active turn → persist previous direction (do not update)
                                print(f"DEBUG - No active turn lock. Persisting direction: {self.robot.direction}")
                        except Exception as e:
                            # On error, do not change direction to avoid unintended flips
                            print(f"DEBUG - Error in robot direction update (persisting previous): {e}")
                

                self.update()  # Trigger a repaint
            else:
                print(f"DEBUG - Could not calculate new robot position for device {device_id}")
                
        except Exception as e:
            print(f"DEBUG - Error updating robot position: {e}")

    # -------- Multi-robot helpers --------
    def _determine_start_coordinates(self):
        """Find a reasonable start position and direction from current zones."""
        try:
            first_name = self.get_first_zone_chronologically()
            if not first_name:
                return QPointF(0, 0), 'north'
            zone = next((z for z in self.zones if str(z.get('from_zone','')) == str(first_name)), None)
            if zone and 'from_x' in zone and 'from_y' in zone:
                pos = QPointF(float(zone.get('from_x', 0)), float(zone.get('from_y', 0)))
                return pos, str(zone.get('direction', 'north')).lower()
        except Exception:
            pass
        return QPointF(0, 0), 'north'

    def set_active_devices(self, device_ids: list):
        """Initialize multiple robot sprites for the provided device IDs."""
        if not isinstance(device_ids, list):
            return
        
        # Sync the robots dictionary: remove those not in device_ids
        ids_to_keep = [str(did) for did in device_ids]
        current_ids = list(self.robots.keys())
        for did in current_ids:
            if did not in ids_to_keep:
                del self.robots[did]

        # Ensure zones are loaded before determining start position
        if not self.zones:
            self.update()
            return

        start_pos, start_dir = self._determine_start_coordinates()
        
        # Create sprites if not already present
        for did in ids_to_keep:
            if did not in self.robots:
                spr = RobotSprite(start_pos, direction=start_dir, label=did)
                spr.starting_zone = None
                spr.starting_coordinates = start_pos
                self.robots[did] = spr
        
        self.robot_active = True
        self.update()

    def update_robot_position_from_csv_multi(self, device_id: str):
        """Update position for a specific device in multi-robot mode."""
        try:
            key = str(device_id)
            if key not in self.robots:
                # Initialize sprite lazily if not set
                start_pos, start_dir = self._determine_start_coordinates()
                self.robots[key] = RobotSprite(start_pos, direction=start_dir, label=key)
                self.robots[key].starting_coordinates = start_pos
            robot = self.robots[key]

            # Temporarily bind single-robot reference for shared helpers
            original_robot = self.robot
            self.robot = robot
            self._current_device_id = key
            new_position = self.calculate_robot_position_from_csv_data(key, self.zones)
            # Restore
            self.robot = original_robot

            if new_position:
                robot.position = new_position
                # Keep direction/lock sync via existing helper paths in calculate_*
                self.update()
        except Exception as e:
            print(f"DEBUG - Error updating multi robot position for {device_id}: {e}")
    
    def get_current_zone_direction(self, device_id: str, zones: list) -> str:
        """
        Get the direction of the zone the robot is currently in or moving towards.
        
        Args:
            device_id: Device identifier to get positioning data for
            zones: List of zone connection dictionaries
            
        Returns:
            Direction string ('north', 'south', 'east', 'west') or None if not found
        """
        try:
            # Initialize device data handler
            import os
            device_logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'device_logs')
            device_handler = DeviceDataHandler(device_logs_dir)
            
            # Get raw positioning data
            positioning_data = device_handler.get_raw_device_positioning_data(device_id)
            if not positioning_data:

                return None
            
            current_zone_num = positioning_data['current_location_zone']
            
            # Find the zone connection that starts from the robot's current location
            zone_connection = self.find_zone_connection_from_current_location(current_zone_num, zones)
            if zone_connection:
                direction = zone_connection.get('direction', 'north')

                return direction
            
            return None
            
        except Exception as e:
            print(f"DEBUG - Error getting zone direction: {e}")
            return None

    def get_first_zone_chronologically(self):
        """Get the first zone created chronologically to use as fixed center reference"""
        if not self.zones:
            return None
        
        # If zones have an ID field, use the one with the smallest ID (oldest)
        zones_with_id = [z for z in self.zones if 'id' in z]
        if zones_with_id:
            first_zone_record = min(zones_with_id, key=lambda z: int(z.get('id', 0)))
            # Return the from_zone as that's typically the starting point
            return first_zone_record.get('from_zone', '')
        
        # Fallback: get all unique zone names and return the first one alphabetically
        # This ensures consistency even without ID fields
        unique_zones = set()
        for zone in self.zones:
            unique_zones.add(zone.get('from_zone', ''))
            unique_zones.add(zone.get('to_zone', ''))
        
        unique_zones = [z for z in unique_zones if z]  # Remove empty strings
        return sorted(unique_zones)[0] if unique_zones else None
    
    def place_remaining_zones_in_grid(self, unplaced_zones, zone_positions, zone_size):
        """Place remaining zones in a grid pattern"""
        if not unplaced_zones:
            return
        
        # Find empty space for grid
        grid_start_x = 100
        grid_start_y = self.map_height - 200
        
        cols = math.ceil(math.sqrt(len(unplaced_zones)))
        spacing = 120
        
        for i, zone_name in enumerate(unplaced_zones):
            col = i % cols
            row = i // cols
            
            x = grid_start_x + col * spacing
            y = grid_start_y + row * spacing
            
            # Ensure within bounds
            x = min(x, self.map_width - 100)
            y = min(y, self.map_height - 100)
            
            zone_positions[zone_name] = {
                'x': x,
                'y': y,
                **zone_size
            }

    def generate_stop_positions(self):
        """Generate positions for stops along zone connections with proper spacing"""
        # Group stops by zone connection to handle each connection separately
        stops_by_connection = {}
        for stop in self.stops:
            zone_connection_id = stop.get('zone_connection_id')
            if zone_connection_id not in stops_by_connection:
                stops_by_connection[zone_connection_id] = []
            stops_by_connection[zone_connection_id].append(stop)
        
        # Process each connection's stops
        for zone_connection_id, connection_stops in stops_by_connection.items():
            # Find the corresponding zone
            zone = next((z for z in self.zones if str(z.get('id')) == str(zone_connection_id)), None)
            
            if zone and 'from_x' in zone and 'to_x' in zone:
                # Get zone coordinates
                from_x = zone['from_x']
                from_y = zone['from_y']
                to_x = zone['to_x']
                to_y = zone['to_y']
                
                # Sort stops by their distance_from_start to ensure proper order
                connection_stops.sort(key=lambda s: float(s.get('distance_from_start', 0)))
                
                # Get the total distance of the zone
                total_distance = float(zone.get('magnitude', 0))
                if total_distance > 0:
                    # Position each stop based on its distance_from_start
                    for stop in connection_stops:
                        # Get the distance from start for this stop
                        distance = float(stop.get('distance_from_start', 0))
                        
                        # Calculate progress as a ratio of the total distance
                        progress = distance / total_distance
                        # Keep within bounds (0-1)
                        progress = max(0.0, min(1.0, progress))
                        
                        # Calculate base position on the connection line
                        base_x = from_x + (to_x - from_x) * progress
                        base_y = from_y + (to_y - from_y) * progress
                        
                        # Calculate perpendicular offset direction
                        dx = to_x - from_x
                        dy = to_y - from_y
                        length = math.sqrt(dx * dx + dy * dy)
                        
                        if length > 0:
                            # Normalize direction vector
                            dx /= length
                            dy /= length
                            
                            # Determine side and offset using new stop_type if available
                            stop_type = str(stop.get('stop_type', '') or '').lower()
                            perp_x = 0
                            perp_y = 0
                            if stop_type == 'left':
                                try:
                                    offset_distance = float(stop.get('left_bins_distance', 0) or 0)
                                except Exception:
                                    offset_distance = 0
                                # Left: perpendicular (dy, -dx)
                                perp_x = dy * offset_distance
                                perp_y = -dx * offset_distance
                            elif stop_type == 'right':
                                try:
                                    offset_distance = float(stop.get('right_bins_distance', 0) or 0)
                                except Exception:
                                    offset_distance = 0
                                # Right: perpendicular (-dy, dx)
                                perp_x = -dy * offset_distance
                                perp_y = dx * offset_distance
                            elif stop_type == 'center':
                                # Center: no lateral offset
                                perp_x = 0
                                perp_y = 0
                            else:
                                # Legacy fallback behavior (pre-stop_type): infer by name/counts
                                stop_name = str(stop.get('name', '') or '').lower()
                                stop_description = str(stop.get('description', '') or '').lower()
                                is_left_bin = 'left bin' in stop_name or 'left bin' in stop_description
                                is_right_bin = 'right bin' in stop_name or 'right bin' in stop_description
                                # Default pixel offset when not provided
                                offset_distance = 10
                                if is_right_bin:
                                    perp_x = -dy * offset_distance
                                    perp_y = dx * offset_distance
                                elif is_left_bin:
                                    perp_x = dy * offset_distance
                                    perp_y = -dx * offset_distance
                                else:
                                    left_bins = float(stop.get('left_bins_count', 0) or 0)
                                    right_bins = float(stop.get('right_bins_count', 0) or 0)
                                    if left_bins > 0 and right_bins == 0:
                                        perp_x = dy * offset_distance
                                        perp_y = -dx * offset_distance
                                    elif right_bins > 0 and left_bins == 0:
                                        perp_x = -dy * offset_distance
                                        perp_y = dx * offset_distance
                                    else:
                                        # Default: center
                                        perp_x = 0
                                        perp_y = 0
                            
                            # Calculate final position
                            x = base_x + perp_x
                            y = base_y + perp_y
                        else:
                            # If line has no length, use base position
                            x = base_x
                            y = base_y
                        
                        stop['display_x'] = x
                        stop['display_y'] = y
                else:
                    # Single stop - place at middle of the line
                    x = (from_x + to_x) / 2
                    y = (from_y + to_y) / 2
                    connection_stops[0]['display_x'] = x
                    connection_stops[0]['display_y'] = y
            else:
                # Fallback: distribute stops in a grid pattern
                for i, stop in enumerate(connection_stops):
                    stop['display_x'] = 100 + (i % 10) * 80
                    stop['display_y'] = 100 + (i // 10) * 60

    def clear_map(self):
        """Clear all map data"""
        self.zones = []
        self.stops = []
        self.stop_groups = []
        self.selected_stop = None
        self.selected_zone = None
        self.update()

    def set_visual_options(self, zones=True, connections=True, stops=True, labels=True, grid=True):
        """Set what elements to show"""
        self.show_zones = zones
        self.show_connections = connections
        self.show_stops = stops
        self.show_labels = labels
        self.show_grid = grid
        self.update()

    def set_map_image(self, image_path):
        """Set the map background image"""
        if image_path:
            self.map_image = QPixmap(image_path)
        else:
            self.map_image = None
        self.update()

    def paintEvent(self, event):
        """Paint the map"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Fill background
        painter.fillRect(self.rect(), self.colors['background'])

        # Apply zoom and pan transformations
        painter.translate(self.pan_offset)
        painter.scale(self.zoom_factor, self.zoom_factor)

        # Draw map background image if available
        if self.map_image:
            scaled_width = self.map_width
            scaled_height = self.map_height
            painter.drawPixmap(0, 0, scaled_width, scaled_height, self.map_image)

        # Draw grid if enabled
        if self.show_grid:
            self.draw_grid(painter)

        # Draw map boundary
        painter.setPen(QPen(QColor('#555555'), 2))
        painter.drawRect(0, 0, self.map_width, self.map_height)

        # Draw zones
        if self.show_zones:
            self.draw_zones(painter)

        # Draw connections
        if self.show_connections:
            self.draw_connections(painter)

        # Draw racks
        self.draw_racks(painter)

        # Draw stops
        # Disabled separate stop drawing to avoid duplicate dots
        # if self.show_stops:
        #     self.draw_stops(painter)
            
        # Draw robot(s) if active
        if self.robots:
            for spr in self.robots.values():
                if spr:
                    spr.draw(painter)
        elif self.robot_active and self.robot:
            self.robot.draw(painter)

    def draw_grid(self, painter):
        """Draw background grid"""
        painter.setPen(QPen(self.colors['grid'], 1))

        grid_size = 50

        # Vertical lines
        for x in range(0, self.map_width + 1, grid_size):
            painter.drawLine(x, 0, x, self.map_height)

        # Horizontal lines
        for y in range(0, self.map_height + 1, grid_size):
            painter.drawLine(0, y, self.map_width, y)

    def draw_zones(self, painter):
        """Draw zone areas"""
        drawn_zones = set()
        
        # Debug print zone data

        for zone in self.zones:

            
            # Draw from_zone
            from_zone = zone.get('from_zone', '')
            if from_zone and from_zone not in drawn_zones:
                if 'from_x' not in zone:
                    continue
                self.draw_single_zone(painter, zone, 'from_', from_zone)
                drawn_zones.add(from_zone)

            # Draw to_zone
            to_zone = zone.get('to_zone', '')
            if to_zone and to_zone not in drawn_zones:
                if 'to_x' not in zone:
                    continue
                self.draw_single_zone(painter, zone, 'to_', to_zone)
                drawn_zones.add(to_zone)

    def draw_single_zone(self, painter, zone, prefix, zone_name):
        """Draw a single zone"""
        x = zone.get(f'{prefix}x', 0) - zone.get(f'{prefix}width', 40) / 2
        y = zone.get(f'{prefix}y', 0) - zone.get(f'{prefix}height', 40) / 2
        width = zone.get(f'{prefix}width', 40)
        height = zone.get(f'{prefix}height', 40)

        # Choose color for zone
        color = self.colors.get('zone_default', QColor('#3B82F6'))

        # Draw zone rectangle
        painter.setPen(QPen(color, 2))
        painter.setBrush(QBrush(color, Qt.Dense7Pattern))
        painter.drawRect(int(x), int(y), int(width), int(height))

        # Draw zone label if enabled
        if self.show_labels:
            painter.setPen(QPen(self.colors['text'], 1))
            painter.setFont(QFont('Arial', 6, QFont.Bold))

            # Zone name - positioned exactly at the center of the zone
            text_x = x + width / 5  # Center of the zone horizontally
            text_y = y + height / 3  # Center of the zone vertically
            painter.drawText(int(text_x), int(text_y), zone_name)
        
        # Draw stops for this zone
        zone_center_x = x + width / 2
        zone_center_y = y + height / 2
        
        if self.show_stops:
            for stop in self.stops:
                # Check if stop belongs to this zone (as start or end point)
                stop_zone = stop.get('zone_name', '')
                if stop_zone == zone_name:
                    # Draw stop as a small yellow circle within the zone
                    painter.setPen(QPen(self.colors['stop_normal'], 1))
                    painter.setBrush(QBrush(self.colors['stop_normal']))
                    
                    # Draw near zone center
                    stop_size = 4
                    painter.drawEllipse(
                        int(zone_center_x - stop_size/2),
                        int(zone_center_y - stop_size/2),
                        stop_size,
                        stop_size
                    )

    def draw_racks(self, painter):
        """Racks are now displayed as part of stop labels - this method is a no-op"""
        # Rack IDs are now shown in stop labels in draw_directional_connection()
        pass

    def draw_connections(self, painter):
        """Draw connections between zones with direction-aware visualization"""
        painter.setPen(QPen(self.colors['connection'], 3))
        
        # Store starting points to draw them last
        starting_points = []

        for zone in self.zones:
            if 'from_x' in zone and 'to_x' in zone:
                from_x = zone['from_x']
                from_y = zone['from_y']
                to_x = zone['to_x']
                to_y = zone['to_y']
                
                # Calculate direction vector
                dx = to_x - from_x
                dy = to_y - from_y
                length = math.sqrt(dx * dx + dy * dy)
                
                if length > 0:
                    dx /= length
                    dy /= length
                    
                    # Store the starting point for later
                    starting_points.append((from_x, from_y))
                    
                    # Calculate connection line attributes
                    direction = zone.get('direction', 'north').lower()
                    total_bin_distance = 0
                    zone_id = str(zone.get('id', ''))
                    for stop in self.stops:
                        if str(stop.get('zone_connection_id', '')) == zone_id:
                            left_bins = float(stop.get('left_bins_distance', 0))
                            right_bins = float(stop.get('right_bins_distance', 0))
                            total_bin_distance += left_bins + right_bins

                # Draw the connection line
                painter.setPen(QPen(self.colors['connection'], 3))
                painter.drawLine(int(from_x), int(from_y), int(to_x), int(to_y))
                
                # Reset pen for connection line
                painter.setPen(QPen(self.colors['connection'], 3))
                
                direction = zone.get('direction', 'north').lower()
                
                # Draw connection line with direction-based styling
                self.draw_directional_connection(painter, zone, from_x, from_y, to_x, to_y)

                # Draw arrow to show direction
                self.draw_arrow(painter, from_x, from_y, to_x, to_y, zone)

                # Draw start point (after the connection line but before labels)
                point_size = 3  # Small 3-pixel point
                
                # Draw start point (pink with white outline)
                # Draw white outline circle first
                painter.setPen(QPen(QColor('#FFFFFF'), 2))
                painter.setBrush(QBrush(QColor('#FFFFFF')))
                painter.drawEllipse(
                    int(from_x - point_size),
                    int(from_y - point_size),
                    point_size * 2,
                    point_size * 2
                )
                
                # Draw pink circle on top
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor('#FF1493')))  # Deep pink
                painter.drawEllipse(
                    int(from_x - point_size/2),
                    int(from_y - point_size/2),
                    point_size,
                    point_size
                )

                # Draw end point (black with white outline)
                # Draw white outline circle first
                painter.setPen(QPen(QColor('#FFFFFF'), 2))
                painter.setBrush(QBrush(QColor('#FFFFFF')))
                painter.drawEllipse(
                    int(to_x - point_size),
                    int(to_y - point_size),
                    point_size * 2,
                    point_size * 2
                )
                
                # Draw black circle on top
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor('#000000')))  # Black
                painter.drawEllipse(
                    int(to_x - point_size/2),
                    int(to_y - point_size/2),
                    point_size,
                    point_size
                )

                # Draw comprehensive labels if enabled
                if self.show_labels:
                    self.draw_connection_labels(painter, zone, from_x, from_y, to_x, to_y)
    
    def draw_directional_connection(self, painter, zone, from_x, from_y, to_x, to_y):
        """Draw connection line with direction-aware styling and width based on total bin distance"""
        direction = zone.get('direction', 'north').lower()

        # Calculate total bin distance by summing up all stops' bin distances on this connection
        zone_id = str(zone.get('id', ''))
        total_bin_distance = 0
        for stop in self.stops:
            if str(stop.get('zone_connection_id', '')) == zone_id:
                left_bins = float(stop.get('left_bins_distance', 0))
                right_bins = float(stop.get('right_bins_distance', 0))
                total_bin_distance += left_bins + right_bins

        # Calculate line width based on total bin distance
        # Set minimum and maximum width limits
        min_width = 1
        max_width = 200
        base_width = 3
        
        # Scale width based on total bin distance
        # Using logarithmic scaling to handle large variations in bin distances
        if total_bin_distance > 0:
            scaled_width = base_width + math.log(total_bin_distance + 1, 2)
            line_width = min(max(scaled_width, min_width), max_width)
        else:
            line_width = base_width

        # Different line styles for different directions with dynamic width
        direction_styles = {
            'north': QPen(QColor('#10B981'), line_width*3),      # Green for north
            'south': QPen(QColor('#F59E0B'), line_width*3),      # Orange for south  
            'east': QPen(QColor('#3B82F6'), line_width*3),       # Blue for east
            'west': QPen(QColor('#8B5CF6'), line_width*3),       # Purple for west
            'northeast': QPen(QColor('#06B6D4'), line_width*3),  # Cyan for northeast
            'northwest': QPen(QColor('#EC4899'), line_width*3),  # Pink for northwest
            'southeast': QPen(QColor('#84CC16'), line_width*3),  # Lime for southeast
            'southwest': QPen(QColor('#EF4444'), line_width*3)   # Red for southwest
        }
        
        # Use direction-specific color with calculated width or default
        pen = direction_styles.get(direction, QPen(self.colors['connection'], line_width))
        painter.setPen(pen)
        
        # Draw the main connection line
        painter.drawLine(int(from_x), int(from_y), int(to_x), int(to_y))

        # Draw stops along this connection
        if self.show_stops:
            zone_id = str(zone.get('id', ''))
            connection_stops = [s for s in self.stops if str(s.get('zone_connection_id', '')) == zone_id]
            
            for stop in connection_stops:
                x = stop.get('display_x', 0)
                y = stop.get('display_y', 0)
                
                # Draw stop circle - keep points close to line
                if stop == self.selected_stop:
                    color = self.colors['stop_selected']
                    size = 6  # Larger for selected
                elif stop == self.hover_stop:
                    color = self.colors['stop_hover']
                    size = 5  # Slightly larger for hover
                else:
                    color = self.colors['stop_normal']
                    size = 4  # Normal size
                
                painter.setPen(QPen(color, 1))
                painter.setBrush(QBrush(color))
                painter.drawEllipse(int(x - size/2), int(y - size/2), size, size)
                
                # Draw stop label if enabled and zoomed in enough
                if self.show_labels and self.zoom_factor > 0.5:
                    painter.setPen(QPen(self.colors['text'], 1))
                    painter.setFont(QFont('Arial', 8))
                    stop_id = stop.get('stop_id', '')
                    stop_name = stop.get('name', stop_id)
                    
                    # Build label with rack IDs sorted by distance (ascending)
                    label_parts = [stop_name]
                    if self.racks:
                        stop_racks = [r for r in self.racks if str(r.get('stop_id')) == str(stop_id)]
                        # Sort by rack_distance_mm ascending
                        def get_distance(r):
                            try:
                                return float(r.get('rack_distance_mm', 0))
                            except:
                                return 0
                        stop_racks.sort(key=get_distance)
                        for rack in stop_racks:
                            rack_id = rack.get('rack_id', '')
                            if rack_id:
                                label_parts.append(rack_id)
                    
                    full_label = '/'.join(label_parts)
                    painter.drawText(int(x + 5), int(y - 5), full_label)

        self.update()

    def draw_direction_indicator(self, painter, from_x, from_y, to_x, to_y, direction):
        """Draw small indicator segments to show direction visually"""
        # Calculate line direction
        dx = to_x - from_x
        dy = to_y - from_y
        length = math.sqrt(dx * dx + dy * dy)
        
        if length == 0:
            return
            
        # Normalize direction
        dx /= length
        dy /= length
        
        # Draw small perpendicular tick marks along the line
        num_ticks = min(int(length / 30), 5)  # Max 5 ticks
        tick_size = 8
        
        for i in range(1, num_ticks + 1):
            progress = i / (num_ticks + 1)
            tick_x = from_x + dx * length * progress
            tick_y = from_y + dy * length * progress
            
            # Perpendicular vector for tick marks
            perp_x = -dy * tick_size
            perp_y = dx * tick_size
            
            # Draw tick mark
            painter.drawLine(
                int(tick_x - perp_x/2), int(tick_y - perp_y/2),
                int(tick_x + perp_x/2), int(tick_y + perp_y/2)
            )
    
    
    def draw_connection_labels(self, painter, zone, from_x, from_y, to_x, to_y):
        """Draw comprehensive labels for connections"""
        mid_x = (from_x + to_x) / 2
        mid_y = (from_y + to_y) / 2
        
        # Calculate perpendicular offset for labels
        dx = to_x - from_x
        dy = to_y - from_y
        length = math.sqrt(dx * dx + dy * dy)
        
        if length > 0:
            # Determine if the line is more horizontal or vertical
            is_horizontal = abs(dx) >= abs(dy)
            
            if is_horizontal:
                # For horizontal lines, position distance labels on the opposite side from stop names
                # Stop names are positioned above/below the line, so put distance on the opposite side
                # Use a smaller offset for distance labels
                perp_x = dy / length * 15  # Reduced offset to keep labels closer to lines
                perp_y = -dx / length * 15
                
                label_x = mid_x + perp_x
                label_y = mid_y + perp_y
            else:
                # For vertical lines, position distance labels on the opposite side from stop names
                # Stop names are positioned left/right of the line, so put distance on the opposite side
                perp_x = dy / length * 20  # Reduced offset to keep labels closer to lines
                perp_y = -dx / length * 20
                
                label_x = mid_x + perp_x
                label_y = mid_y + perp_y
        else:
            label_x = mid_x - 15  # Reduced offset to keep labels closer to lines
            label_y = mid_y - 10
        
        painter.setPen(QPen(self.colors['text_secondary'], 1))
        
        # Draw distance with reduced font size
        painter.setFont(QFont('Arial', 3, QFont.Bold))  # Reduced from 6 to 4
        distance = zone.get('magnitude', 0)
        painter.drawText(int(label_x), int(label_y), f"{distance}m")
        
        # Draw direction with reduced font size
        painter.setFont(QFont('Arial', 3))  # Reduced from 5 to 3
        direction = zone.get('direction', 'north').title()
        painter.drawText(int(label_x), int(label_y + 8), f"↗ {direction}")  # Reduced spacing from 12 to 8

    def draw_arrow(self, painter, from_x, from_y, to_x, to_y, zone=None):
        """Draw clear directional arrow that points exactly in the specified direction"""
        # Position arrow exactly at the destination endpoint (zone B)
        arrow_x = to_x
        arrow_y = to_y
        
        # Get the direction from zone data if provided
        if zone:
            direction = zone.get('direction', 'north').lower()
        else:
            # Fallback: calculate direction from line
            dx = to_x - from_x
            dy = to_y - from_y
            length = math.sqrt(dx * dx + dy * dy)
            if length == 0:
                return
            direction = 'east'  # Default fallback
        
        # Arrow dimensions
        arrow_length = 15  # Length of arrow head
        arrow_width = 8    # Width of arrow head
        
        # Draw arrow based on exact direction
        if direction == 'north':
            # Arrow pointing straight UP
            tip_x, tip_y = arrow_x, arrow_y - arrow_length
            left_x, left_y = arrow_x - arrow_width, arrow_y
            right_x, right_y = arrow_x + arrow_width, arrow_y
            color = QColor('#10B981')  # Green for north
            
        elif direction == 'south':
            # Arrow pointing straight DOWN
            tip_x, tip_y = arrow_x, arrow_y + arrow_length
            left_x, left_y = arrow_x - arrow_width, arrow_y
            right_x, right_y = arrow_x + arrow_width, arrow_y
            color = QColor('#F59E0B')  # Orange for south
            
        elif direction == 'east':
            # Arrow pointing straight RIGHT
            tip_x, tip_y = arrow_x + arrow_length, arrow_y
            left_x, left_y = arrow_x, arrow_y - arrow_width
            right_x, right_y = arrow_x, arrow_y + arrow_width
            color = QColor('#3B82F6')  # Blue for east
            
        elif direction == 'west':
            # Arrow pointing straight LEFT
            tip_x, tip_y = arrow_x - arrow_length, arrow_y
            left_x, left_y = arrow_x, arrow_y - arrow_width
            right_x, right_y = arrow_x, arrow_y + arrow_width
            color = QColor('#8B5CF6')  # Purple for west
            
        else:
            # For diagonal directions, use the original method
            direction_vectors = {
                'northeast': (0.707, -0.707),
                'northwest': (-0.707, -0.707),
                'southeast': (0.707, 0.707),
                'southwest': (-0.707, 0.707)
            }
            dx, dy = direction_vectors.get(direction, (1, 0))
            
            tip_x = arrow_x + dx * arrow_length
            tip_y = arrow_y + dy * arrow_length
            left_x = arrow_x - dx * arrow_width - dy * arrow_width * 0.5
            left_y = arrow_y - dy * arrow_width + dx * arrow_width * 0.5
            right_x = arrow_x - dx * arrow_width + dy * arrow_width * 0.5
            right_y = arrow_y - dy * arrow_width - dx * arrow_width * 0.5
            color = QColor('#06B6D4')  # Cyan for diagonal
        
        # Create arrow triangle
        arrow_points = [
            QPointF(tip_x, tip_y),    # Arrow tip
            QPointF(left_x, left_y),  # Left wing
            QPointF(right_x, right_y) # Right wing
        ]
        
        # Draw the arrow with thick border for visibility
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(color.darker(150), 2))  # Darker border
        painter.drawPolygon(QPolygonF(arrow_points))
        
        # Add a small circle at the base for better visibility
        painter.setBrush(QBrush(color.darker(120)))
        painter.setPen(QPen(color.darker(150), 1))
        painter.drawEllipse(int(arrow_x - 3), int(arrow_y - 3), 6, 6)

    def draw_stops(self, painter):
        """Draw stops with minimal size to prevent overlapping"""
        for stop in self.stops:
            # Get map coordinates
            map_x = stop.get('display_x', 0)
            map_y = stop.get('display_y', 0)
            
            # Use map coordinates directly since painter is already transformed
            # with zoom and pan transformations
            x = map_x
            y = map_y

            # Adjust size based on zoom factor to maintain visibility
            base_size = 2.0 / self.zoom_factor
            
            # Much smaller sizes to prevent overlapping
            if stop == self.selected_stop:
                color = self.colors['stop_selected']
                size = max(4, base_size * 2)  # Ensure selected stops are visible
            elif stop == self.hover_stop:
                color = self.colors['stop_hover']
                size = max(3, base_size * 1.5)  # Ensure hover stops are visible
            else:
                color = self.colors['stop_normal']
                size = max(2, base_size)  # Ensure normal stops are visible

            # Draw stop circle (yellow points only)
            painter.setPen(QPen(color, 1))  # Thinner border
            painter.setBrush(QBrush(color))
            painter.drawEllipse(int(x - size / 2), int(y - size / 2), int(size), int(size))

            # Draw stop label if enabled and zoomed in enough
            if self.show_labels and self.zoom_factor > 0.5:
                painter.setPen(QPen(self.colors['text'], 1))
                painter.setFont(QFont('Arial', 8))  # Slightly larger font
                stop_name = stop.get('name', stop.get('stop_id', ''))
                
                # Simple left/right detection
                is_left = 'left bin' in stop.get('name', '').lower() or 'left bin' in stop.get('description', '').lower()
                
                if is_left:
                    # Position FAR to the left for left bins
                    text_x = x - 1500  # MUCH larger offset
                    text_y = y
                    text_x -= len(stop_name) * 15  # Extra space for text
                else:
                    # Keep right bins close to their points
                    text_x = x + 20
                    text_y = y
                
                # Draw the label text
                painter.drawText(int(text_x), int(text_y), stop_name)
                    
                # Get zone info for any additional processing
                zone_connection_id = stop.get('zone_connection_id')
                zone = next((z for z in self.zones if str(z.get('id')) == str(zone_connection_id)), None)
                if zone:
                    # Get the direction line coordinates
                    from_x = zone.get('from_x', 0)
                    from_y = zone.get('from_y', 0)
                    to_x = zone.get('to_x', 0)
                    to_y = zone.get('to_y', 0)
                    
                    # Calculate the direction vector
                    dx = to_x - from_x
                    dy = to_y - from_y
                    length = math.sqrt(dx * dx + dy * dy)
                    
                    if length > 0:
                        # Normalize the direction vector
                        dx /= length
                        dy /= length
                        
                        # Different offset distances for left and right labels
                        base_offset = 10  # Base offset for stop dots
                        text_offset_left = 800  # MUCH MUCH larger offset for left bin labels only
                        text_offset_right = 20  # Small offset for right bin labels
                        
                        # Check both name and description for "left bin" or "right bin"
                        stop_name_lower = stop.get('name', '').lower()
                        stop_desc_lower = stop.get('description', '').lower()
                        is_left_bin = 'left bin' in stop_name_lower or 'left bin' in stop_desc_lower
                        
                        # For a vertical line (north/south), dx will be near 0 and dy will be +/-1
                        # For a horizontal line (east/west), dy will be near 0 and dx will be +/-1
                        
                        # Calculate base position for the label
                        if is_left_bin:
                            # For vertical lines going up: left means x-800
                            # For vertical lines going down: left means x-800
                            # Use dx/dy to determine orientation but always move left
                            base_offset = text_offset_left  # 800 pixels
                            label_x = x - base_offset  # Always move left by fixed amount
                            label_y = y  # Keep same vertical position
                            # Add extra left spacing for text
                            label_x -= len(stop_name) * 10
                        else:
                            # Right bins stay close to line
                            base_offset = text_offset_right  # 20 pixels
                            label_x = x + base_offset  # Move slightly right
                            label_y = y
                        
                        # Draw the label
                        if abs(dx) > abs(dy):  # More horizontal line
                            # For horizontal lines, draw text above/below
                            painter.drawText(int(label_x), int(label_y), stop_name)
                        else:  # More vertical line
                            # For vertical lines, rotate text
                            painter.save()
                            painter.translate(int(label_x), int(label_y))
                            if dx > 0:  # Line going up
                                painter.rotate(-90)
                            else:  # Line going down
                                painter.rotate(90)
                            painter.drawText(0, 0, stop_name)
                            painter.restore()

    def calculate_stop_label_position(self, stop, x, y, size):
        """Calculate position for stop label based on whether stop is a left or right bin"""
        # Find the zone connection this stop belongs to
        zone_connection_id = stop.get('zone_connection_id')
        zone = next((z for z in self.zones if str(z.get('id')) == str(zone_connection_id)), None)
        
        if zone and 'from_x' in zone and 'to_x' in zone:
            # Get the direction line coordinates
            from_x = zone['from_x']
            from_y = zone['from_y']
            to_x = zone['to_x']
            to_y = zone['to_y']
            
            # Calculate the direction vector of the line
            dx = to_x - from_x
            dy = to_y - from_y
            length = math.sqrt(dx * dx + dy * dy)
            
            if length > 0:
                # Normalize the direction vector
                dx /= length
                dy /= length
                
                # Base offset distance for labels
                offset_distance = 20  # Distance from stop point to label
                
                # Determine which side based on stop name/description
                stop_name = stop.get('name', '').lower()
                stop_description = stop.get('description', '').lower()
                
                # Check both name and description for "left bin" or "right bin"
                is_left_bin = 'left bin' in stop_name or 'left bin' in stop_description
                is_right_bin = 'right bin' in stop_name or 'right bin' in stop_description
                
                if is_left_bin:
                    # Place label on left side
                    label_x = x - offset_distance
                    perp_x = -dy
                    perp_y = dx
                elif is_right_bin:
                    # Place label on right side
                    label_x = x + offset_distance
                    perp_x = dy
                    perp_y = -dx
                else:
                    # Fallback to bin counts
                    left_bins = float(stop.get('left_bins_count', 0))
                    right_bins = float(stop.get('right_bins_count', 0))
                    
                    if right_bins > 0 and left_bins == 0:
                        # Place on right side
                        label_x = x + offset_distance
                        perp_x = dy
                        perp_y = -dx
                    else:
                        # Place on left side by default
                        label_x = x - offset_distance
                        perp_x = -dy
                        perp_y = dx
                
                label_y = y
                
                # Determine if the line is more horizontal or vertical for text orientation
                is_horizontal = abs(dx) >= abs(dy)
                
                return label_x, label_y, is_horizontal
        
        # Fallback: position to the right of the stop point
        return x + size + 5, y + 1, False

    def draw_stop_bins(self, painter, stop, x, y, size):
        """Draw minimal bin indicators for a stop"""
        left_bins = int(stop.get('left_bins_count', 0))
        right_bins = int(stop.get('right_bins_count', 0))

        # Scale bin size and spacing based on zoom factor
        bin_size = max(1, 1.0 / self.zoom_factor)  # Adjust bin size for zoom
        bin_spacing = max(2, 2.0 / self.zoom_factor)  # Adjust spacing for zoom

        # Draw left bins - only if zoomed in enough
        if left_bins > 0 and self.zoom_factor > 0.4:  # Lower threshold to show bins
            painter.setPen(QPen(QColor('#60A5FA'), 1))
            painter.setBrush(QBrush(QColor('#60A5FA')))

            start_x = x - size - bin_spacing
            for i in range(min(left_bins, 3)):  # Max 3 visual bins
                bin_x = start_x - i * (bin_size + 1)
                painter.drawRect(int(bin_x), int(y - bin_size / 2), max(1, int(bin_size)), max(1, int(bin_size)))

        # Draw right bins - only if zoomed in enough
        if right_bins > 0 and self.zoom_factor > 0.4:  # Lower threshold to show bins
            painter.setPen(QPen(QColor('#34D399'), 1))
            painter.setBrush(QBrush(QColor('#34D399')))

            start_x = x + size + bin_spacing
            for i in range(min(right_bins, 3)):  # Max 3 visual bins
                bin_x = start_x + i * (bin_size + 1)
                painter.drawRect(int(bin_x), int(y - bin_size / 2), max(1, int(bin_size)), max(1, int(bin_size)))

    def mousePressEvent(self, event):
        """Handle mouse press events"""
        if event.button() == Qt.LeftButton:
            # Convert screen coordinates to map coordinates
            map_point = self.screen_to_map_coords(event.pos())

            # Check if clicked on a stop
            clicked_stop = self.get_stop_at_position(map_point)
            if clicked_stop:
                self.selected_stop = clicked_stop
                self.stop_clicked.emit(clicked_stop)
                self.update()
                return

            # Check if clicked on a zone
            clicked_zone = self.get_zone_at_position(map_point)
            if clicked_zone:
                self.selected_zone = clicked_zone
                self.zone_clicked.emit(clicked_zone)
                self.update()
                return

            # Start panning
            self.is_panning = True
            self.last_pan_point = event.pos()

    def mouseMoveEvent(self, event):
        """Handle mouse move events"""
        if self.is_panning and event.buttons() & Qt.LeftButton:
            # Pan the map
            delta = event.pos() - self.last_pan_point
            self.pan_offset += delta
            self.last_pan_point = event.pos()
            self.update()
        else:
            # Check for hover
            map_point = self.screen_to_map_coords(event.pos())
            hover_stop = self.get_stop_at_position(map_point)

            if hover_stop != self.hover_stop:
                self.hover_stop = hover_stop
                self.update()

    def mouseReleaseEvent(self, event):
        """Handle mouse release events"""
        if event.button() == Qt.LeftButton:
            self.is_panning = False

    def wheelEvent(self, event):
        """Handle wheel events for zooming with fixed center point"""
        zoom_in = event.angleDelta().y() > 0
        zoom_factor = 1.15 if zoom_in else 1 / 1.15
        
        # Apply zoom limits
        new_zoom = self.zoom_factor * zoom_factor
        if self.min_zoom <= new_zoom <= self.max_zoom:
            # Get mouse position in widget coordinates
            mouse_pos = event.pos()
            
            # Convert current mouse position to map coordinates
            old_map_pos = self.screen_to_map_coords(mouse_pos)
            
            # Update zoom factor
            old_zoom = self.zoom_factor
            self.zoom_factor = new_zoom
            
            # Calculate new screen position of the same map point
            new_screen_pos = QPointF(
                old_map_pos.x() * self.zoom_factor + self.pan_offset.x(),
                old_map_pos.y() * self.zoom_factor + self.pan_offset.y()
            )
            
            # Adjust pan offset so mouse position stays at the same map location
            self.pan_offset.setX(self.pan_offset.x() + (mouse_pos.x() - new_screen_pos.x()))
            self.pan_offset.setY(self.pan_offset.y() + (mouse_pos.y() - new_screen_pos.y()))
            
            self.update()

    def screen_to_map_coords(self, screen_point):
        """Convert screen coordinates to map coordinates"""
        map_x = (screen_point.x() - self.pan_offset.x()) / self.zoom_factor
        map_y = (screen_point.y() - self.pan_offset.y()) / self.zoom_factor
        return QPointF(map_x, map_y)

    def map_to_screen_coords(self, map_point):
        """Convert map coordinates to screen coordinates"""
        screen_x = map_point.x() * self.zoom_factor + self.pan_offset.x()
        screen_y = map_point.y() * self.zoom_factor + self.pan_offset.y()
        return QPointF(screen_x, screen_y)

    def get_stop_at_position(self, position):
        """Get stop at given position"""
        # Convert screen position to map coordinates
        map_position = self.screen_to_map_coords(position)
        
        # Adjust click radius based on zoom factor for better usability
        # Smaller radius when zoomed in, larger when zoomed out
        base_click_radius = 10  # Base click radius in map units
        click_radius = base_click_radius / self.zoom_factor  # Adjust for zoom

        for stop in self.stops:
            stop_x = stop.get('display_x', 0)
            stop_y = stop.get('display_y', 0)

            # Calculate distance in map coordinates
            distance = math.sqrt((map_position.x() - stop_x) ** 2 + (map_position.y() - stop_y) ** 2)
            if distance <= click_radius:
                return stop

        return None

    def get_zone_at_position(self, position):
        """Get zone at given position"""
        # Convert screen position to map coordinates
        map_position = self.screen_to_map_coords(position)
        
        for zone in self.zones:
            # Check from_zone
            if 'from_x' in zone:
                x = zone['from_x'] - zone.get('from_width', 40) / 2
                y = zone['from_y'] - zone.get('from_height', 40) / 2
                width = zone.get('from_width', 40)
                height = zone.get('from_height', 40)

                if (x <= map_position.x() <= x + width and
                        y <= map_position.y() <= y + height):
                    return zone

            # Check to_zone
            if 'to_x' in zone:
                x = zone['to_x'] - zone.get('to_width', 40) / 2
                y = zone['to_y'] - zone.get('to_height', 40) / 2
                width = zone.get('to_width', 40)
                height = zone.get('to_height', 40)

                if (x <= map_position.x() <= x + width and
                        y <= map_position.y() <= y + height):
                    return zone

        return None

    def reset_view(self):
        """Reset zoom and pan to default"""
        self.zoom_factor = 1.0
        self.pan_offset = QPointF(0, 0)
        self.update()

    def fit_to_view(self):
        """Fit map to view"""
        if not self.zones and not self.stops:
            self.reset_view()
            return

        # Calculate bounds of all elements
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')

        # Check zones
        for zone in self.zones:
            if 'from_x' in zone:
                x = zone['from_x'] - zone.get('from_width', 40) / 2
                y = zone['from_y'] - zone.get('from_height', 40) / 2
                width = zone.get('from_width', 40)
                height = zone.get('from_height', 40)

                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x + width)
                max_y = max(max_y, y + height)

            if 'to_x' in zone:
                x = zone['to_x'] - zone.get('to_width', 40) / 2
                y = zone['to_y'] - zone.get('to_height', 40) / 2
                width = zone.get('to_width', 40)
                height = zone.get('to_height', 40)

                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x + width)
                max_y = max(max_y, y + height)

        # Check stops
        for stop in self.stops:
            x = stop.get('display_x', 0)
            y = stop.get('display_y', 0)
            min_x = min(min_x, x - 30)
            min_y = min(min_y, y - 30)
            max_x = max(max_x, x + 30)
            max_y = max(max_y, y + 30)

        if min_x != float('inf'):
            # Add padding around the content for better visibility
            padding = 50
            min_x -= padding
            min_y -= padding
            max_x += padding
            max_y += padding
            
            # Calculate zoom to fit
            content_width = max_x - min_x
            content_height = max_y - min_y

            if content_width > 0 and content_height > 0:
                # Use more of the available space (reduce margins)
                zoom_x = (self.width() - 50) / content_width
                zoom_y = (self.height() - 50) / content_height
                self.zoom_factor = min(zoom_x, zoom_y, self.max_zoom)

                # Center the content
                center_x = (min_x + max_x) / 2
                center_y = (min_y + max_y) / 2

                self.pan_offset = QPointF(
                    self.width() / 2 - center_x * self.zoom_factor,
                    self.height() / 2 - center_y * self.zoom_factor
                )

                self.update()


class MapViewerWidget(QWidget):
    """Map viewer widget with controls"""

    stop_selected = pyqtSignal(dict)
    zone_selected = pyqtSignal(dict)

    def __init__(self, api_client: APIClient, csv_handler: CSVHandler):
        super().__init__()
        self.api_client = api_client
        self.csv_handler = csv_handler
        self.logger = setup_logger('map_viewer')

        self.setup_ui()

    def setup_ui(self):
        """Setup map viewer UI"""
        # Create layout with minimal margins and spacing
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Ensure widget itself has proper visibility and styling
        self.setVisible(True)
        self.setAttribute(Qt.WA_StyledBackground, True)

        # Controls panel - create but don't add to layout yet
        self.controls_panel = QFrame()
        self.controls_panel.setObjectName("controls_panel")
        controls_layout = QVBoxLayout(self.controls_panel)  # Add layout to the frame
        self.create_controls_panel(controls_layout)  # Pass the layout instead of the frame
        layout.addWidget(self.controls_panel)

        # Map canvas with explicit visibility and size policy
        self.map_canvas = MapCanvas()
        self.map_canvas.setVisible(True)  # Explicitly set map canvas visibility
        self.map_canvas.stop_clicked.connect(self.on_stop_clicked)
        self.map_canvas.zone_clicked.connect(self.on_zone_clicked)
        # Ensure map canvas expands properly
        self.map_canvas.setSizePolicy(
            self.map_canvas.sizePolicy().Expanding,
            self.map_canvas.sizePolicy().Expanding
        )
        # Add to layout and force show
        layout.addWidget(self.map_canvas, 1)  # Give map canvas stretch priority
        self.map_canvas.show()

    def create_controls_panel(self, controls_layout):
        """Create map control panel"""
        controls_frame = QFrame()
        controls_frame.setStyleSheet("""
            QFrame {
                background-color: #353535;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 10px;
            }
        """)
        inner_layout = QHBoxLayout(controls_frame)

        # View controls
        view_group = QFrame()
        view_layout = QHBoxLayout(view_group)
        view_layout.setContentsMargins(0, 0, 0, 0)

        # Zoom controls
        zoom_out_btn = QPushButton("🔍−")
        zoom_out_btn.setFixedSize(30, 30)
        zoom_out_btn.clicked.connect(self.zoom_out)
        self.apply_button_style(zoom_out_btn)
        view_layout.addWidget(zoom_out_btn)

        # Zoom slider
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(10, 500)  # 0.1x to 5.0x zoom
        self.zoom_slider.setValue(100)  # 1.0x zoom
        self.zoom_slider.valueChanged.connect(self.on_zoom_slider_changed)
        self.zoom_slider.setFixedWidth(100)
        view_layout.addWidget(self.zoom_slider)

        zoom_in_btn = QPushButton("🔍+")
        zoom_in_btn.setFixedSize(30, 30)
        zoom_in_btn.clicked.connect(self.zoom_in)
        self.apply_button_style(zoom_in_btn)
        view_layout.addWidget(zoom_in_btn)

        # View buttons
        reset_btn = QPushButton("🎯 Reset")
        reset_btn.clicked.connect(self.reset_view)
        self.apply_button_style(reset_btn)
        view_layout.addWidget(reset_btn)

        fit_btn = QPushButton("📐 Fit")
        fit_btn.clicked.connect(self.fit_to_view)
        self.apply_button_style(fit_btn)
        view_layout.addWidget(fit_btn)

        inner_layout.addWidget(view_group)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setStyleSheet("color: #555555;")
        inner_layout.addWidget(separator)

        # Display options
        display_group = QFrame()
        display_layout = QHBoxLayout(display_group)
        display_layout.setContentsMargins(0, 0, 0, 0)

        # Checkboxes for display options
        self.show_zones_cb = QCheckBox("Zones")
        self.show_zones_cb.setChecked(True)
        self.show_zones_cb.toggled.connect(self.update_display_options)
        display_layout.addWidget(self.show_zones_cb)

        self.show_connections_cb = QCheckBox("Connections")
        self.show_connections_cb.setChecked(True)
        self.show_connections_cb.toggled.connect(self.update_display_options)
        display_layout.addWidget(self.show_connections_cb)

        self.show_stops_cb = QCheckBox("Stops")
        self.show_stops_cb.setChecked(True)
        self.show_stops_cb.toggled.connect(self.update_display_options)
        display_layout.addWidget(self.show_stops_cb)

        self.show_labels_cb = QCheckBox("Labels")
        self.show_labels_cb.setChecked(True)
        self.show_labels_cb.toggled.connect(self.update_display_options)
        display_layout.addWidget(self.show_labels_cb)

        self.show_grid_cb = QCheckBox("Grid")
        self.show_grid_cb.setChecked(True)
        self.show_grid_cb.toggled.connect(self.update_display_options)
        display_layout.addWidget(self.show_grid_cb)

        inner_layout.addWidget(display_group)

        inner_layout.addStretch()

        # Info label
        self.info_label = QLabel("Click on zones or stops to select them")
        self.info_label.setStyleSheet("color: #cccccc; font-style: italic;")
        inner_layout.addWidget(self.info_label)

        controls_layout.addWidget(controls_frame)

    def apply_button_style(self, button):
        """Apply button styling"""
        button.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #666666;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
        """)

    def set_map_data(self, zones, stops, stop_groups, map_width=1000, map_height=800, map_data=None, task_status=None, task_details=None, racks=None):
        """Set map data"""
        # Store map_data for reference
        if map_data:
            # Load map image or background if available
            map_image = map_data.get('image_path')
            if map_image:
                self.map_canvas.set_map_image(map_image)
        
        # Set the map data with dimensions and task details
        self.map_canvas.set_map_data(
            zones, stops, stop_groups, 
            map_width, map_height, 
            map_data=map_data,
            task_status=task_status,
            task_details=task_details,
            racks=racks
        )
        self.update_info_label()

    def clear_map(self):
        """Clear map data"""
        self.map_canvas.clear_map()
        self.update_info_label()

    def set_task_mode(self, enabled=True):
        """Toggle between full map view and task-specific view"""
        # Get the controls panel
        controls = self.findChild(QFrame)
        if controls:
            controls.setVisible(not enabled)
        
        # Set default display options for task view
        if enabled:
            self.show_zones_cb.setChecked(True)
            self.show_connections_cb.setChecked(True)
            self.show_stops_cb.setChecked(True)
            self.show_labels_cb.setChecked(True)
            self.show_grid_cb.setChecked(True)
            # Force update display
            self.update_display_options()
            # Fit to view when showing task
            self.fit_to_view()

    def update_display_options(self):
        """Update display options"""
        self.map_canvas.set_visual_options(
            zones=self.show_zones_cb.isChecked(),
            connections=self.show_connections_cb.isChecked(),
            stops=self.show_stops_cb.isChecked(),
            labels=self.show_labels_cb.isChecked(),
            grid=self.show_grid_cb.isChecked()
        )

    def update_info_label(self):
        """Update info label"""
        zone_count = len(self.map_canvas.zones)
        stop_count = len(self.map_canvas.stops)

        if zone_count == 0 and stop_count == 0:
            self.info_label.setText("No map data loaded")
        else:
            self.info_label.setText(f"Map: {zone_count} zones, {stop_count} stops | Click to select")

    def zoom_in(self):
        """Zoom in"""
        current_zoom = int(self.map_canvas.zoom_factor * 100)
        new_zoom = min(current_zoom + 20, 500)
        self.zoom_slider.setValue(new_zoom)

    def zoom_out(self):
        """Zoom out"""
        current_zoom = int(self.map_canvas.zoom_factor * 100)
        new_zoom = max(current_zoom - 20, 10)
        self.zoom_slider.setValue(new_zoom)

    def on_zoom_slider_changed(self, value):
        """Handle zoom slider change with center-based zoom"""
        new_zoom_factor = value / 100.0
        
        if new_zoom_factor != self.map_canvas.zoom_factor:
            # Get center point of the widget
            center_point = QPointF(self.map_canvas.width() / 2, self.map_canvas.height() / 2)
            
            # Convert center to map coordinates
            center_map_pos = self.map_canvas.screen_to_map_coords(center_point)
            
            # Update zoom factor
            self.map_canvas.zoom_factor = new_zoom_factor
            
            # Calculate new screen position of the center map point
            new_screen_pos = QPointF(
                center_map_pos.x() * self.map_canvas.zoom_factor + self.map_canvas.pan_offset.x(),
                center_map_pos.y() * self.map_canvas.zoom_factor + self.map_canvas.pan_offset.y()
            )
            
            # Adjust pan offset to keep center point centered
            self.map_canvas.pan_offset.setX(self.map_canvas.pan_offset.x() + (center_point.x() - new_screen_pos.x()))
            self.map_canvas.pan_offset.setY(self.map_canvas.pan_offset.y() + (center_point.y() - new_screen_pos.y()))
            
            self.map_canvas.update()

    def reset_view(self):
        """Reset view"""
        self.map_canvas.reset_view()
        self.zoom_slider.setValue(100)

    def fit_to_view(self):
        """Fit to view"""
        self.map_canvas.fit_to_view()
        # Update slider to reflect new zoom
        current_zoom = int(self.map_canvas.zoom_factor * 100)
        self.zoom_slider.setValue(current_zoom)

    def on_stop_clicked(self, stop_data):
        """Handle stop click"""
        self.stop_selected.emit(stop_data)
        stop_name = stop_data.get('name', stop_data.get('stop_id', 'Unknown'))
        self.info_label.setText(f"Selected stop: {stop_name}")

    def on_zone_clicked(self, zone_data):
        """Handle zone click"""
        self.zone_selected.emit(zone_data)
        zone_name = f"{zone_data.get('from_zone', '')} → {zone_data.get('to_zone', '')}"
        self.info_label.setText(f"Selected zone: {zone_name}")
    
    def update_robot_position(self, device_id: str):
        """
        Update robot position based on CSV data for the given device.
        
        Args:
            device_id: Device identifier to update position for
        """
        self.map_canvas.update_robot_position_from_csv(device_id)
