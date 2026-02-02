from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QMessageBox, QDialog, QFormLayout, QLineEdit, QSpinBox
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
from ui.common.base_dialog import BaseDialog

from ui.common.table_widget import DataTableWidget
from api.client import APIClient
from data_manager.csv_handler import CSVHandler
from utils.logger import setup_logger


class RackManagementWidget(QWidget):
    def __init__(self, api_client: APIClient, csv_handler: CSVHandler):
        super().__init__()
        self.api_client = api_client
        self.csv_handler = csv_handler
        self.logger = setup_logger('rack_management')

        self.setup_ui()
        self.refresh_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        title = QLabel("Rack Management")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignLeft)
        title.setStyleSheet("color: #ffffff;")
        layout.addWidget(title)

        # Table columns: Rack_id, Distance from Ground, Map_name, Zone_name, Stop_id, Actions
        self.racks_table = DataTableWidget([
            "Rack_id", "Distance from Ground", "Map_name", "Zone_name", "Stop_id", "Actions"
        ], searchable=True, selectable=False)
        layout.addWidget(self.racks_table)

    def refresh_data(self):
        try:
            racks = self.csv_handler.read_csv('racks')
        except Exception as e:
            self.logger.error(f"Error reading racks CSV: {e}")
            racks = []

        rows = []
        for r in racks:
            rows.append([
                r.get('rack_id', ''),
                r.get('rack_distance_mm', ''),
                r.get('map_name', ''),
                r.get('zone_name', ''),
                r.get('stop_id', ''),
                "" # Action column
            ])
        self.racks_table.set_data(rows)
        self.add_action_buttons()

    def add_action_buttons(self):
        """Add Edit and Delete buttons to each row"""
        for row_idx in range(self.racks_table.table.rowCount()):
            rack_id = self.racks_table.table.item(row_idx, 0).text()
            
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(5, 2, 5, 2)
            action_layout.setSpacing(5)
            
            edit_btn = QPushButton("✏️ Edit")
            edit_btn.setStyleSheet("background-color: #3B82F6; color: white; border-radius: 2px; padding: 2px;")
            edit_btn.clicked.connect(lambda ch, r_id=rack_id: self.on_edit_rack(r_id))
            action_layout.addWidget(edit_btn)
            
            delete_btn = QPushButton("🗑️ Delete")
            delete_btn.setStyleSheet("background-color: #EF4444; color: white; border-radius: 2px; padding: 2px;")
            delete_btn.clicked.connect(lambda ch, r_id=rack_id: self.on_delete_rack(r_id))
            action_layout.addWidget(delete_btn)
            
            self.racks_table.table.setCellWidget(row_idx, 5, action_widget)

    def on_edit_rack(self, rack_id):
        """Handle rack edit"""
        racks = self.csv_handler.read_csv('racks')
        rack_data = next((r for r in racks if str(r.get('rack_id')) == str(rack_id)), None)
        
        if not rack_data:
            QMessageBox.warning(self, "Error", f"Rack {rack_id} not found")
            return
            
        dialog = EditRackDialog(self, rack_data)
        if dialog.exec_() == QDialog.Accepted:
            new_data = dialog.get_data()
            
            # Check for name uniqueness if ID changed
            if new_data['rack_id'] != rack_id:
                if any(str(r.get('rack_id')) == new_data['rack_id'] for r in racks):
                    QMessageBox.warning(self, "Duplicate ID", f"Rack ID '{new_data['rack_id']}' already exists.")
                    return
            
            # Update data while preserving other fields (map_name, zone_name, stop_id)
            updated_racks = []
            for r in racks:
                if str(r.get('rack_id')) == str(rack_id):
                    updated_racks.append({
                        **r,
                        'rack_id': new_data['rack_id'],
                        'rack_distance_mm': new_data['rack_distance_mm']
                    })
                else:
                    updated_racks.append(r)
            
            if self.csv_handler.write_csv('racks', updated_racks):
                QMessageBox.information(self, "Success", "Rack updated successfully")
                self.refresh_data()
                # Notify main window to refresh maps if needed
                parent = self.window()
                if hasattr(parent, 'map_management_widget'):
                    map_mgt = parent.map_management_widget
                    if hasattr(map_mgt, 'selected_map_id') and map_mgt.selected_map_id:
                        map_mgt.load_map_data(map_mgt.selected_map_id)
            else:
                QMessageBox.warning(self, "Error", "Failed to update rack data")

    def on_delete_rack(self, rack_id):
        """Handle rack deletion"""
        reply = QMessageBox.question(self, 'Confirm Deletion',
                                   f"Are you sure you want to delete rack {rack_id}?",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            racks = self.csv_handler.read_csv('racks')
            updated_racks = [r for r in racks if str(r.get('rack_id')) != str(rack_id)]
            
            if self.csv_handler.write_csv('racks', updated_racks):
                QMessageBox.information(self, "Success", "Rack deleted successfully")
                self.refresh_data()
                # Notify main window to refresh maps if needed
                parent = self.window()
                if hasattr(parent, 'map_management_widget'):
                    map_mgt = parent.map_management_widget
                    if hasattr(map_mgt, 'selected_map_id') and map_mgt.selected_map_id:
                        map_mgt.load_map_data(map_mgt.selected_map_id)
            else:
                QMessageBox.warning(self, "Error", "Failed to delete rack")

class EditRackDialog(BaseDialog):
    """Dialog for editing rack details"""
    def __init__(self, parent, rack_data):
        super().__init__(parent)
        self.rack_data = rack_data
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Edit Rack")
        self.setFixedWidth(350)
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.id_input = QLineEdit(self.rack_data.get('rack_id', ''))
        form.addRow("Rack ID:", self.id_input)
        
        self.distance_input = QSpinBox()
        self.distance_input.setRange(0, 1000000)
        self.distance_input.setValue(int(float(self.rack_data.get('rack_distance_mm', 0))))
        self.distance_input.setSuffix(" mm")
        form.addRow("Distance:", self.distance_input)
        
        layout.addLayout(form)
        
        buttons = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setAutoDefault(False)
        save_btn.clicked.connect(self.accept)
        save_btn.setStyleSheet("background-color: #10B981; color: white;")
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setAutoDefault(False)
        cancel_btn.clicked.connect(self.reject)
        
        buttons.addWidget(cancel_btn)
        buttons.addWidget(save_btn)
        layout.addLayout(buttons)
        
    def get_data(self):
        return {
            'rack_id': self.id_input.text().strip(),
            'rack_distance_mm': self.distance_input.value()
        }
