from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QPushButton, QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
                             QComboBox, QFrame, QScrollArea, QGroupBox, QGridLayout,
                             QMessageBox, QTabWidget, QListWidget, QListWidgetItem,
                             QSplitter, QTableWidget, QTableWidgetItem, QHeaderView,
                             QDialog, QCheckBox, QDialogButtonBox)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from datetime import datetime
from ui.common.input_validators import apply_no_special_chars_validator

from api.client import APIClient
from api.maps import MapsAPI
from ui.common.base_dialog import BaseDialog
from data_manager.csv_handler import CSVHandler
from utils.logger import setup_logger
from utils.stop_position_calculator import StopPositionCalculator


class ZoneConfigWidget(QWidget):
    zone_updated = pyqtSignal()

    def __init__(self, api_client: APIClient, csv_handler: CSVHandler):
        super().__init__()
        self.api_client = api_client
        self.csv_handler = csv_handler
        self.maps_api = MapsAPI(api_client)
        self.logger = setup_logger('zone_config')
        self.position_calculator = StopPositionCalculator()

        self.current_map_id = None
        self.current_zones = []
        self.current_stops = []
        
        # Edit mode state
        self.is_edit_mode = False
        self.editing_zone_id = None

        self.setup_ui()

    def setup_ui(self):
        """Setup zone configuration UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        header_label = QLabel("Zone Configuration")
        header_label.setFont(QFont("Arial", 14, QFont.Bold))
        header_label.setStyleSheet("color: #ffffff; margin-bottom: 10px;")
        layout.addWidget(header_label)

        # Main content with splitter
        splitter = QSplitter(Qt.Horizontal)

        # Left panel - Zone creation and management
        left_panel = self.create_zone_management_panel()
        splitter.addWidget(left_panel)

        # Right panel - Stop configuration
        right_panel = self.create_stop_config_panel()
        splitter.addWidget(right_panel)

        # Set splitter proportions
        splitter.setSizes([400, 500])
        layout.addWidget(splitter)

    def create_zone_management_panel(self):
        """Create zone management panel"""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: #353535;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        layout = QVBoxLayout(panel)

        # Zone creation section
        zone_group = QGroupBox("Create Zone Connection")
        zone_group.setStyleSheet(self.get_groupbox_style())
        zone_layout = QFormLayout(zone_group)

        # From Zone
        self.from_zone_input = QLineEdit()
        self.from_zone_input.setPlaceholderText("e.g., A, 1, PICK")
        self.apply_input_style(self.from_zone_input)
        apply_no_special_chars_validator(self.from_zone_input)
        zone_layout.addRow("From Zone:", self.from_zone_input)

        # To Zone
        self.to_zone_input = QLineEdit()
        self.to_zone_input.setPlaceholderText("e.g., B, 2, PACK")
        self.apply_input_style(self.to_zone_input)
        apply_no_special_chars_validator(self.to_zone_input)
        zone_layout.addRow("To Zone:", self.to_zone_input)

        # Magnitude (distance)
        self.magnitude_input = QDoubleSpinBox()
        self.magnitude_input.setRange(0.1, 1000.0)
        self.magnitude_input.setValue(100.0)
        self.magnitude_input.setSuffix(" m")
        self.magnitude_input.setDecimals(1)
        self.apply_input_style(self.magnitude_input)
        zone_layout.addRow("Distance:", self.magnitude_input)

        # Direction
        self.direction_combo = QComboBox()
        directions = ["north", "south", "east", "west"]
        self.direction_combo.addItems(directions)
        self.apply_input_style(self.direction_combo)
        zone_layout.addRow("Direction:", self.direction_combo)

        # Direction
        self.direction_combo = QComboBox()
        directions = ["north", "south", "east", "west"]
        self.direction_combo.addItems(directions)
        self.apply_input_style(self.direction_combo)
        zone_layout.addRow("Direction:", self.direction_combo)

        # Create/Update zone button
        self.zone_action_btn = QPushButton("➕ Create Zone Connection")
        self.zone_action_btn.clicked.connect(self.create_zone_connection)
        create_zone_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff6b35;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
                margin: 10px 0;
            }
            QPushButton:hover {
                background-color: #e55a2b;
            }
        """)
        zone_layout.addRow(self.zone_action_btn)

        layout.addWidget(zone_group)

        # Existing zones table with prominent title
        zones_list_group = QGroupBox("Existing Zone Connections")
        zones_list_group.setStyleSheet(self.get_groupbox_style() + """
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                color: #ff6b35;
            }
        """)
        zones_list_layout = QVBoxLayout(zones_list_group)

        # Create table widget with configurable headers
        self.zones_table = QTableWidget()
        
        # Define available columns with their properties
        self.available_columns = [
            {"id": "from_zone", "name": "From Zone", "key": "from_zone", "visible": True},
            {"id": "to_zone", "name": "To Zone", "key": "to_zone", "visible": True},
            {"id": "distance", "name": "Distance", "key": "magnitude", "visible": True},
            {"id": "direction", "name": "Direction", "key": "direction", "visible": True},
            {"id": "created", "name": "Created", "key": "created_at", "visible": True},
            {"id": "edited", "name": "Edited", "key": "edited_at", "visible": True},
            {"id": "updated", "name": "Last Updated", "key": "updated_at", "visible": False},
            {"id": "status", "name": "Status", "key": "status", "visible": False}
        ]
        
        # Configure visible columns
        self.configure_table_columns()
        
        # Apply a custom font to headers for better visibility
        header_font = QFont("Arial", 12, QFont.Bold)
        self.zones_table.horizontalHeader().setFont(header_font)
        
        # Style the table for better visibility
        self.zones_table.setStyleSheet("""
            QTableWidget {
                background-color: #404040;
                border: 1px solid #555555;
                border-radius: 4px;
                color: #ffffff;
                gridline-color: #555555;
                selection-background-color: #ff6b35;
            }
            QTableWidget::item {
                padding: 10px;
                border-bottom: 1px solid #555555;
                font-size: 12px;
            }
            QTableWidget::item:selected {
                background-color: #ff6b35;
                color: white;
            }
            QTableWidget::item:hover {
                background-color: #555555;
            }
            QHeaderView::section {
                background-color: #2c2c2c;
                color: #ffffff;
                padding: 25px;
                border: 3px solid #ff6b35;
                font-weight: bold;
                font-size: 18px;
                text-align: center;
                margin: 4px;
                border-radius: 6px;
                text-transform: uppercase;
                letter-spacing: 2px;
                box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.5);
            }
            QHeaderView::section:hover {
                background-color: #3a3a3a;
                border: 3px solid #ff8c5a;
            }
            QHeaderView {
                background-color: #000000;
            }
        """)
        
        # Configure table properties
        self.zones_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.zones_table.setAlternatingRowColors(True)
        self.zones_table.horizontalHeader().setStretchLastSection(True)
        self.zones_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.zones_table.horizontalHeader().setHighlightSections(True)
        self.zones_table.horizontalHeader().setMinimumHeight(100)
        self.zones_table.verticalHeader().setVisible(False)
        
        # Connect selection event
        self.zones_table.itemSelectionChanged.connect(self.on_zone_table_selected)
        zones_list_layout.addWidget(self.zones_table)

        # Table controls layout
        table_controls = QHBoxLayout()
        
        # Edit zone button
        edit_zone_btn = QPushButton("✏️ Edit Selected Zone")
        edit_zone_btn.clicked.connect(self.edit_selected_zone)
        self.apply_button_style(edit_zone_btn)
        table_controls.addWidget(edit_zone_btn)
        
        # Delete zone button
        delete_zone_btn = QPushButton("🗑️ Delete Selected Zone")
        delete_zone_btn.clicked.connect(self.delete_selected_zone)
        self.apply_button_style(delete_zone_btn)
        table_controls.addWidget(delete_zone_btn)
        
        # Column configuration button
        configure_columns_btn = QPushButton("⚙️ Configure Columns")
        configure_columns_btn.clicked.connect(self.show_column_config)
        self.apply_button_style(configure_columns_btn)
        table_controls.addWidget(configure_columns_btn)
        
        zones_list_layout.addLayout(table_controls)

        layout.addWidget(zones_list_group)

        return panel

    def create_stop_config_panel(self):
        """Create stop configuration panel"""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: #353535;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        layout = QVBoxLayout(panel)

        # Stop generation section
        stop_gen_group = QGroupBox("Generate Stops")
        stop_gen_group.setStyleSheet(self.get_groupbox_style())
        stop_gen_layout = QVBoxLayout(stop_gen_group)

        # Basic stop configuration
        basic_config_layout = QFormLayout()

        # Stop count
        self.stop_count_input = QSpinBox()
        self.stop_count_input.setRange(1, 100)
        self.stop_count_input.setValue(10)
        self.apply_input_style(self.stop_count_input)
        basic_config_layout.addRow("Number of Stops:", self.stop_count_input)

        # Stop spacing
        self.stop_spacing_input = QDoubleSpinBox()
        self.stop_spacing_input.setRange(0.1, 50.0)
        self.stop_spacing_input.setValue(5.0)
        self.stop_spacing_input.setSuffix(" m")
        self.stop_spacing_input.setDecimals(1)
        self.apply_input_style(self.stop_spacing_input)
        basic_config_layout.addRow("Stop Spacing:", self.stop_spacing_input)

        stop_gen_layout.addLayout(basic_config_layout)

        # Bin configuration
        bin_config_group = QGroupBox("Bin Configuration")
        bin_config_group.setStyleSheet(self.get_groupbox_style())
        bin_config_layout = QGridLayout(bin_config_group)
        
        # Add explanation label
        explanation_label = QLabel(
            "Left/Right Bins = Number of stops on each side\n"
            "Example: 2 left + 2 right = 4 total stops (2 per side)"
        )
        explanation_label.setStyleSheet(
            "color: #cccccc; font-style: italic; font-size: 10px; margin: 5px;"
        )
        bin_config_layout.addWidget(explanation_label, 0, 0, 1, 4)  # Span all columns

        # Left bins
        bin_config_layout.addWidget(QLabel("Left Bins Count:"), 1, 0)
        self.left_bins_input = QSpinBox()
        self.left_bins_input.setRange(0, 20)
        self.left_bins_input.setValue(2)
        self.apply_input_style(self.left_bins_input)
        bin_config_layout.addWidget(self.left_bins_input, 1, 1)

        bin_config_layout.addWidget(QLabel("Left Bins Distance:"), 1, 2)
        self.left_bins_distance_input = QDoubleSpinBox()
        self.left_bins_distance_input.setRange(0.1, 10.0)
        self.left_bins_distance_input.setValue(2.0)
        self.left_bins_distance_input.setSuffix(" m")
        self.left_bins_distance_input.setDecimals(1)
        self.apply_input_style(self.left_bins_distance_input)
        bin_config_layout.addWidget(self.left_bins_distance_input, 1, 3)

        # Right bins
        bin_config_layout.addWidget(QLabel("Right Bins Count:"), 2, 0)
        self.right_bins_input = QSpinBox()
        self.right_bins_input.setRange(0, 20)
        self.right_bins_input.setValue(2)
        self.apply_input_style(self.right_bins_input)
        bin_config_layout.addWidget(self.right_bins_input, 2, 1)

        bin_config_layout.addWidget(QLabel("Right Bins Distance:"), 2, 2)
        self.right_bins_distance_input = QDoubleSpinBox()
        self.right_bins_distance_input.setRange(0.1, 10.0)
        self.right_bins_distance_input.setValue(2.0)
        self.right_bins_distance_input.setSuffix(" m")
        self.right_bins_distance_input.setDecimals(1)
        self.apply_input_style(self.right_bins_distance_input)
        bin_config_layout.addWidget(self.right_bins_distance_input, 2, 3)

        stop_gen_layout.addWidget(bin_config_group)


        # Generate stops button
        generate_btn = QPushButton("🔧 Generate Stops")
        generate_btn.clicked.connect(self.generate_stops)
        generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: white;
                border: none;
                padding: 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        stop_gen_layout.addWidget(generate_btn)

        layout.addWidget(stop_gen_group)

        # Generated stops list
        stops_group = QGroupBox("Generated Stops")
        stops_group.setStyleSheet(self.get_groupbox_style())
        stops_layout = QVBoxLayout(stops_group)

        self.stops_list = QListWidget()
        self.stops_list.setStyleSheet("""
            QListWidget {
                background-color: #404040;
                border: 1px solid #555555;
                border-radius: 4px;
                color: #ffffff;
                padding: 5px;
            }
            QListWidget::item {
                padding: 6px;
                margin: 1px;
                border-radius: 3px;
                background-color: #4a4a4a;
                font-size: 11px;
            }
            QListWidget::item:selected {
                background-color: #ff6b35;
            }
        """)
        stops_layout.addWidget(self.stops_list)

        layout.addWidget(stops_group)

        return panel

    def get_groupbox_style(self):
        """Get groupbox styling"""
        return """
            QGroupBox {
                color: #ffffff;
                border: 1px solid #666666;
                border-radius: 6px;
                padding-top: 10px;
                margin: 5px;
                font-weight: bold;
            }
            QGroupBox::title {
                color: #ff6b35;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """

    def apply_input_style(self, widget):
        """Apply input styling with visible dropdown arrows for combo boxes"""
        if isinstance(widget, QComboBox):
            # Special styling for combo boxes with visible dropdown arrow
            widget.setStyleSheet("""
                QComboBox {
                    background-color: #404040;
                    border: 1px solid #555555;
                    padding: 8px 25px 8px 8px;
                    border-radius: 4px;
                    color: #ffffff;
                    min-width: 150px;
                }
                QComboBox:focus {
                    border: 2px solid #ff6b35;
                }
                QComboBox::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 20px;
                    border-left: 1px solid #666666;
                    background-color: #555555;
                    border-top-right-radius: 4px;
                    border-bottom-right-radius: 4px;
                }
                QComboBox::drop-down:hover {
                    background-color: #666666;
                }
                QComboBox::down-arrow {
                    image: none;
                    border: 2px solid #ffffff;
                    width: 6px;
                    height: 6px;
                    border-top: none;
                    border-right: none;
                    transform: rotate(45deg);
                    margin: 2px;
                }
                QComboBox::down-arrow:hover {
                    border-color: #ff6b35;
                }
                QComboBox QAbstractItemView {
                    background-color: #404040;
                    color: #ffffff;
                    selection-background-color: #ff6b35;
                    border: 1px solid #555555;
                    outline: none;
                }
            """)
        else:
            # Regular styling for other input widgets
            widget.setStyleSheet("""
                QLineEdit, QSpinBox, QDoubleSpinBox {
                    background-color: #404040;
                    border: 1px solid #555555;
                    padding: 6px;
                    border-radius: 4px;
                    color: #ffffff;
                }
                QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                    border: 2px solid #ff6b35;
                }
            """)

    def apply_button_style(self, button):
        """Apply button styling"""
        button.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)

    def set_map_id(self, map_id):
        """Set current map ID"""
        self.current_map_id = map_id
        self.load_zones()

    def clear_map(self):
        """Clear map data"""
        self.current_map_id = None
        self.current_zones = []
        self.current_stops = []
        self.zones_table.setRowCount(0)
        self.stops_list.clear()

    def load_zones(self):
        """Load zones for current map"""
        if not self.current_map_id:
            return

        try:
            # Load from CSV
            zones = self.csv_handler.read_csv('zones')
            self.current_zones = [z for z in zones if str(z.get('map_id')) == str(self.current_map_id)]
            self.populate_zones_list()

        except Exception as e:
            self.logger.error(f"Error loading zones: {e}")

    def configure_table_columns(self):
        """Configure table columns based on visible columns"""
        # Get visible columns
        visible_columns = [col for col in self.available_columns if col["visible"]]
        
        # Set column count
        self.zones_table.setColumnCount(len(visible_columns))
        
        # Set header labels with increased size
        headers = [col["name"] for col in visible_columns]
        self.zones_table.setHorizontalHeaderLabels(headers)
        
        # Increase header height for better visibility
        self.zones_table.horizontalHeader().setMinimumHeight(60)
        
        # Apply custom font to headers
        header_font = QFont("Arial", 12, QFont.Bold)
        self.zones_table.horizontalHeader().setFont(header_font)
        
        # Store visible columns for reference when populating
        self.visible_columns = visible_columns
    
    def toggle_column_visibility(self, column_id, visible=True):
        """Toggle visibility of a column"""
        for col in self.available_columns:
            if col["id"] == column_id:
                col["visible"] = visible
                break
        
        # Reconfigure table columns
        self.configure_table_columns()
        
        # Repopulate table with new column configuration
        self.populate_zones_list()
    
    def populate_zones_list(self):
        """Populate zones table with dynamic columns"""
        self.zones_table.setRowCount(0)  # Clear existing rows

        # Create font for better readability
        cell_font = QFont()
        cell_font.setPointSize(11)  # Increase font size for better visibility

        for zone in self.current_zones:
            row_position = self.zones_table.rowCount()
            self.zones_table.insertRow(row_position)
            
            # Set row height for better visibility
            self.zones_table.setRowHeight(row_position, 40)

            # Populate each visible column
            for col_idx, column in enumerate(self.visible_columns):
                col_id = column["id"]
                col_key = column["key"]
                
                # Create table item based on column type
                if col_id == "distance":
                    magnitude = zone.get(col_key, 0)
                    item = QTableWidgetItem(f"{magnitude} m")
                
                elif col_id in ["created", "updated"]:
                    date_value = zone.get(col_key, '')
                    if date_value:
                        try:
                            # Format the date with time for better display
                            dt = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                            formatted_date = dt.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            # If parsing fails, try to include time if available
                            if len(date_value) >= 19:  # Length of 'YYYY-MM-DD HH:MM:SS'
                                formatted_date = date_value[:19]
                            else:
                                formatted_date = date_value
                    else:
                        formatted_date = 'N/A'
                    item = QTableWidgetItem(formatted_date)
                
                elif col_id in ["type", "direction", "status"]:
                    # Title case for readability
                    item = QTableWidgetItem(str(zone.get(col_key, '')).title())
                
                else:
                    # Default handling for other columns
                    item = QTableWidgetItem(str(zone.get(col_key, '')))
                
                # Apply font to cell for better visibility
                item.setFont(cell_font)
                
                # Center align text for better readability
                item.setTextAlignment(Qt.AlignCenter)
                
                # Store zone data in every column for easier access
                item.setData(Qt.UserRole, zone)
                
                self.zones_table.setItem(row_position, col_idx, item)



    def create_zone_connection(self):
        """Create new zone connection"""
        if not self.current_map_id:
            QMessageBox.warning(self, "No Map", "Please select a map first")
            return

        from_zone = self.from_zone_input.text().strip()
        to_zone = self.to_zone_input.text().strip()

        if not from_zone or not to_zone:
            QMessageBox.warning(self, "Missing Data", "Please enter both from and to zones")
            return

        zone_data = {
            'map_id': self.current_map_id,
            'from_zone': from_zone,
            'to_zone': to_zone,
            'magnitude': self.magnitude_input.value(),
            'direction': self.direction_combo.currentText()
        }
        
        now = datetime.now().isoformat()

        try:
            if self.is_edit_mode and self.editing_zone_id:
                # Update existing zone
                zone_data['id'] = self.editing_zone_id
                # Keep created_at
                existing_zone = next((z for z in self.current_zones if str(z.get('id')) == str(self.editing_zone_id)), {})
                zone_data['created_at'] = existing_zone.get('created_at', now)
                zone_data['edited_at'] = now
                
                if self.csv_handler.update_csv_row('zones', self.editing_zone_id, zone_data):
                    QMessageBox.information(self, "Success", "Zone connection updated successfully!")
                    self.load_zones()
                    self.clear_zone_form()
                    self.zone_updated.emit()
                else:
                    raise Exception("Failed to update CSV")
            else:
                # Create new zone
                zone_data['id'] = self.csv_handler.get_next_id('zones')
                zone_data['created_at'] = now
                zone_data['edited_at'] = ''
                
                # Try API first if authenticated
                if self.api_client.is_authenticated():
                    response = self.maps_api.create_zone_connection(self.current_map_id, zone_data)
                    if 'error' not in response:
                        QMessageBox.information(self, "Success", "Zone connection created successfully!")
                        self.load_zones()
                        self.clear_zone_form()
                        self.zone_updated.emit()
                        return
                    else:
                        raise Exception(response['error'])

                # Fallback to CSV
                if self.csv_handler.append_to_csv('zones', zone_data):
                    QMessageBox.information(self, "Success", "Zone connection saved to local storage!")
                    self.load_zones()
                    self.clear_zone_form()
                    self.zone_updated.emit()
                else:
                    raise Exception("Failed to save to CSV")

        except Exception as e:
            self.logger.error(f"Error handling zone connection: {e}")
            QMessageBox.critical(self, "Error", f"Failed to handle zone connection: {e}")

    def clear_zone_form(self):
        """Clear zone creation form and reset edit mode"""
        self.from_zone_input.clear()
        self.to_zone_input.clear()
        self.magnitude_input.setValue(100.0)
        self.direction_combo.setCurrentIndex(0)
        
        self.is_edit_mode = False
        self.editing_zone_id = None
        self.zone_action_btn.setText("➕ Create Zone Connection")
        self.zone_action_btn.setStyleSheet(self.zone_action_btn.styleSheet().replace("#10B981", "#ff6b35"))

    def on_zone_table_selected(self):
        """Handle zone table selection"""
        # We don't automatically enter edit mode on selection anymore
        # but we can still populate the form if the user wants to see details
        current_row = self.zones_table.currentRow()
        if current_row >= 0:
            # Find the column that contains the zone data (from_zone)
            zone_data = None
            for col_idx, column in enumerate(self.visible_columns):
                if column["id"] == "from_zone":
                    from_zone_item = self.zones_table.item(current_row, col_idx)
                    if from_zone_item:
                        zone_data = from_zone_item.data(Qt.UserRole)
                    break
            
            if zone_data and not self.is_edit_mode:
                # Populate form with selected zone data (preview)
                self.from_zone_input.setText(zone_data.get('from_zone', ''))
                self.to_zone_input.setText(zone_data.get('to_zone', ''))
                self.magnitude_input.setValue(float(zone_data.get('magnitude', 100)))

                # Set direction
                direction = zone_data.get('direction', 'north')
                direction_index = self.direction_combo.findText(direction)
                if direction_index >= 0:
                    self.direction_combo.setCurrentIndex(direction_index)
                else:
                    self.direction_combo.setCurrentIndex(0)

    def edit_selected_zone(self):
        """Enter edit mode for selected zone"""
        current_row = self.zones_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a zone to edit")
            return
            
        # Find zone data
        zone_data = None
        for col_idx, column in enumerate(self.visible_columns):
            if column["id"] == "from_zone":
                item = self.zones_table.item(current_row, col_idx)
                if item:
                    zone_data = item.data(Qt.UserRole)
                break
        
        if zone_data:
            self.is_edit_mode = True
            self.editing_zone_id = zone_data.get('id')
            
            # Populate form
            self.from_zone_input.setText(zone_data.get('from_zone', ''))
            self.to_zone_input.setText(zone_data.get('to_zone', ''))
            self.magnitude_input.setValue(float(zone_data.get('magnitude', 100)))
            
            direction = zone_data.get('direction', 'north')
            direction_index = self.direction_combo.findText(direction)
            if direction_index >= 0:
                self.direction_combo.setCurrentIndex(direction_index)
            
            # Update UI
            self.zone_action_btn.setText("💾 Update Zone Connection")
            self.zone_action_btn.setStyleSheet(self.zone_action_btn.styleSheet().replace("#ff6b35", "#10B981"))
            self.from_zone_input.setFocus()

    def show_column_config(self):
        """Show column configuration dialog"""
        dialog = BaseDialog(self)
        dialog.setWindowTitle("Configure Table Columns")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(500)
        
        layout = QVBoxLayout(dialog)
        
        # Instructions
        instructions = QLabel("Configure columns to display in the zone connections table:\nDrag and drop items to reorder them.")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Create a list widget for drag and drop reordering
        list_widget = QListWidget()
        list_widget.setDragDropMode(QListWidget.InternalMove)
        list_widget.setSelectionMode(QListWidget.SingleSelection)
        layout.addWidget(list_widget)
        
        # Add items to the list widget
        for column in self.available_columns:
            item = QListWidgetItem(column["name"])
            item.setData(Qt.UserRole, column["id"])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
            item.setCheckState(Qt.Checked if column["visible"] else Qt.Unchecked)
            list_widget.addItem(item)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # Select All button
        select_all_btn = QPushButton("Select All")
        select_all_btn.setAutoDefault(False)
        select_all_btn.clicked.connect(lambda: self.toggle_all_list_items(list_widget, Qt.Checked))
        button_layout.addWidget(select_all_btn)
        
        # Deselect All button
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.setAutoDefault(False)
        deselect_all_btn.clicked.connect(lambda: self.toggle_all_list_items(list_widget, Qt.Unchecked))
        button_layout.addWidget(deselect_all_btn)
        
        # Reset to Default button
        reset_default_btn = QPushButton("Reset to Default")
        reset_default_btn.setAutoDefault(False)
        reset_default_btn.clicked.connect(lambda: self.reset_default_list_items(list_widget))
        button_layout.addWidget(reset_default_btn)
        
        layout.addLayout(button_layout)
        
        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        save_btn = buttons.button(QDialogButtonBox.Ok)
        save_btn.setText("Save Configuration")
        save_btn.setAutoDefault(False)
        buttons.accepted.connect(dialog.accept)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setAutoDefault(False)
        cancel_btn.clicked.connect(dialog.reject)
        buttons.addButton(cancel_btn, QDialogButtonBox.RejectRole)

        layout.addWidget(buttons)
        
        # Execute dialog
        if dialog.exec_() == QDialog.Accepted:
            # Create a new column order based on the list widget
            new_column_order = []
            visible_columns = []
            
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                col_id = item.data(Qt.UserRole)
                is_visible = item.checkState() == Qt.Checked
                
                # Find the column in available_columns
                for col in self.available_columns:
                    if col["id"] == col_id:
                        # Create a copy of the column with updated visibility
                        new_col = col.copy()
                        new_col["visible"] = is_visible
                        new_column_order.append(new_col)
                        if is_visible:
                            visible_columns.append(new_col)
                        break
            
            # Ensure at least one column is visible
            if not visible_columns:
                QMessageBox.warning(self, "Warning", "At least one column must be visible. Resetting to defaults.")
                self.reset_column_defaults()
            else:
                # Update available_columns with the new order
                self.available_columns = new_column_order
            
            # Reconfigure table
            self.configure_table_columns()
            self.populate_zones_list()
    
    def toggle_all_list_items(self, list_widget, state):
        """Toggle all list items to the specified check state"""
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            item.setCheckState(state)
    
    def reset_default_list_items(self, list_widget):
        """Reset list items to default column configuration"""
        default_visible = ["from_zone", "to_zone", "distance", "direction", "type", "created"]
        
        # First, reset all items to their default visibility
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            col_id = item.data(Qt.UserRole)
            item.setCheckState(Qt.Checked if col_id in default_visible else Qt.Unchecked)
        
        # Then, reorder the items to match the default order
        # Create a mapping of column IDs to their default positions
        default_order = {col_id: idx for idx, col_id in enumerate(default_visible)}
        
        # Sort the items based on their default positions
        items_to_sort = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            col_id = item.data(Qt.UserRole)
            # Items in default_visible come first, in their specified order
            # Items not in default_visible come after, in their current order
            sort_key = default_order.get(col_id, 1000 + i)
            items_to_sort.append((sort_key, item.clone()))
        
        # Sort items by their sort key
        items_to_sort.sort(key=lambda x: x[0])
        
        # Clear and repopulate the list widget
        list_widget.clear()
        for _, item in items_to_sort:
            list_widget.addItem(item)
    
    def reset_column_defaults(self):
        """Reset column visibility to defaults"""
        default_visible = ["from_zone", "to_zone", "distance", "direction", "type", "created"]
        for column in self.available_columns:
            column["visible"] = column["id"] in default_visible
    
    def delete_selected_zone(self):
        """Delete selected zone"""
        current_row = self.zones_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a zone to delete")
            return

        # Find the column that contains the zone data (from_zone)
        zone_data = None
        for col_idx, column in enumerate(self.visible_columns):
            if column["id"] == "from_zone":
                from_zone_item = self.zones_table.item(current_row, col_idx)
                if from_zone_item:
                    zone_data = from_zone_item.data(Qt.UserRole)
                break
        
        # If from_zone column is not visible, try to get data from any column
        if not zone_data:
            for col in range(self.zones_table.columnCount()):
                item = self.zones_table.item(current_row, col)
                if item and item.data(Qt.UserRole):
                    zone_data = item.data(Qt.UserRole)
                    break
                    
        if not zone_data:
            QMessageBox.warning(self, "Error", "Could not retrieve zone data")
            return
            
        zone_id = zone_data.get('id')

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete zone connection {zone_data.get('from_zone')} → {zone_data.get('to_zone')}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # Try API first
                if self.api_client.is_authenticated():
                    response = self.maps_api.delete_zone_connection(self.current_map_id, zone_id)
                    if 'error' not in response:
                        QMessageBox.information(self, "Success", "Zone connection deleted!")
                        self.load_zones()
                        self.zone_updated.emit()
                        return
                    else:
                        raise Exception(response['error'])

                # Fallback to CSV
                if self.csv_handler.delete_csv_row('zones', zone_id):
                    QMessageBox.information(self, "Success", "Zone connection deleted from local storage!")
                    self.load_zones()
                    self.zone_updated.emit()
                else:
                    raise Exception("Failed to delete from CSV")

            except Exception as e:
                self.logger.error(f"Error deleting zone: {e}")
                QMessageBox.critical(self, "Error", f"Failed to delete zone: {e}")

    def generate_stops(self):
        """Generate stops for selected zone"""

        current_row = self.zones_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a zone connection first")
            return

        # Get zone data from the first column
        from_zone_item = self.zones_table.item(current_row, 0)
        if not from_zone_item:
            return
            
        zone_data = from_zone_item.data(Qt.UserRole)
        zone_id = zone_data.get('id')

        stop_generation_data = {
            'stop_count': self.stop_count_input.value(),
            'stop_spacing': self.stop_spacing_input.value(),
            'left_bins_count': self.left_bins_input.value(),
            'right_bins_count': self.right_bins_input.value(),
            'left_bins_distance': self.left_bins_distance_input.value(),
            'right_bins_distance': self.right_bins_distance_input.value()
        }

        try:
            # Debug: Show what parameters we're working with

            self.generate_stops_locally(zone_data, stop_generation_data)
            return
            
            # Original API code (commented out for debugging)
            # if self.api_client.is_authenticated():
            #     response = self.maps_api.generate_stops(self.current_map_id, zone_id, stop_generation_data)
            #     if 'error' not in response:
            #         QMessageBox.information(self, "Success", f"Generated {self.stop_count_input.value()} stops!")
            #         self.load_generated_stops(zone_id)
            #         self.zone_updated.emit()
            #         return
            #     else:
            #         raise Exception(response['error'])
            # 
            # # Fallback to local generation
            # self.generate_stops_locally(zone_data, stop_generation_data)

        except Exception as e:
            self.logger.error(f"Error generating stops: {e}")
            QMessageBox.critical(self, "Error", f"Failed to generate stops: {e}")

    def generate_stops_locally(self, zone_data, config):
        """Generate stops locally with automatic position calculation and save to CSV"""
        try:

            # First, we need to get zone coordinates from existing zone data
            # For now, we'll create mock coordinates based on zone names
            # In a real scenario, these would come from the map layout
            
            # Generate default coordinates for zones if they don't exist
            from_x = zone_data.get('from_x', 100)  # Default starting point
            from_y = zone_data.get('from_y', 100)
            
            # Calculate end coordinates based on direction and distance
            magnitude = float(zone_data.get('magnitude', 50))
            direction = zone_data.get('direction', 'east')  # Default direction
            
            # Use direction to calculate end coordinates
            direction_vectors = {
                'north': (0, -1), 'south': (0, 1), 'east': (1, 0), 'west': (-1, 0),
                'northeast': (0.707, -0.707), 'northwest': (-0.707, -0.707),
                'southeast': (0.707, 0.707), 'southwest': (-0.707, 0.707)
            }
            
            dx, dy = direction_vectors.get(direction.lower(), (1, 0))
            to_x = from_x + dx * magnitude
            to_y = from_y + dy * magnitude
            
            # Prepare zone data for position calculator
            calc_zone_data = {
                'from_zone': zone_data.get('from_zone'),
                'to_zone': zone_data.get('to_zone'),
                'from_x': from_x,
                'from_y': from_y,
                'to_x': to_x,
                'to_y': to_y,
                'magnitude': magnitude,
                'direction': direction
            }
            
            # Use equal interval calculation as specified in requirements
            # This creates separate stops for left and right sides at calculated intervals
            stop_positions = self.position_calculator.calculate_equal_interval_stops(
                from_point=(from_x, from_y),
                to_point=(to_x, to_y),
                total_distance=magnitude,                    # Total distance for calculation
                left_bins_count=config['left_bins_count'],   # Number of left side stops
                right_bins_count=config['right_bins_count'], # Number of right side stops
                bin_offset_distance=config['left_bins_distance'],  # Offset distance from main path
                zone_name=f"{zone_data.get('from_zone', 'A')}_to_{zone_data.get('to_zone', 'B')}"
            )
            
            # Validate positions
            warnings = self.position_calculator.validate_positions(stop_positions)
            if warnings:
                warning_text = "\n".join(warnings)
                self.logger.warning(f"Position validation warnings: {warning_text}")
            
            # Export coordinates for map display
            map_export_data = self.position_calculator.export_coordinates_for_map(stop_positions)
            
            # Convert to CSV format and save
            stops_saved = 0
            for stop_pos in stop_positions:
                stop_data = {
                    'id': self.csv_handler.get_next_id('stops'),
                    'zone_connection_id': zone_data.get('id'),
                    'map_id': self.current_map_id,
                    'stop_id': stop_pos.stop_id,
                    'name': stop_pos.name,
                    'x_coordinate': stop_pos.main_x,
                    'y_coordinate': stop_pos.main_y,
                    'display_x': stop_pos.main_x,  # For map viewer compatibility
                    'display_y': stop_pos.main_y,  # For map viewer compatibility
                    'left_bins_count': config['left_bins_count'],
                    'right_bins_count': config['right_bins_count'],
                    'left_bins_distance': config['left_bins_distance'],
                    'right_bins_distance': config['right_bins_distance'],
                    'distance_from_start': stop_pos.distance_from_start,
                    'created_at': datetime.now().isoformat()
                }
                
                if self.csv_handler.append_to_csv('stops', stop_data):
                    stops_saved += 1
                else:
                    self.logger.error(f"Failed to save stop: {stop_pos.stop_id}")
            
            # Also save bin positions as separate entries for detailed tracking
            bins_saved = 0
            for stop_pos in stop_positions:
                for bin_pos in stop_pos.bins:
                    bin_data = {
                        'id': self.csv_handler.get_next_id('bin_positions'),
                        'stop_id': stop_pos.stop_id,
                        'zone_connection_id': zone_data.get('id'),
                        'map_id': self.current_map_id,
                        'bin_id': f"{bin_pos.stop_id}_{bin_pos.side}_{bin_pos.bin_number}",
                        'side': bin_pos.side,
                        'bin_number': bin_pos.bin_number,
                        'x_coordinate': bin_pos.x,
                        'y_coordinate': bin_pos.y,
                        'created_at': datetime.now().isoformat()
                    }
                    
                    # Save to bin_positions CSV (create if doesn't exist)
                    if self.csv_handler.append_to_csv('bin_positions', bin_data):
                        bins_saved += 1
            
            success_message = f"Generated {stops_saved} stops with precise coordinates!"
            if bins_saved > 0:
                success_message += f"\n{bins_saved} bin positions calculated."
            if warnings:
                success_message += f"\nWarnings: {len(warnings)} position conflicts detected."
                
            QMessageBox.information(self, "Success", success_message)
            
            # Show detailed calculation results
            self.show_calculation_results(stop_positions, magnitude)
            
            self.load_generated_stops(zone_data.get('id'))
            self.zone_updated.emit()
            
        except Exception as e:
            self.logger.error(f"Error in automatic stop generation: {e}")
            QMessageBox.critical(self, "Error", f"Failed to generate stops: {e}")
    
    def show_calculation_results(self, stop_positions, total_distance):
        """Show detailed calculation results in a message box"""
        if not stop_positions:
            return
            
        result_text = f"Automatic Stop Positioning Results\n"
        result_text += f"="*45 + "\n"
        result_text += f"Total Route Distance: {total_distance:.1f}m\n"
        result_text += f"Number of Stops Generated: {len(stop_positions)}\n\n"
        
        for i, stop in enumerate(stop_positions):
            result_text += f"Stop {i+1}: {stop.name}\n"
            result_text += f"  Position: ({stop.main_x:.2f}, {stop.main_y:.2f})\n"
            result_text += f"  Distance from start: {stop.distance_from_start:.2f}m\n"
            result_text += f"  Bins: {len(stop.bins)} ({len([b for b in stop.bins if b.side == 'left'])} left, {len([b for b in stop.bins if b.side == 'right'])} right)\n"
            
            # Show first few bin positions
            if stop.bins:
                result_text += f"  Bin coordinates:\n"
                for bin_pos in stop.bins[:4]:  # Show first 4 bins
                    result_text += f"    {bin_pos.side.title()} Bin {bin_pos.bin_number}: ({bin_pos.x:.2f}, {bin_pos.y:.2f})\n"
                if len(stop.bins) > 4:
                    result_text += f"    ... and {len(stop.bins) - 4} more bins\n"
            result_text += "\n"
        
        # Show in a separate dialog for better readability
        msg = QMessageBox(self)
        msg.setWindowTitle("Stop Position Calculation Results")
        msg.setText("Automatic positioning complete!")
        msg.setDetailedText(result_text)
        msg.setIcon(QMessageBox.Information)
        msg.exec_()

    def load_generated_stops(self, zone_id):
        """Load generated stops for a zone"""
        try:
            stops = self.csv_handler.read_csv('stops')
            zone_stops = [s for s in stops if str(s.get('zone_connection_id')) == str(zone_id)]

            self.stops_list.clear()
            for stop in zone_stops:
                stop_text = f"{stop.get('name', '')} - {stop.get('stop_id', '')}"
                stop_text += f"\nBins: L{stop.get('left_bins_count', 0)} R{stop.get('right_bins_count', 0)}"

                item = QListWidgetItem(stop_text)
                item.setData(Qt.UserRole, stop)
                self.stops_list.addItem(item)

        except Exception as e:
            self.logger.error(f"Error loading stops: {e}")