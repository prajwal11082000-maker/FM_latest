from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QTextEdit, QFrame, QPushButton, QScrollArea,
                             QGridLayout, QWidget, QSplitter)
from PyQt5.QtCore import Qt, QTimer
from ui.common.base_dialog import BaseDialog
from PyQt5.QtGui import QFont
import logging

from ui.maps.map_viewer import MapViewerWidget
from api.client import APIClient
from data_manager.device_data_handler import DeviceDataHandler
import os


class TaskDetailsDialog(BaseDialog):
    def __init__(self, parent=None, task_data=None):
       super().__init__(parent)
       self.task_data = task_data or {}
       self.csv_handler = parent.csv_handler if parent else None
       self.map_data = None
       self.zones_data = []
       self.stops_data = []
       self.stop_groups_data = []
       
       # Initialize logger
       self.logger = logging.getLogger(__name__)
       
       # Initialize device data handler
       self.device_data_handler = DeviceDataHandler(
           os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'device_logs')
       )
       
       # Initialize UI elements to None
       self.task_id_label = None
       self.task_name_label = None
       self.task_type_label = None
       self.assigned_device_label = None
       self.assigned_user_label = None
       self.created_by_label = None
       self.estimated_duration_label = None
       self.actual_duration_label = None
       self.status_label = None
       self.created_at_label = None
       self.started_at_label = None
       self.completed_at_label = None
       self.map_viewer = None
       
       # Initialize live tracking labels
       self.device_location_label = None
       self.device_distance_label = None
       self.device_direction_label = None
       self.live_tracking_blocks = {}
       self.live_tracking_devices = []
       
       # Initialize default labels for task type details
       self.zone_label = "Zones"
       self.stop_label = "Stops"
       
       # Load data first
       self.load_task_type_details()
       
       # Setup UI (this will create all the labels)
       self.setup_ui()
       
       # Populate data after UI is setup
       self.populate_data()

    def start_live_tracking_updates(self):
        """Start timer for live tracking updates"""
        # Initialize timer for live updates
        self.tracking_timer = QTimer(self)
        self.tracking_timer.timeout.connect(self.update_live_tracking)
        self.tracking_timer.start(1000)  # Update every second

    def update_live_tracking(self):
        """Update live tracking information"""
        if not getattr(self, 'live_tracking_blocks', None):
            return
        for did, labels in self.live_tracking_blocks.items():
            try:
                device_data = self.device_data_handler.get_latest_device_data(did)
                if device_data:
                    labels['location'].setText(device_data.get('current_location', 'N/A'))
                    labels['distance'].setText(device_data.get('distance', 'N/A'))
                    labels['direction'].setText(device_data.get('direction', 'N/A'))
                else:
                    labels['location'].setText("No data available")
                    labels['distance'].setText("N/A")
                    labels['direction'].setText("N/A")
            except Exception:
                labels['location'].setText("No data available")
                labels['distance'].setText("N/A")
                labels['direction'].setText("N/A")

    def setup_ui(self):
       """Setup dialog UI"""
       self.setWindowTitle("Task Details")
       self.setModal(True)
       self.setMinimumSize(1000, 800)
       self.resize(1200, 800)

       # Apply dark theme
       self.setStyleSheet("""
           QDialog {
               background-color: #2b2b2b;
               color: #ffffff;
           }
           QLabel {
               color: #ffffff;
           }
           QScrollArea {
               background-color: #2b2b2b;
               border: none;
           }
           QWidget#scrollContent {
               background-color: #2b2b2b;
           }
           QPushButton {
               background-color: #555555;
               border: 1px solid #666666;
               padding: 10px 20px;
               border-radius: 4px;
               color: #ffffff;
               font-weight: bold;
           }
           QPushButton:hover {
               background-color: #666666;
           }
       """)

       layout = QVBoxLayout(self)
       layout.setSpacing(20)
       layout.setContentsMargins(20, 20, 20, 20)

       # Title
       title = QLabel(f"Task Details: {self.task_data.get('task_name', 'Unknown Task')}")
       title.setFont(QFont("Arial", 16, QFont.Bold))
       title.setAlignment(Qt.AlignCenter)
       title.setStyleSheet("color: #ff6b35; margin-bottom: 10px;")
       layout.addWidget(title)

       # Create splitter for details and map
       splitter = QSplitter(Qt.Horizontal)
       
       # Left panel - Task details
       left_panel = QWidget()
       left_layout = QVBoxLayout(left_panel)
       left_layout.setContentsMargins(0, 0, 0, 0)
       
       # Create scroll area for task details
       scroll_area = QScrollArea()
       scroll_area.setWidgetResizable(True)
       scroll_area.setFrameStyle(QFrame.NoFrame)

       # Create content widget for the scroll area
       content_widget = QWidget()
       content_widget.setObjectName("scrollContent")
       content_layout = QVBoxLayout(content_widget)
       content_layout.setSpacing(15)
       content_layout.setContentsMargins(5, 5, 15, 5)

       # Add all sections
       self.create_basic_info_section(content_layout)
       self.create_assignment_section(content_layout)
       self.create_task_type_details_section(content_layout)
       self.create_live_tracking_section(content_layout)
       self.create_location_timing_section(content_layout)
       self.create_status_section(content_layout)

       # Add a stretcher to push everything up
       content_layout.addStretch()

       # Set the content widget to the scroll area
       scroll_area.setWidget(content_widget)
       left_layout.addWidget(scroll_area)
       
       # Right panel - Map viewer
       right_panel = QWidget()
       right_layout = QVBoxLayout(right_panel)
       right_layout.setContentsMargins(0, 0, 0, 0)
       
       # Map title
       map_title = QLabel("Task Map")
       map_title.setFont(QFont("Arial", 14, QFont.Bold))
       map_title.setAlignment(Qt.AlignCenter)
       map_title.setStyleSheet("color: #ff6b35; margin-bottom: 10px;")
       right_layout.addWidget(map_title)
       
       # Map viewer
       api_client = APIClient()
       self.map_viewer = MapViewerWidget(api_client, self.csv_handler)
       self.map_viewer.setMinimumSize(400, 400)
       
       right_layout.addWidget(self.map_viewer)
       
       # Add panels to splitter
       splitter.addWidget(left_panel)
       splitter.addWidget(right_panel)
       splitter.setSizes([600, 600])  # Set initial sizes
       layout.addWidget(splitter)

       # Close button
       close_btn = QPushButton("Close")
       close_btn.setAutoDefault(False)
       close_btn.clicked.connect(self.accept)
       close_btn.setStyleSheet("""
           QPushButton {
               background-color: #ff6b35;
               color: white;
               margin-top: 10px;
           }
           QPushButton:hover {
               background-color: #e55a2b;
           }
       """)
       layout.addWidget(close_btn)
        
    def load_task_type_details(self):
       """Load map, zones, stops, and stop groups data for the task"""
       if not self.csv_handler or not self.task_data:
           return
           
       try:
           # Load task details from JSON
           import json
           self.task_details = {}
           if self.task_data.get('task_details'):
               try:
                   self.task_details = json.loads(self.task_data['task_details'])
               except json.JSONDecodeError:
                   print("Error decoding task details JSON")

           # Store task type for later use
           self.task_type = self.task_data.get('task_type', '').lower()


           # Get map ID from task or task details
           map_id = self.task_data.get('map_id')
           if self.task_type == 'auditing' and self.task_details:
               # For auditing tasks, get map ID from task details
               auditing_map_id = self.task_details.get('auditing_map_id', map_id)
               if auditing_map_id:
                   map_id = auditing_map_id
                   
           if not map_id:
               self.logger.error("No map ID found for task")
               return
               
           # Load map data
           maps = self.csv_handler.read_csv('maps')

           self.map_data = next((m for m in maps if str(m.get('id')) == str(map_id)), None)
           
           if not self.map_data:
               self.logger.error(f"Could not find map with ID {map_id}")

               return
               
           
           if self.map_data:
               # Load zones data based on zone_ids
               zones = self.csv_handler.read_csv('zones')
               zone_ids = str(self.task_data.get('zone_ids', '')).split(',')
               self.zones_data = [z for z in zones if str(z.get('id')) in zone_ids]
               
               # Load stops data based on stop_ids
               stops = self.csv_handler.read_csv('stops')
               stop_ids = [s.strip() for s in str(self.task_data.get('stop_ids', '')).split(',') if s.strip()]
               self.stops_data = [s for s in stops if (str(s.get('id')) in stop_ids or 
                                                     str(s.get('stop_id')) in stop_ids)]
               
               # Load stop groups data
               stop_groups = self.csv_handler.read_csv('stop_groups')
               self.stop_groups_data = [sg for sg in stop_groups if str(sg.get('map_id')) == str(map_id)]

               # Store additional context based on task type
               task_type = self.task_data.get('task_type', '')
               if task_type == 'picking':
                   self.zone_label = "Drop Zone"
                   self.stop_label = "Pick Up Stops"
               elif task_type == 'storing':
                   self.zone_label = "Pickup Zone"
                   self.stop_label = "Pickup Stops"
               else:
                   self.zone_label = "Zones"
                   self.stop_label = "Stops"

       except Exception as e:
           print(f"Error loading task type details: {e}")
           self.map_data = None
           self.zones_data = []
           self.stops_data = []
           self.stop_groups_data = []
           self.task_details = {}
                
    def create_task_type_details_section(self, parent_layout):
        """Create task type details section with map, zones, and stops information"""
        frame, layout = self.create_section_frame("Task Type Details")
        
        grid_layout = QGridLayout()
        row = 0

        # Task Type Specific Label
        task_type = self.task_data.get('task_type', '').title()
        grid_layout.addWidget(QLabel(f"{task_type} Task Details:"), row, 0)
        row += 1
        
        # Map Information
        map_label_text = "Map:"
        if task_type == 'Picking':
            map_label_text = "Pickup Map:"
        elif task_type == 'Storing':
            map_label_text = "Storing Map:"
        elif task_type == 'Auditing':
            map_label_text = "Auditing Map:"
            
        grid_layout.addWidget(QLabel(map_label_text), row, 0)
        map_name = self.map_data.get('name', 'N/A') if self.map_data else 'N/A'
        if self.task_details:
            if task_type == 'Picking':
                map_name = self.task_details.get('pickup_map_name', map_name)
            elif task_type == 'Storing':
                map_name = self.task_details.get('storing_map_name', map_name)
            elif task_type == 'Auditing':
                map_name = self.task_details.get('auditing_map_name', map_name)
        map_label = QLabel(map_name)
        map_label.setStyleSheet("color: #cccccc; font-weight: bold;")
        grid_layout.addWidget(map_label, row, 1)
        
        # Charging Station Information
        if task_type == 'Charging' and self.task_details:
            row += 1
            grid_layout.addWidget(QLabel("Charging Station:"), row, 0)
            station = self.task_details.get('charging_station', 'N/A')
            station_label = QLabel(f"Zone {station}" if station != 'N/A' else 'N/A')
            station_label.setStyleSheet("color: #cccccc; font-weight: bold;")
            grid_layout.addWidget(station_label, row, 1)
        
        # Zones Information
        if task_type not in ['Auditing', 'Charging']:  # Auditing and Charging tasks don't have zones
            row += 1
            grid_layout.addWidget(QLabel(self.zone_label + ":"), row, 0)
            
            zones_text = ""
            if self.task_details:
                # Display zone name from task details if available
                if task_type == 'Picking' and self.task_details.get('drop_zone_name'):
                    zones_text = f"• {self.task_details['drop_zone_name']}"
                elif task_type == 'Storing' and self.task_details.get('pickup_zone_name'):
                    zones_text = f"• {self.task_details['pickup_zone_name']}"
            
            # If no zone name in task details, fall back to zones data
            if not zones_text:
                for zone in self.zones_data:
                    from_zone = zone.get('from_zone', 'Unknown')
                    to_zone = zone.get('to_zone', 'Unknown')
                    zone_text = f"• {from_zone} → {to_zone}"
                    if zone.get('magnitude'):
                        zone_text += f" ({zone.get('magnitude')} {zone.get('direction', '')})"
                    zones_text += f"{zone_text}\\n"
            
            zones_label = QLabel(zones_text.strip() or "No zones assigned")
            zones_label.setStyleSheet("color: #cccccc;")
            zones_label.setWordWrap(True)
            grid_layout.addWidget(zones_label, row, 1)
        
        # Stops Information
        if task_type not in ['Auditing', 'Charging']:  # Auditing and Charging tasks don't have stops
            row += 1
            grid_layout.addWidget(QLabel(self.stop_label + ":"), row, 0)
            
            stops_text = []  # Use a list to collect stop entries
            
            # First try to get stops from task details
            if self.task_details:
                if task_type == 'Picking':
                    if self.task_details.get('pickup_stops'):
                        stops = self.task_details.get('pickup_stops', [])
                        stop_names = self.task_details.get('pickup_stop_names', [])
                    else:
                        stops = self.task_details.get('drop_stops', [])
                        stop_names = self.task_details.get('drop_stop_names', [])
                    for i, stop_id in enumerate(stops):
                        name = stop_names[i] if i < len(stop_names) else stop_id
                        stops_text.append(f"• {name}")
                elif task_type == 'Storing' and self.task_details.get('pickup_stops'):
                    stops = self.task_details.get('pickup_stops', [])
                    stop_names = self.task_details.get('pickup_stop_names', [])
                    for i, stop_id in enumerate(stops):
                        name = stop_names[i] if i < len(stop_names) else stop_id
                        stops_text.append(f"• {name}")
            
            # If no stops in task details, fall back to stops data
            if not stops_text and self.stops_data:
                for stop in self.stops_data:
                    stop_id = stop.get('stop_id', 'Unknown')
                    name = stop.get('name', stop_id)
                    location = f"({stop.get('x_coordinate', '?')}, {stop.get('y_coordinate', '?')})"
                    rack_info = ""
                    if stop.get('rack_levels'):
                        rack_info = f", {stop.get('rack_levels')} levels"
                    stops_text.append(f"• {name} {location}{rack_info}")
            
            # Create the label with the collected stops or "No stops assigned"
            final_text = "\n".join(stops_text) if stops_text else "No stops assigned"
            stops_label = QLabel(final_text)
            stops_label.setStyleSheet("color: #cccccc;")
            stops_label.setWordWrap(True)
            grid_layout.addWidget(stops_label, row, 1)
        
        # Add additional task type specific details
        if task_type == 'Auditing' and self.task_details:
            if self.task_details.get('barcode'):
                row += 1
                grid_layout.addWidget(QLabel("Barcode:"), row, 0)
                barcode_label = QLabel(self.task_details['barcode'])
                barcode_label.setStyleSheet("color: #cccccc;")
                grid_layout.addWidget(barcode_label, row, 1)
            
            if self.task_details.get('csv_file_path'):
                row += 1
                grid_layout.addWidget(QLabel("CSV File:"), row, 0)
                file_label = QLabel(self.task_details['csv_file_path'])
                file_label.setStyleSheet("color: #cccccc;")
                file_label.setWordWrap(True)
                grid_layout.addWidget(file_label, row, 1)
        
        layout.addLayout(grid_layout)
        parent_layout.addWidget(frame)

    def create_section_frame(self, title):
        """Create a styled section frame"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #353535;
                border: 1px solid #555555;
                border-radius: 6px;
                margin: 5px;
                padding: 15px;
            }
        """)

        layout = QVBoxLayout(frame)

        # Section title
        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        title_label.setStyleSheet("color: #ff6b35; margin-bottom: 10px;")
        layout.addWidget(title_label)

        return frame, layout

    def create_basic_info_section(self, parent_layout):
        """Create basic information section"""
        frame, layout = self.create_section_frame("Basic Information")

        grid_layout = QGridLayout()

        # Task ID
        grid_layout.addWidget(QLabel("Task ID:"), 0, 0)
        self.task_id_label = QLabel()
        self.task_id_label.setStyleSheet("color: #cccccc; font-weight: bold;")
        grid_layout.addWidget(self.task_id_label, 0, 1)

        # Task Name
        grid_layout.addWidget(QLabel("Task Name:"), 1, 0)
        self.task_name_label = QLabel()
        self.task_name_label.setStyleSheet("color: #cccccc; font-weight: bold;")
        self.task_name_label.setWordWrap(True)
        grid_layout.addWidget(self.task_name_label, 1, 1)

        # Task Type
        grid_layout.addWidget(QLabel("Type:"), 2, 0)
        self.task_type_label = QLabel()
        self.task_type_label.setStyleSheet("color: #cccccc;")
        grid_layout.addWidget(self.task_type_label, 2, 1)



        layout.addLayout(grid_layout)
        parent_layout.addWidget(frame)

    def create_assignment_section(self, parent_layout):
        """Create assignment section"""
        frame, layout = self.create_section_frame("Assignment")

        grid_layout = QGridLayout()

        # Assigned Device(s)
        grid_layout.addWidget(QLabel("Assigned Device(s):"), 0, 0)
        self.assigned_device_label = QLabel()
        self.assigned_device_label.setStyleSheet("color: #cccccc;")
        self.assigned_device_label.setWordWrap(True)
        grid_layout.addWidget(self.assigned_device_label, 0, 1)

        # Assigned User
        grid_layout.addWidget(QLabel("Assigned User:"), 1, 0)
        self.assigned_user_label = QLabel()
        self.assigned_user_label.setStyleSheet("color: #cccccc;")
        self.assigned_user_label.setWordWrap(True)
        grid_layout.addWidget(self.assigned_user_label, 1, 1)

        # Created By
        grid_layout.addWidget(QLabel("Created By:"), 2, 0)
        self.created_by_label = QLabel()
        self.created_by_label.setStyleSheet("color: #cccccc;")
        grid_layout.addWidget(self.created_by_label, 2, 1)

        layout.addLayout(grid_layout)
        parent_layout.addWidget(frame)

    def create_live_tracking_section(self, parent_layout):
        """Create section showing live tracking information"""
        frame, layout = self.create_section_frame("📍 Live Tracking")
        self.live_tracking_blocks = {}
        self.live_tracking_devices = []

        # Determine assigned devices and resolve to device_id strings
        devices_list = []
        try:
            ids_str = str(self.task_data.get('assigned_device_ids') or '').strip()
            if ids_str:
                pk_ids = [s for s in ids_str.split(',') if s.strip()]
            else:
                single = self.task_data.get('assigned_device_id')
                pk_ids = [str(single)] if single else []

            all_devices = self.csv_handler.read_csv('devices') if self.csv_handler else []
            for pk in pk_ids:
                did = pk
                drow = next((d for d in all_devices if str(d.get('id')) == str(pk) or str(d.get('device_id')) == str(pk)), None)
                if drow and drow.get('device_id'):
                    did = drow.get('device_id')
                devices_list.append(str(did))
        except Exception:
            devices_list = []

        self.live_tracking_devices = devices_list

        if not devices_list:
            no_label = QLabel("No device(s) assigned")
            no_label.setStyleSheet("color: #cccccc;")
            layout.addWidget(no_label)
            parent_layout.addWidget(frame)
            return

        for idx, did in enumerate(devices_list):
            block = QFrame()
            block.setStyleSheet("QFrame { background-color: #2f2f2f; border: 1px solid #555555; border-radius: 4px; padding: 10px; }")
            blk_layout = QGridLayout(block)

            blk_layout.addWidget(QLabel("Device ID:"), 0, 0)
            id_val = QLabel(str(did))
            id_val.setStyleSheet("color: #cccccc; font-weight: bold;")
            blk_layout.addWidget(id_val, 0, 1)

            blk_layout.addWidget(QLabel("Device Current Location:"), 1, 0)
            loc_val = QLabel("Loading...")
            loc_val.setStyleSheet("color: #10B981;")
            blk_layout.addWidget(loc_val, 1, 1)

            blk_layout.addWidget(QLabel("Distance from Current Location:"), 2, 0)
            dist_val = QLabel("Loading...")
            dist_val.setStyleSheet("color: #3B82F6;")
            blk_layout.addWidget(dist_val, 2, 1)

            blk_layout.addWidget(QLabel("Direction:"), 3, 0)
            dir_val = QLabel("Loading...")
            dir_val.setStyleSheet("color: #8B5CF6;")
            blk_layout.addWidget(dir_val, 3, 1)

            layout.addWidget(block)

            self.live_tracking_blocks[did] = {
                'id_label': id_val,
                'location': loc_val,
                'distance': dist_val,
                'direction': dir_val
            }

        parent_layout.addWidget(frame)

        # Start periodic updates
        self.start_live_tracking_updates()

    def create_location_timing_section(self, parent_layout):
        """Create location and timing section"""
        frame, layout = self.create_section_frame("Location & Timing")

        grid_layout = QGridLayout()

        # From Location
        '''
        grid_layout.addWidget(QLabel("From Location:"), 0, 0)
        self.from_location_label = QLabel()
        self.from_location_label.setStyleSheet("color: #cccccc;")
        self.from_location_label.setWordWrap(True)
        grid_layout.addWidget(self.from_location_label, 0, 1)

        # To Location
        grid_layout.addWidget(QLabel("To Location:"), 1, 0)
        self.to_location_label = QLabel()
        self.to_location_label.setStyleSheet("color: #cccccc;")
        self.to_location_label.setWordWrap(True)
        grid_layout.addWidget(self.to_location_label, 1, 1)
        '''

        # Estimated Duration
        grid_layout.addWidget(QLabel("Estimated Duration:"), 2, 0)
        self.estimated_duration_label = QLabel()
        self.estimated_duration_label.setStyleSheet("color: #cccccc;")
        grid_layout.addWidget(self.estimated_duration_label, 2, 1)

        # Actual Duration
        grid_layout.addWidget(QLabel("Actual Duration:"), 3, 0)
        self.actual_duration_label = QLabel()
        self.actual_duration_label.setStyleSheet("color: #cccccc;")
        grid_layout.addWidget(self.actual_duration_label, 3, 1)

        layout.addLayout(grid_layout)
        parent_layout.addWidget(frame)

    '''
    def create_description_section(self, parent_layout):
        """Create description section"""
        frame, layout = self.create_section_frame("Description")

        self.description_text = QTextEdit()
        self.description_text.setReadOnly(True)
        self.description_text.setMaximumHeight(120)
        layout.addWidget(self.description_text)

        parent_layout.addWidget(frame)
        '''

    def configure_map_display(self, task_type, map_width, map_height):
        """Configure map display based on task type"""
        task_status = self.task_data.get('status', '').lower()
        if task_type == 'auditing':
            # For auditing tasks, show the complete map with all zones and stops
            if not self.map_data:
                self.logger.error("No map data available for auditing task")
                return
                
            # Get all zones and stops for the auditing map
            zones = self.csv_handler.read_csv('zones')
            stops = self.csv_handler.read_csv('stops')
            stop_groups = self.csv_handler.read_csv('stop_groups')
            
            # Filter data for the current map
            map_zones = [z for z in zones if str(z.get('map_id')) == str(self.map_data.get('id'))]
            map_stops = [s for s in stops if str(s.get('map_id')) == str(self.map_data.get('id'))]
            map_stop_groups = [sg for sg in stop_groups if str(sg.get('map_id')) == str(self.map_data.get('id'))]
            
            # Set the complete map data
            self.map_viewer.set_map_data(
                zones=map_zones,
                stops=map_stops,
                stop_groups=map_stop_groups,
                map_width=map_width,
                map_height=map_height,
                map_data=self.map_data,
                task_status=task_status
            )
            
            # Configure display settings for auditing tasks - show everything
            self.map_viewer.map_canvas.show_zones = True
            self.map_viewer.map_canvas.show_connections = True
            self.map_viewer.map_canvas.show_stops = True
            self.map_viewer.map_canvas.show_labels = True
            self.map_viewer.map_canvas.show_grid = True
            
            # Update the checkboxes to match
            self.map_viewer.show_zones_cb.setChecked(False)
            self.map_viewer.show_connections_cb.setChecked(False)
            self.map_viewer.show_stops_cb.setChecked(False)
            self.map_viewer.show_labels_cb.setChecked(True)
            self.map_viewer.show_grid_cb.setChecked(True)
        else:
            # For non-auditing tasks, show all map elements
            self.map_viewer.set_map_data(
                self.zones_data,
                self.stops_data,
                self.stop_groups_data,
                map_width=map_width,
                map_height=map_height,
                map_data=self.map_data
            )
            
            # Enable all visual elements for non-auditing tasks
            self.map_viewer.map_canvas.show_zones = True
            self.map_viewer.map_canvas.show_connections = True
            self.map_viewer.map_canvas.show_stops = True
            self.map_viewer.map_canvas.show_labels = True
            
            # Update the checkboxes to match
            self.map_viewer.show_zones_cb.setChecked(True)
            self.map_viewer.show_connections_cb.setChecked(True)
            self.map_viewer.show_stops_cb.setChecked(True)
            self.map_viewer.show_labels_cb.setChecked(True)
            
        # Fit the map to view
        self.map_viewer.fit_to_view()
        
        # Force a refresh
        self.map_viewer.map_canvas.update()
        self.map_viewer.fit_to_view()

    def create_status_section(self, parent_layout):
        """Create status and progress section"""
        frame, layout = self.create_section_frame("Status & Timeline")

        grid_layout = QGridLayout()

        # Status
        grid_layout.addWidget(QLabel("Status:"), 0, 0)
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #cccccc; font-weight: bold;")
        grid_layout.addWidget(self.status_label, 0, 1)

        # Created At
        grid_layout.addWidget(QLabel("Created:"), 1, 0)
        self.created_at_label = QLabel()
        self.created_at_label.setStyleSheet("color: #cccccc;")
        grid_layout.addWidget(self.created_at_label, 1, 1)

        # Started At
        grid_layout.addWidget(QLabel("Started:"), 2, 0)
        self.started_at_label = QLabel()
        self.started_at_label.setStyleSheet("color: #cccccc;")
        grid_layout.addWidget(self.started_at_label, 2, 1)

        # Completed At
        grid_layout.addWidget(QLabel("Completed:"), 3, 0)
        self.completed_at_label = QLabel()
        self.completed_at_label.setStyleSheet("color: #cccccc;")
        grid_layout.addWidget(self.completed_at_label, 3, 1)

        # Updated At
        '''
        grid_layout.addWidget(QLabel("Last Updated:"), 4, 0)
        self.updated_at_label = QLabel()
        self.updated_at_label.setStyleSheet("color: #cccccc;")
        grid_layout.addWidget(self.updated_at_label, 4, 1)
        '''

        layout.addLayout(grid_layout)
        parent_layout.addWidget(frame)

    def populate_data(self):
       """Populate dialog with task data"""
       if not self.task_data:
           return

       # Check if UI elements exist before populating
       if all([self.task_id_label, self.task_name_label, self.task_type_label]):
           # Basic information
           self.task_id_label.setText(str(self.task_data.get('task_id', 'N/A')))
           self.task_name_label.setText(str(self.task_data.get('task_name', 'N/A')))
           self.task_type_label.setText(str(self.task_data.get('task_type', 'N/A')).title())

       # Check if assignment labels exist
       if all([self.assigned_device_label, self.assigned_user_label, self.created_by_label]):
           # Assignment - devices (support multiple)
           devices = []
           try:
               devices = self.csv_handler.read_csv('devices')
           except Exception:
               devices = []
           device_text = 'Unassigned'
           multi_ids = [s.strip() for s in str(self.task_data.get('assigned_device_ids') or '').split(',') if s.strip()]
           if multi_ids:
               names = []
               for did in multi_ids:
                   d = next((x for x in devices if str(x.get('id')) == str(did) or str(x.get('device_id')) == str(did)), None)
                   if d:
                       names.append(f"{d.get('device_name','')} ({d.get('device_id','')})")
                   else:
                       names.append(str(did))
               device_text = ", ".join(names)
           else:
               device_id = self.task_data.get('assigned_device_id', 'Unassigned')
               if device_id and device_id != 'Unassigned':
                   try:
                       d = next((x for x in devices if str(x.get('id')) == str(device_id) or str(x.get('device_id')) == str(device_id)), None)
                       if d:
                           device_text = f"{d.get('device_name', '')} ({d.get('device_id', '')})"
                       else:
                           device_text = f"Device: {device_id}"
                   except Exception:
                       device_text = str(device_id)
               else:
                   device_text = 'Unassigned'
           self.assigned_device_label.setText(device_text)

           user_id = self.task_data.get('assigned_user_id', 'Unassigned')
           if user_id and user_id != 'Unassigned':
               try:
                   users = self.csv_handler.read_csv('users')
                   user = next((u for u in users if str(u.get('id')) == str(user_id)), None)
                   if user:
                       user_text = user.get('username', f"User ID: {user_id}")
                   else:
                       user_text = f"User ID: {user_id}"
               except Exception:
                   user_text = str(user_id)
           else:
               user_text = 'Unassigned'
           self.assigned_user_label.setText(user_text)

           created_by = self.task_data.get('created_by', 'System')
           self.created_by_label.setText(str(created_by))

       # Location and timing
       #self.from_location_label.setText(self.task_data.get('from_location', 'N/A'))
       #self.to_location_label.setText(self.task_data.get('to_location', 'N/A'))

       # Check if duration labels exist
       if all([self.estimated_duration_label, self.actual_duration_label]):
           estimated_duration = self.task_data.get('estimated_duration')
           if estimated_duration:
               self.estimated_duration_label.setText(f"{estimated_duration} minutes")
           else:
               self.estimated_duration_label.setText('N/A')

           actual_duration = self.task_data.get('actual_duration')
           if actual_duration:
               self.actual_duration_label.setText(f"{actual_duration} minutes")
           else:
               self.actual_duration_label.setText('N/A')

       # Check if status label exists
       if self.status_label:
           # Status and timeline
           status = str(self.task_data.get('status', 'unknown')).title()
           self.status_label.setText(status)

           # Apply status color
           status_colors = {
               'Pending': '#3B82F6',
               'Running': '#10B981',
               'Completed': '#8B5CF6',
               'Failed': '#EF4444',
               'Cancelled': '#6B7280'
           }
           color = status_colors.get(status, '#cccccc')
           self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")

       # Check if timestamp labels exist
       if all([self.created_at_label, self.started_at_label, self.completed_at_label]):
           # Timestamps
           def format_timestamp(timestamp):
               if timestamp:
                   return timestamp.replace('T', ' ')[:19] if 'T' in timestamp else timestamp[:19]
               return 'N/A'

           self.created_at_label.setText(format_timestamp(self.task_data.get('created_at')))
           self.started_at_label.setText(format_timestamp(self.task_data.get('started_at')))
           self.completed_at_label.setText(format_timestamp(self.task_data.get('completed_at')))
       #self.updated_at_label.setText(format_timestamp(self.task_data.get('updated_at')))
       
       # Display map data if map viewer exists and we have map data
       if self.map_viewer and self.map_data:
           # Get map ID and task type
           map_id = self.task_data.get('map_id')
           task_type = self.task_data.get('task_type', '').lower()
           
           # Set map data in the viewer
           # Debug log the data being passed

           # Get map dimensions from map data if available, otherwise use defaults
           map_width = int(self.map_data.get('width', 1000)) if self.map_data else 1000
           map_height = int(self.map_data.get('height', 800)) if self.map_data else 800
           

           
           if task_type == 'auditing':

               # For auditing tasks, load all map elements
               try:
                   # Get all zones and stops for the map
                   zones = self.csv_handler.read_csv('zones')
                   stops = self.csv_handler.read_csv('stops')
                   stop_groups = self.csv_handler.read_csv('stop_groups')
                   
                   # Filter for current map
                   map_zones = [z for z in zones if str(z.get('map_id')) == str(self.map_data.get('id'))]
                   map_stops = [s for s in stops if str(s.get('map_id')) == str(self.map_data.get('id'))]
                   map_stop_groups = [sg for sg in stop_groups if str(sg.get('map_id')) == str(self.map_data.get('id'))]
                   
                   
                   # Set complete map data
                   self.map_viewer.set_map_data(
                       zones=map_zones,
                       stops=map_stops,
                       stop_groups=map_stop_groups,
                       map_width=map_width,
                       map_height=map_height,
                       map_data=self.map_data
                   )
                   
                   # Configure display settings - show everything for auditing
                   self.map_viewer.map_canvas.show_zones = True
                   self.map_viewer.map_canvas.show_connections = True
                   self.map_viewer.map_canvas.show_stops = True
                   self.map_viewer.map_canvas.show_labels = True
                   self.map_viewer.map_canvas.show_grid = True
                   
                   # Update checkboxes
                   if hasattr(self.map_viewer, 'show_zones_cb'):
                       self.map_viewer.show_zones_cb.setChecked(True)
                   if hasattr(self.map_viewer, 'show_connections_cb'):
                       self.map_viewer.show_connections_cb.setChecked(True)
                   if hasattr(self.map_viewer, 'show_stops_cb'):
                       self.map_viewer.show_stops_cb.setChecked(True)
                   if hasattr(self.map_viewer, 'show_labels_cb'):
                       self.map_viewer.show_labels_cb.setChecked(True)
                   if hasattr(self.map_viewer, 'show_grid_cb'):
                       self.map_viewer.show_grid_cb.setChecked(True)
                       
                   # Force refresh
                   self.map_viewer.map_canvas.update()
                   self.map_viewer.fit_to_view()
                   
               except Exception as e:
                   print(f"DEBUG - Error configuring auditing map: {str(e)}")
                   self.logger.error(f"Error configuring map for auditing task: {str(e)}")
           else:
               # For non-auditing tasks, check for required data
               if not self.zones_data:
                   self.logger.warning("No zones data available for display")
               if not self.stops_data:
                   self.logger.warning("No stops data available for display")
                   
               # Set all map data for non-auditing tasks
               task_status = self.task_data.get('status', '').lower()  # Get task status here
               self.map_viewer.set_map_data(
                   zones=self.zones_data,
                   stops=self.stops_data,
                   stop_groups=self.stop_groups_data,
                   map_width=map_width,
                   map_height=map_height,
                   map_data=self.map_data,
                   task_status=task_status
               )
               
               # Enable all visual elements for non-auditing tasks
               self.map_viewer.map_canvas.show_zones = True
               self.map_viewer.map_canvas.show_connections = True
               self.map_viewer.map_canvas.show_stops = True
               self.map_viewer.map_canvas.show_labels = True
               
               # Update the checkboxes to match
               self.map_viewer.show_zones_cb.setChecked(True)
               self.map_viewer.show_connections_cb.setChecked(True)
               self.map_viewer.show_stops_cb.setChecked(True)
               self.map_viewer.show_labels_cb.setChecked(True)
           
           # Fit the map to view
           self.map_viewer.fit_to_view()
           
           # Force a refresh
           self.map_viewer.map_canvas.update()
           self.map_viewer.fit_to_view()