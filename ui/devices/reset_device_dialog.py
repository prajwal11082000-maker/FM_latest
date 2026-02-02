from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox, QPushButton, QLabel, QFrame, QMessageBox
from PyQt5.QtCore import Qt
from ui.common.base_dialog import BaseDialog
from PyQt5.QtGui import QFont

class ResetDeviceDialog(BaseDialog):
    def __init__(self, parent=None, current_location: str = ""):
        super().__init__(parent)
        self.current_location = str(current_location) if current_location is not None else ""
        self.setup_ui()
        self.populate_maps_dropdown()
        
    def setup_ui(self):
        self.setWindowTitle("Reset Device")
        self.setModal(True)
        self.setFixedSize(600, 400)
        self.setStyleSheet(
            """
            QDialog { background-color: #2b2b2b; color: #ffffff; }
            QLabel { color: #ffffff; }
            QComboBox { background-color: #404040; border: 1px solid #555555; padding: 8px; border-radius: 4px; color: #ffffff; }
            QComboBox::drop-down { border: none; padding-right: 15px; }
            QPushButton { background-color: #555555; border: 1px solid #666666; padding: 10px 20px; border-radius: 4px; color: #ffffff; font-weight: bold; font-size: 13px; }
            QPushButton:hover { background-color: #666666; }
            QPushButton:pressed { background-color: #444444; }
        """
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("Reset Device")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #ff6b35; margin-bottom: 10px;")
        layout.addWidget(title)

        form_frame = QFrame()
        form_frame.setStyleSheet("QFrame { background-color: #353535; border: 1px solid #555555; border-radius: 6px; padding: 20px; }")
        form_layout = QFormLayout(form_frame)
        form_layout.setSpacing(15)

        # Current Map
        map_label = QLabel("Current Map *:")
        self.current_map_combo = QComboBox()
        self.current_map_combo.setPlaceholderText("Select Map")
        self.current_map_combo.currentIndexChanged.connect(self.on_map_changed)
        form_layout.addRow(map_label, self.current_map_combo)

        # Current Location
        loc_label = QLabel("Current Location *:")
        self.current_location_combo = QComboBox()
        self.current_location_combo.setPlaceholderText("Select Map First")
        self.current_location_combo.setEnabled(False)
        form_layout.addRow(loc_label, self.current_location_combo)
        
        layout.addWidget(form_frame)

        btns = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setAutoDefault(False)
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)

        reset_btn = QPushButton("Reset Device")
        reset_btn.setAutoDefault(False)
        reset_btn.setStyleSheet("QPushButton { background-color: #ff6b35; color: white; } QPushButton:hover { background-color: #e55a2b; }")
        reset_btn.clicked.connect(self.on_confirm)
        btns.addWidget(reset_btn)
        layout.addLayout(btns)

    def populate_maps_dropdown(self):
        try:
            csv_handler = self.parent().csv_handler
            maps = csv_handler.read_csv('maps')
            self.current_map_combo.clear()
            self.current_map_combo.addItem("Select Map", "")
            for m in maps:
                name = m.get('name', '')
                mid = m.get('id', '')
                if name and mid:
                    self.current_map_combo.addItem(name, str(mid))
                    
        except Exception as e:
            print(f"Error populating maps: {e}")
            QMessageBox.warning(self, "Error", "Failed to load maps")

    def on_map_changed(self, index):
        map_id = self.current_map_combo.currentData()
        if map_id:
            self.current_location_combo.setEnabled(True)
            self.populate_location_dropdown(map_id)
        else:
            self.current_location_combo.clear()
            self.current_location_combo.addItem("Select Location", "")
            self.current_location_combo.setEnabled(False)

    def populate_location_dropdown(self, map_id):
        try:
            csv_handler = self.parent().csv_handler
            zones = csv_handler.read_csv('zones')
            unique_zones = set()
            for zone in zones:
                if str(zone.get('map_id')) == str(map_id):
                    fz = zone.get('from_zone', '')
                    tz = zone.get('to_zone', '')
                    if fz:
                        unique_zones.add(fz)
                    if tz:
                        unique_zones.add(tz)
            
            self.current_location_combo.clear()
            self.current_location_combo.addItem("Select Location", "")
            for z in sorted(unique_zones):
                self.current_location_combo.addItem(z, z)
        except Exception as _:
            QMessageBox.warning(self, "Error", "Failed to load zones for location dropdown")

    def on_confirm(self):
        map_id = self.current_map_combo.currentData()
        loc = self.current_location_combo.currentData()
        if not map_id:
            QMessageBox.warning(self, "Validation", "Please select a map")
            return
        if not loc:
            QMessageBox.warning(self, "Validation", "Please select a location")
            return
        self.accept()

    def get_selected_location(self) -> str:
        return self.current_location_combo.currentData() or ""

    def get_selected_map(self) -> str:
        return self.current_map_combo.currentData() or ""
