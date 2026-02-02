from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QComboBox, QMessageBox, QFrame, QSplitter, QTableWidgetItem, QScrollArea)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from .add_device_dialog import AddDeviceDialog
from .reset_device_dialog import ResetDeviceDialog
from ui.common.table_widget import DataTableWidget
from api.client import APIClient
from api.devices import DevicesAPI
from data_manager.csv_handler import CSVHandler
from data_manager.device_data_handler import DeviceDataHandler
from data_manager.sync_manager import SyncManager
from config.constants import DEVICE_STATUS
from utils.logger import setup_logger
from datetime import datetime
from sync_device_locations import DeviceLocationSyncer
from utils.device_movement_tracker import DeviceMovementTracker
from utils.zone_navigation_manager import get_zone_navigation_manager

class DeviceListWidget(QWidget):
    device_updated = pyqtSignal()

    def __init__(self, api_client: APIClient, csv_handler: CSVHandler):
        super().__init__()
        self.api_client = api_client
        self.csv_handler = csv_handler
        self.devices_api = DevicesAPI(api_client)
        self.sync_manager = SyncManager(api_client, csv_handler)
        self.logger = setup_logger('device_list')
        self.device_data_handler = DeviceDataHandler()

        self.current_devices = []

        self.setup_ui()
        self.setup_timer()
        self.refresh_data()

    def setup_ui(self):
        """Setup device list UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()

        #title = QLabel("Device Management")
        #title.setFont(QFont("Arial", 20, QFont.Bold))
        #title.setStyleSheet("color: #ffffff;")
        #header_layout.addWidget(title)

        header_layout.addStretch()

        # Status filter
        filter_label = QLabel("Filter by Status:")
        filter_label.setStyleSheet("color: #cccccc;")
        header_layout.addWidget(filter_label)

        self.status_filter = QComboBox()
        self.status_filter.addItem("All Statuses", "")
        for key, value in DEVICE_STATUS.items():
            self.status_filter.addItem(value, key)
        self.status_filter.currentTextChanged.connect(self.filter_devices)
        self.status_filter.setStyleSheet("""
            QComboBox {
                background-color: #404040;
                border: 1px solid #555555;
                padding: 6px;
                border-radius: 4px;
                color: #ffffff;
                min-width: 120px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #404040;
                color: #ffffff;
                selection-background-color: #ff6b35;
            }
        """)
        header_layout.addWidget(self.status_filter)

        # Add device button
        add_btn = QPushButton("➕ Add Device")
        add_btn.clicked.connect(self.show_add_device_dialog)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff6b35;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e55a2b;
            }
        """)
        header_layout.addWidget(add_btn)

        self.reset_device_btn = QPushButton("Reset Device")
        self.reset_device_btn.setEnabled(False)
        self.reset_device_btn.clicked.connect(self.reset_selected_device)
        self.reset_device_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #666666; }
            QPushButton:disabled { background-color: #555555; color: #888888; }
        """)
        header_layout.addWidget(self.reset_device_btn)

        layout.addLayout(header_layout)

        # Main content area
        splitter = QSplitter(Qt.Horizontal)

        # Devices table
        self.devices_table = DataTableWidget([
            "Device ID", "Device Name", "Device Model", "Forward (m/s)", "Turning (m/s)", "Status", "Battery %", "Current Location", "Current Map", "Facing Direction",
            "Distance (mm)", "Diameter (mm)", "Dist. Wheels (m)", "Length (m)", "Width (m)", "Height (m)", "Lifting (m)",
            "Created"
        ], searchable=True, selectable=True)
        self.devices_table.row_selected.connect(self.on_device_selected)
        self.devices_table.row_double_clicked.connect(self.on_device_double_clicked)
        splitter.addWidget(self.devices_table)
        # Column index for quick updates
        self.FACING_COL_INDEX = 9

        # Device details panel
        self.create_details_panel(splitter)

        # Set splitter proportions
        splitter.setSizes([730, 270])
        layout.addWidget(splitter)

        # Action buttons
        self.create_action_buttons(layout)

    def create_details_panel(self, parent):
        """Create device details panel"""
        details_frame = QFrame()
        details_frame.setStyleSheet("""
            QFrame {
                background-color: #353535;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px;
            }
        """)
        details_layout = QVBoxLayout(details_frame)

        # Title
        details_title = QLabel("Device Details")
        details_title.setFont(QFont("Arial", 12, QFont.Bold))
        details_title.setStyleSheet("color: #ffffff; margin-bottom: 5px;")
        details_layout.addWidget(details_title)

        # Device info labels
        self.device_model_label = QLabel("Device Model: -")
        self.device_id_label = QLabel("Device ID: -")
        self.device_name_label = QLabel("Device Name: -")
        self.device_battery_label = QLabel("Battery: -")
        self.device_status_label = QLabel("Status: -")
        self.device_location_label = QLabel("Current Location: -")
        self.device_facing_label = QLabel("Facing Direction: -")
        self.device_distance_label = QLabel("Distance: -")
        self.device_forward_speed_label = QLabel("Forward Speed (m/s): -")
        self.device_turning_speed_label = QLabel("Turning Speed (m/s): -")
        self.device_wheel_diameter_label = QLabel("Wheel Diameter (mm): -")
        self.device_dbw_label = QLabel("Distance Between Wheels (m): -")
        self.device_length_label = QLabel("Length (m): -")
        self.device_width_label = QLabel("Width (m): -")
        self.device_height_label = QLabel("Height (m): -")
        self.device_lifting_height_label = QLabel("Lifting Height (m): -")
        self.device_created_label = QLabel("Created: -")
        self.device_updated_label = QLabel("Updated: -")

        # Add in required order
        info_labels = [
            self.device_model_label,
            self.device_id_label,
            self.device_name_label,
            self.device_battery_label,
            self.device_status_label,
            self.device_location_label,
            self.device_facing_label,
            self.device_distance_label,
            self.device_forward_speed_label,
            self.device_turning_speed_label,
            self.device_wheel_diameter_label,
            self.device_dbw_label,
            self.device_lifting_height_label,
            self.device_length_label,
            self.device_width_label,
            self.device_height_label,
            self.device_created_label,
            self.device_updated_label
        ]

        for label in info_labels:
            label.setStyleSheet("color: #cccccc; margin: 3px 0;")
            label.setWordWrap(True)
            details_layout.addWidget(label)

        details_layout.addStretch()

        # Device actions
        self.edit_device_btn = QPushButton("Edit Device")
        self.edit_device_btn.clicked.connect(self.edit_selected_device)
        self.edit_device_btn.setEnabled(False)

        self.delete_device_btn = QPushButton("Delete Device")
        self.delete_device_btn.clicked.connect(self.delete_selected_device)
        self.delete_device_btn.setEnabled(False)
        self.delete_device_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
        """)

        details_layout.addWidget(self.edit_device_btn)
        details_layout.addWidget(self.delete_device_btn)

        # Make details scrollable
        details_scroll = QScrollArea()
        details_scroll.setWidgetResizable(True)
        details_scroll.setStyleSheet("QScrollArea { background-color: transparent; }")
        details_scroll.setWidget(details_frame)

        parent.addWidget(details_scroll)

    def create_action_buttons(self, parent_layout):
        """Create action buttons"""
        action_layout = QHBoxLayout()

        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        action_layout.addWidget(refresh_btn)

        # Sync button
        sync_btn = QPushButton("🔄 Sync with API")
        sync_btn.clicked.connect(self.sync_with_api)
        action_layout.addWidget(sync_btn)
        
        # Distance sync button
        distance_sync_btn = QPushButton("📏 Sync Distance")
        distance_sync_btn.clicked.connect(self.sync_device_distances)
        distance_sync_btn.setToolTip("Sync device distances from log files")
        action_layout.addWidget(distance_sync_btn)

        action_layout.addStretch()

        # Export button
        export_btn = QPushButton("📤 Export CSV")
        export_btn.clicked.connect(self.export_devices)
        action_layout.addWidget(export_btn)

        # Button styling
        buttons = [refresh_btn, sync_btn, distance_sync_btn, export_btn]
        for btn in buttons:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #555555;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    margin: 2px;
                }
                QPushButton:hover {
                    background-color: #666666;
                }
            """)

        parent_layout.addLayout(action_layout)

    def setup_timer(self):
        """Setup refresh timer"""
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(30000)  # Refresh every 30 seconds
        # Fast timer to keep Facing Direction column in sync with live data
        self.facing_timer = QTimer()
        self.facing_timer.timeout.connect(self.update_facing_column)
        self.facing_timer.start(1000)  # Update facing every second

    def refresh_data(self):
        """Refresh device data"""
        self.logger.info("Refreshing device data...")
        self.load_devices()

    def load_devices(self):
        """Load devices from API or CSV"""
        try:
            # Try API first
            if self.api_client.is_authenticated():
                response = self.devices_api.list_devices()
                if 'error' not in response:
                    devices_data = response.get('results', response) if isinstance(response, dict) else response
                    self.current_devices = devices_data
                    self.populate_devices_table(devices_data)
                    self.logger.info(f"Loaded {len(devices_data)} devices from API")
                    return

            # Fallback to CSV
            devices = self.csv_handler.read_csv('devices')
            self.current_devices = devices
            self.populate_devices_table(devices)
            self.logger.info(f"Loaded {len(devices)} devices from CSV")

        except Exception as e:
            self.logger.error(f"Error loading devices: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load devices: {e}")
            # Try to repair CSV if loading failed
            self.csv_handler.repair_csv_file('devices')
            # Try loading again after repair
            try:
                devices = self.csv_handler.read_csv('devices')
                self.current_devices = devices
                self.populate_devices_table(devices)
                self.logger.info(f"Loaded {len(devices)} devices from repaired CSV")
            except Exception as repair_error:
                self.logger.error(f"Even repair failed: {repair_error}")
                self.current_devices = []
                self.populate_devices_table([])

    def populate_devices_table(self, devices):
        """Populate devices table"""
        self.devices_table.clear_data()
        # Track the list currently displayed (after filters)
        self.displayed_devices = list(devices)

        # Build maps lookup for Current Map column
        maps_lookup = {}
        try:
            maps_data = self.csv_handler.read_csv('maps')
            for m in maps_data:
                maps_lookup[str(m.get('id', ''))] = m.get('name', '')
        except Exception:
            pass

        for device in devices:
            battery_level = device.get('battery_level', 0)
            battery_text = f"{battery_level}%" if battery_level is not None else "N/A"
            
            # Format distance
            distance = device.get('distance', 0)
            distance_text = f"{float(distance):.2f} mm" if distance and str(distance) != '0.00' else "0.00 mm"

            # Speeds (convert from mm/s to m/s)
            try:
                fs_val = device.get('forward_speed', '')
                forward_speed_text = f"{float(fs_val) / 1000.0:.2f}" if fs_val not in (None, '') else "N/A"
            except Exception:
                forward_speed_text = "N/A"
            try:
                ts_val = device.get('turning_speed', '')
                turning_speed_text = f"{float(ts_val) / 1000.0:.2f}" if ts_val not in (None, '') else "N/A"
            except Exception:
                turning_speed_text = "N/A"

            # Compute current facing direction via DeviceDataHandler (live from logs/nav)
            facing_text = "N/A"
            try:
                dev_id = device.get('device_id', '')
                if dev_id:
                    zinfo = self.device_data_handler.get_zone_transition_info(dev_id)
                    facing = zinfo.get('facing_direction') if isinstance(zinfo, dict) else None
                    if isinstance(facing, str) and facing:
                        facing_text = facing.title()
            except Exception:
                facing_text = "N/A"
            
            # Map name lookup
            current_map_id = str(device.get('current_map', ''))
            current_map_name = maps_lookup.get(current_map_id, '')

            row_data = [
                device.get('device_id', ''),
                device.get('device_name', ''),
                device.get('device_model', ''),
                forward_speed_text,
                turning_speed_text,
                device.get('status', '').title(),
                battery_text,
                device.get('current_location', 'N/A'),
                current_map_name,
                facing_text,
                distance_text,
                # New fields after Facing Direction
                f"{float(device.get('wheel_diameter', 0) or 0):.2f}" if str(device.get('wheel_diameter', '')).strip() != '' else "",
                f"{float(device.get('distance_between_wheels', 0) or 0):.2f}" if str(device.get('distance_between_wheels', '')).strip() != '' else "",
                f"{float(device.get('length', 0) or 0):.2f}" if str(device.get('length', '')).strip() != '' else "",
                f"{float(device.get('width', 0) or 0):.2f}" if str(device.get('width', '')).strip() != '' else "",
                f"{float(device.get('height', 0) or 0):.2f}" if str(device.get('height', '')).strip() != '' else "",
                f"{float(device.get('lifting_height', 0) or 0):.2f}" if str(device.get('lifting_height', '')).strip() != '' else "",
                device.get('created_at', '')[:10] if device.get('created_at') else ''
            ]
            self.devices_table.add_row(row_data)

    def filter_devices(self):
        """Filter devices by status"""
        selected_status = self.status_filter.currentData()

        if not selected_status:
            # Show all devices
            self.populate_devices_table(self.current_devices)
        else:
            # Filter by status
            filtered_devices = [d for d in self.current_devices
                                if d.get('status', '').lower() == selected_status]
            self.populate_devices_table(filtered_devices)

    def show_add_device_dialog(self):
        """Show add device dialog"""
        dialog = AddDeviceDialog(self)
        if dialog.exec_() == AddDeviceDialog.Accepted:
            device_data = dialog.get_device_data()
            self.add_device(device_data)

    def add_device(self, device_data):
        """Add new device"""
        try:
            # Validate the data first
            validation_result = self.csv_handler.validate_csv_data('devices', device_data)

            if not validation_result['valid']:
                error_msg = '\n'.join(validation_result['errors'])
                QMessageBox.critical(self, "Validation Error", f"Cannot save device:\n{error_msg}")
                return

            # Use validated data
            device_data = validation_result['data']

            # Try API first
            if self.api_client.is_authenticated():
                response = self.devices_api.create_device(device_data)
                if 'error' not in response:
                    QMessageBox.information(self, "Success", "Device added successfully!")
                    self.refresh_data()
                    return
                else:
                    self.logger.warning(f"API failed: {response['error']}, falling back to CSV")

            # Fallback to CSV - ensure ID is generated
            if 'id' not in device_data or not device_data['id']:
                device_data['id'] = self.csv_handler.get_next_id('devices')

            # Ensure timestamps
            current_time = datetime.now().isoformat()
            device_data['created_at'] = current_time
            device_data['updated_at'] = current_time
            # Debug logging
            self.logger.info(f"Attempting to save device data: {device_data}")

            # Save to CSV
            if self.csv_handler.append_to_csv('devices', device_data):
                QMessageBox.information(self, "Success",
                                        f"Device '{device_data['device_name']}' added to local storage!")

                # Immediately refresh to show the new device
                self.refresh_data()

                # Log success
                self.logger.info(f"Successfully added device: {device_data['device_id']}")

                # Ensure per-device task CSV exists: '<device_id>_task.csv'
                try:
                    dev_id_str = device_data.get('device_id')
                    if dev_id_str:
                        self.device_data_handler.create_device_task_file(dev_id_str)
                except Exception as e:
                    self.logger.warning(f"Could not create per-device task file for {device_data.get('device_id')}: {e}")
            else:
                raise Exception("Failed to save to CSV - check file permissions and disk space")

        except Exception as e:
            self.logger.error(f"Error adding device: {e}")
            QMessageBox.critical(self, "Error", f"Failed to add device: {e}")

    def on_device_selected(self, row):
        """Handle device selection"""
        if row < len(self.current_devices):
            device = self.current_devices[row]
            self.show_device_details(device)
            self.edit_device_btn.setEnabled(True)
            self.delete_device_btn.setEnabled(True)
            if hasattr(self, 'reset_device_btn'):
                self.reset_device_btn.setEnabled(True)

    def on_device_double_clicked(self, row):
        """Handle device double click"""
        self.edit_selected_device()

    def show_device_details(self, device):
        """Show device details in side panel"""
        self.device_id_label.setText(f"Device ID: {device.get('device_id', 'N/A')}")
        self.device_name_label.setText(f"Device Name: {device.get('device_name', 'N/A')}")
        self.device_model_label.setText(f"Device Model: {device.get('device_model', 'N/A')}")
        self.device_status_label.setText(f"Status: {device.get('status', 'N/A').title()}")

        # Speeds in details (convert from mm/s to m/s)
        try:
            fs = device.get('forward_speed', '')
            self.device_forward_speed_label.setText(f"Forward Speed (m/s): {float(fs)/1000.0:.2f}" if fs not in (None, '') else "Forward Speed (m/s): N/A")
        except Exception:
            self.device_forward_speed_label.setText("Forward Speed (m/s): N/A")
        try:
            ts = device.get('turning_speed', '')
            self.device_turning_speed_label.setText(f"Turning Speed (m/s): {float(ts)/1000.0:.2f}" if ts not in (None, '') else "Turning Speed (m/s): N/A")
        except Exception:
            self.device_turning_speed_label.setText("Turning Speed (m/s): N/A")

        # New fields in details
        def fmt_f(v):
            try:
                if v in (None, ''):
                    return "N/A"
                return f"{float(v):.2f}"
            except Exception:
                return "N/A"
        def fmt_i(v):
            try:
                if v in (None, ''):
                    return "N/A"
                return f"{int(float(v))}"
            except Exception:
                return "N/A"
        self.device_wheel_diameter_label.setText(f"Wheel Diameter (mm): {fmt_f(device.get('wheel_diameter', ''))}")
        self.device_dbw_label.setText(f"Distance Between Wheels (m): {fmt_f(device.get('distance_between_wheels', ''))}")
        self.device_length_label.setText(f"Length (m): {fmt_f(device.get('length', ''))}")
        self.device_width_label.setText(f"Width (m): {fmt_f(device.get('width', ''))}")
        self.device_height_label.setText(f"Height (m): {fmt_f(device.get('height', ''))}")
        self.device_lifting_height_label.setText(f"Lifting Height (m): {fmt_f(device.get('lifting_height', ''))}")

        battery = device.get('battery_level', 0)
        battery_text = f"{battery}%" if battery is not None else "N/A"
        self.device_battery_label.setText(f"Battery: {battery_text}")

        current_location = device.get('current_location', 'N/A')
        self.device_location_label.setText(f"Current Location: {current_location}")
        # Facing direction (live)
        facing_text = "N/A"
        try:
            dev_id = device.get('device_id', '')
            if dev_id:
                zinfo = self.device_data_handler.get_zone_transition_info(dev_id)
                facing = zinfo.get('facing_direction') if isinstance(zinfo, dict) else None
                if isinstance(facing, str) and facing:
                    facing_text = facing.title()
        except Exception:
            facing_text = "N/A"
        self.device_facing_label.setText(f"Facing Direction: {facing_text}")
        
        # Format and display distance
        distance = device.get('distance', 0)
        distance_text = f"{float(distance):.2f} mm" if distance and str(distance) != '0.00' else "0.00 mm"
        self.device_distance_label.setText(f"Distance: {distance_text}")

        self.device_created_label.setText(
            f"Created: {device.get('created_at', 'N/A')[:19] if device.get('created_at') else 'N/A'}")
        self.device_updated_label.setText(
            f"Updated: {device.get('updated_at', 'N/A')[:19] if device.get('updated_at') else 'N/A'}")

    def update_facing_column(self):
        """Keep the Facing Direction column synchronized with live facing data."""
        try:
            if not hasattr(self, 'displayed_devices') or not self.displayed_devices:
                return
            table = self.devices_table.table
            # For each displayed device, update the facing cell by matching Device ID in column 0
            for device in self.displayed_devices:
                dev_id = device.get('device_id', '')
                if not dev_id:
                    continue
                # Compute facing
                facing_text = "N/A"
                try:
                    zinfo = self.device_data_handler.get_zone_transition_info(dev_id)
                    facing = zinfo.get('facing_direction') if isinstance(zinfo, dict) else None
                    if isinstance(facing, str) and facing:
                        facing_text = facing.title()
                except Exception:
                    facing_text = "N/A"
                # Find row by Device ID in column 0
                row_to_update = None
                for row in range(table.rowCount()):
                    item = table.item(row, 0)
                    if item and item.text() == dev_id:
                        row_to_update = row
                        break
                if row_to_update is None:
                    continue
                # Update facing cell
                existing_item = table.item(row_to_update, self.FACING_COL_INDEX)
                if existing_item is None:
                    existing_item = QTableWidgetItem()
                    existing_item.setFlags(existing_item.flags() & ~Qt.ItemIsEditable)
                    table.setItem(row_to_update, self.FACING_COL_INDEX, existing_item)
                if existing_item.text() != facing_text:
                    existing_item.setText(facing_text)
            # Also update the details panel's facing label for the currently selected row
            selected_row = table.currentRow()
            if selected_row is not None and selected_row >= 0:
                sel_item = table.item(selected_row, 0)
                sel_dev_id = sel_item.text() if sel_item else None
                if sel_dev_id:
                    try:
                        zinfo_sel = self.device_data_handler.get_zone_transition_info(sel_dev_id)
                        facing_sel = zinfo_sel.get('facing_direction') if isinstance(zinfo_sel, dict) else None
                        facing_sel_text = facing_sel.title() if isinstance(facing_sel, str) and facing_sel else "N/A"
                    except Exception:
                        facing_sel_text = "N/A"
                    if hasattr(self, 'device_facing_label'):
                        self.device_facing_label.setText(f"Facing Direction: {facing_sel_text}")
        except Exception:
            # Non-fatal: keep UI responsive even if a row fails to update
            pass

    def edit_selected_device(self):
        """Edit selected device"""
        selected_row_data = self.devices_table.get_selected_row_data()
        if selected_row_data:
            current_row = self.devices_table.table.currentRow()
            if current_row < len(self.current_devices):
                device = self.current_devices[current_row]
                dialog = AddDeviceDialog(self, device)
                if dialog.exec_() == AddDeviceDialog.Accepted:
                    updated_data = dialog.get_device_data()
                    self.update_device(device.get('id'), updated_data)

    def update_device(self, device_id, updated_data):
        """Update device"""
        try:
            # Add updated timestamp
            updated_data['updated_at'] = datetime.now().isoformat()

            # Try API first
            if self.api_client.is_authenticated():
                response = self.devices_api.update_device(device_id, updated_data)
                if 'error' not in response:
                    QMessageBox.information(self, "Success", "Device updated successfully!")
                    self.refresh_data()
                    return
                else:
                    self.logger.warning(f"API failed: {response['error']}, falling back to CSV")

            # Fallback to CSV
            if self.csv_handler.update_csv_row('devices', device_id, updated_data):
                QMessageBox.information(self, "Success", "Device updated in local storage!")
                self.refresh_data()
                self.logger.info(f"Successfully updated device: {device_id}")
            else:
                raise Exception("Failed to update CSV")

        except Exception as e:
            self.logger.error(f"Error updating device: {e}")
            QMessageBox.critical(self, "Error", f"Failed to update device: {e}")

    def delete_selected_device(self):
        """Delete selected device"""
        current_row = self.devices_table.table.currentRow()
        if current_row < len(self.current_devices):
            device = self.current_devices[current_row]
            device_name = device.get('device_name', 'Unknown')

            reply = QMessageBox.question(
                self, "Confirm Delete",
                f"Are you sure you want to delete device '{device_name}'?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.delete_device(device.get('id'))

    def reset_selected_device(self):
        """Reset the selected device's state: set location via popup and lock facing to North."""
        try:
            current_row = self.devices_table.table.currentRow()
            if current_row < 0 or current_row >= len(self.current_devices):
                QMessageBox.information(self, "Reset Device", "Please select a device from the table first.")
                return

            device = self.current_devices[current_row]
            device_id = device.get('device_id', '')
            if not device_id:
                QMessageBox.warning(self, "Reset Device", "Selected row has no device_id.")
                return

            current_loc = device.get('current_location', '')
            dlg = ResetDeviceDialog(self, current_loc)
            if dlg.exec_() != ResetDeviceDialog.Accepted:
                return

            new_location = dlg.get_selected_location()
            new_map = dlg.get_selected_map()
            
            if not new_location:
                QMessageBox.warning(self, "Reset Device", "Please select a location.")
                return

            # Update current_map and current_location in the devices CSV
            # Using device.get('id') which is the primary key for update_csv_row
            row_id = device.get('id')
            if row_id and new_map:
                try:
                    update_payload = {
                        'current_map': str(new_map),
                        'current_location': str(new_location),
                        'updated_at': datetime.now().isoformat()
                    }
                    if self.csv_handler.update_csv_row('devices', row_id, update_payload):
                        self.logger.info(f"Successfully updated devices.csv for {device_id} (ID: {row_id})")
                    else:
                        self.logger.warning(f"Failed to update devices.csv for {device_id} (ID: {row_id})")
                except Exception as _me:
                    self.logger.warning(f"Error updating devices table for {device_id}: {_me}")

            # Also log the movement to maintain history and trigger facing reset
            success, error = DeviceMovementTracker.log_device_movement(
                device_id=device_id,
                right_drive=0,
                left_drive=0,
                right_motor=0.0,
                left_motor=0.0,
                current_location=str(new_location)
            )
            if not success:
                QMessageBox.critical(self, "Reset Device", f"Failed to write device log: {error}")
                return

            try:
                nav = get_zone_navigation_manager()
                nav.set_initial_direction(device_id, str(new_location) or '', 'north')
            except Exception as _e:
                # Non-fatal
                self.logger.warning(f"Failed to set initial facing for {device_id}: {_e}")

            try:
                syncer = DeviceLocationSyncer()
                syncer.sync_device_locations()
            except Exception as _se:
                # Non-fatal; UI will still refresh from existing data
                self.logger.warning(f"Device sync after reset failed: {_se}")

            QMessageBox.information(self, "Reset Device", f"Device '{device_id}' has been reset to location {new_location}")
            self.refresh_data()
        except Exception as e:
            self.logger.error(f"Error during device reset: {e}")
            QMessageBox.critical(self, "Reset Device", f"Error: {e}")

    def delete_device(self, device_id):
        """Delete device"""
        try:
            # Capture device_id string for file cleanup before deletion
            device_id_str = None
            for d in self.current_devices:
                if str(d.get('id')) == str(device_id):
                    device_id_str = d.get('device_id')
                    break

            # Try API first
            if self.api_client.is_authenticated():
                response = self.devices_api.delete_device(device_id)
                if 'error' not in response:
                    QMessageBox.information(self, "Success", "Device deleted successfully!")
                    
                    # Cleanup files if we have the device_id string
                    if device_id_str:
                        self.device_data_handler.delete_device_files(device_id_str)
                        
                    self.refresh_data()
                    self.clear_device_details()
                    return
                else:
                    self.logger.warning(f"API failed: {response['error']}, falling back to CSV")

            # Fallback to CSV
            if self.csv_handler.delete_csv_row('devices', device_id):
                QMessageBox.information(self, "Success", "Device deleted from local storage!")
                
                # Cleanup files if we have the device_id string
                if device_id_str:
                    self.device_data_handler.delete_device_files(device_id_str)
                    
                self.refresh_data()
                self.clear_device_details()
                self.logger.info(f"Successfully deleted device: {device_id}")
            else:
                raise Exception("Failed to delete from CSV")

        except Exception as e:
            self.logger.error(f"Error deleting device: {e}")
            QMessageBox.critical(self, "Error", f"Failed to delete device: {e}")

    def clear_device_details(self):
        """Clear device details panel"""
        self.device_id_label.setText("Device ID: -")
        self.device_name_label.setText("Device Name: -")
        self.device_model_label.setText("Device Model: -")
        self.device_status_label.setText("Status: -")
        self.device_lifting_height_label.setText("Lifting Height (m): -")
        self.device_length_label.setText("Length (m): -")
        self.device_width_label.setText("Width (m): -")
        self.device_height_label.setText("Height (m): -")
        self.device_battery_label.setText("Battery: -")
        self.device_location_label.setText("Current Location: -")
        if hasattr(self, 'device_facing_label'):
            self.device_facing_label.setText("Facing Direction: -")
        self.device_distance_label.setText("Distance: -")
        self.device_created_label.setText("Created: -")
        self.device_updated_label.setText("Updated: -")

        self.edit_device_btn.setEnabled(False)
        self.delete_device_btn.setEnabled(False)
        if hasattr(self, 'reset_device_btn'):
            self.reset_device_btn.setEnabled(False)

    def sync_with_api(self):
        """Sync devices with API"""
        if not self.api_client.is_authenticated():
            QMessageBox.warning(self, "Not Connected", "Please connect to API first")
            return

        try:
            success = self.sync_manager.sync_data_type('devices')
            if success:
                QMessageBox.information(self, "Success", "Devices synced successfully!")
                self.refresh_data()
            else:
                QMessageBox.warning(self, "Sync Failed", "Failed to sync devices")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Sync error: {e}")
    
    def sync_device_distances(self):
        """Sync device distances from log files"""
        try:
            # Import the sync functionality
            from sync_device_locations import DeviceLocationSyncer
            
            syncer = DeviceLocationSyncer()
            result = syncer.sync_device_locations()
            
            if result.get('errors'):
                error_msg = '\n'.join(result['errors'])
                QMessageBox.warning(self, "Sync Completed with Warnings", 
                                   f"Sync completed with {result['updated_devices']} devices updated.\n\nWarnings:\n{error_msg}")
            else:
                QMessageBox.information(self, "Distance Sync Success", 
                                       f"Successfully synced distances for {result['updated_devices']} devices!")
            
            # Refresh the display
            self.refresh_data()
            
        except Exception as e:
            self.logger.error(f"Error syncing distances: {e}")
            QMessageBox.critical(self, "Distance Sync Error", f"Failed to sync distances: {e}")

    def export_devices(self):
        """Export devices to CSV"""
        from PyQt5.QtWidgets import QFileDialog
        import shutil

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Devices", "devices_export.csv", "CSV Files (*.csv)"
        )

        if file_path:
            try:
                devices_csv_path = self.csv_handler.CSV_FILES['devices']
                shutil.copy2(devices_csv_path, file_path)
                QMessageBox.information(self, "Success", f"Devices exported to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Export failed: {e}")