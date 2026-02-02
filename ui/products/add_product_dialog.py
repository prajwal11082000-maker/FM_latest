from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QPushButton, QLabel, QFrame, QMessageBox
)
from PyQt5.QtCore import Qt
from ui.common.base_dialog import BaseDialog
from PyQt5.QtGui import QFont, QIntValidator
from datetime import datetime
from ui.common.input_validators import apply_no_special_chars_validator


class AddProductDialog(BaseDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.populate_sku_dropdown()

    def setup_ui(self):
        self.setWindowTitle("Add Product")
        self.setModal(True)
        self.setFixedSize(700, 600)

        self.setStyleSheet(
            """
            QDialog { background-color: #2b2b2b; color: #ffffff; }
            QLabel { color: #ffffff; }
            QLineEdit, QComboBox {
                background-color: #404040; border: 1px solid #555555;
                padding: 8px; border-radius: 4px; color: #ffffff;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 2px solid #ff6b35; background-color: #454545;
            }
            QPushButton {
                background-color: #555555; border: 1px solid #666666; padding: 10px 20px;
                border-radius: 4px; color: #ffffff; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #666666; }
            """
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("Add Product")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setStyleSheet("color: #ff6b35; margin-bottom: 10px;")
        layout.addWidget(title)

        form_frame = QFrame()
        form_frame.setStyleSheet(
            """
            QFrame { background-color: #353535; border: 1px solid #555555; border-radius: 6px; padding: 20px; }
            """
        )
        form_layout = QFormLayout(form_frame)
        form_layout.setSpacing(12)

        # product_id
        id_label = QLabel("product_id *:")
        id_label.setStyleSheet("color: #ff6b35; font-weight: bold; min-width: 130px;")
        self.product_id_input = QLineEdit()
        self.product_id_input.setPlaceholderText("e.g., P0001")
        apply_no_special_chars_validator(self.product_id_input)
        form_layout.addRow(id_label, self.product_id_input)

        # product_name
        name_label = QLabel("product_name *:")
        name_label.setStyleSheet("color: #ff6b35; font-weight: bold; min-width: 130px;")
        self.product_name_input = QLineEdit()
        self.product_name_input.setPlaceholderText("e.g., Widget A")
        apply_no_special_chars_validator(self.product_name_input)
        form_layout.addRow(name_label, self.product_name_input)

        # sku_weight (grams) - optional
        weight_label = QLabel("sku_weight (g):")
        weight_label.setStyleSheet("color: #ffffff; font-weight: bold; min-width: 130px;")
        self.sku_weight_input = QLineEdit()
        self.sku_weight_input.setPlaceholderText("in grams, e.g., 250")
        self.sku_weight_input.setValidator(QIntValidator(0, 1000000000, self))
        form_layout.addRow(weight_label, self.sku_weight_input)

        # sku_location_id (now mapped from rack_id)
        sku_label = QLabel("sku_location_id *:")
        sku_label.setStyleSheet("color: #ff6b35; font-weight: bold; min-width: 130px;")
        self.sku_combo = QComboBox()
        self.sku_combo.setPlaceholderText("Select Rack ID")
        form_layout.addRow(sku_label, self.sku_combo)

        layout.addWidget(form_frame)

        hint = QLabel("* Required fields")
        hint.setStyleSheet("color: #cccccc; font-size: 12px;")
        layout.addWidget(hint)

        # Buttons
        buttons = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setAutoDefault(False)
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        save_btn = QPushButton("Add Product")
        save_btn.setAutoDefault(False)
        save_btn.setStyleSheet("QPushButton { background-color: #ff6b35; color: white; } QPushButton:hover { background-color: #e55a2b; }")
        save_btn.clicked.connect(self.on_save)
        buttons.addWidget(save_btn)

        layout.addLayout(buttons)

    def populate_sku_dropdown(self):
        try:
            csv_handler = self.parent().csv_handler
            rack_rows = csv_handler.read_csv('racks')
            self.sku_combo.addItem("Select Rack ID", "")
            seen = set()
            for row in rack_rows:
                rack_id = str(row.get('rack_id', '')).strip()
                if rack_id and rack_id not in seen:
                    self.sku_combo.addItem(rack_id, rack_id)
                    seen.add(rack_id)
        except Exception:
            # Non-fatal; leave dropdown empty
            pass

    def on_save(self):
        pid = self.product_id_input.text().strip()
        pname = self.product_name_input.text().strip()
        sku = self.sku_combo.currentData() or ''
        weight_text = self.sku_weight_input.text().strip()

        if not pid:
            QMessageBox.warning(self, "Validation Error", "product_id is not empty")
            self.product_id_input.setFocus()
            return
        if not pname:
            QMessageBox.warning(self, "Validation Error", "product_name is not empty")
            self.product_name_input.setFocus()
            return
        if not sku:
            QMessageBox.warning(self, "Validation Error", "Please select sku_location_id (rack_id)")
            self.sku_combo.setFocus()
            return
        if weight_text and not weight_text.isdigit():
            QMessageBox.warning(self, "Validation Error", "sku_weight must be a positive integer (grams)")
            self.sku_weight_input.setFocus()
            return

        self.accept()

    def get_product_data(self):
        now = datetime.now().isoformat()
        return {
            'product_id': self.product_id_input.text().strip(),
            'product_name': self.product_name_input.text().strip(),
            'sku_location_id': self.sku_combo.currentData() or '',
            'sku_weight': self.sku_weight_input.text().strip(),
            'created_at': now,
            'updated_at': now,
        }
