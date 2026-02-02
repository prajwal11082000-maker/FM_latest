from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QMessageBox, QSplitter
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
import re

from ui.common.table_widget import DataTableWidget
from api.client import APIClient
from data_manager.csv_handler import CSVHandler
from utils.logger import setup_logger
from datetime import datetime

from .add_product_dialog import AddProductDialog


class ProductManagementWidget(QWidget):
    product_updated = pyqtSignal()

    def __init__(self, api_client: APIClient, csv_handler: CSVHandler):
        super().__init__()
        self.api_client = api_client
        self.csv_handler = csv_handler
        self.logger = setup_logger('product_management')

        self.current_products = []

        self.setup_ui()
        self.refresh_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()
        header_layout.addStretch()

        # Add product button
        add_btn = QPushButton("➕ Add Product")
        add_btn.clicked.connect(self.show_add_product_dialog)
        add_btn.setStyleSheet(
            """
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
            """
        )
        header_layout.addWidget(add_btn)

        layout.addLayout(header_layout)

        # Main content area - single container with title and table (details panel removed)
        splitter = QSplitter(Qt.Horizontal)
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel("Product Details")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        title_label.setStyleSheet("color: #ffffff;")
        left_layout.addWidget(title_label)
        # Products table - include sku_weight after product_name
        self.products_table = DataTableWidget([
            "product_id", "product_name", "sku_weight", "sku_location_id"
        ], searchable=True, selectable=True)
        # No side details panel to update, but keep row selection behavior intact
        self.products_table.row_selected.connect(self.on_product_selected)
        left_layout.addWidget(self.products_table)
        splitter.addWidget(left_container)
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_title_label = QLabel("Product Quantity Details")
        right_title_label.setFont(QFont("Arial", 12, QFont.Bold))
        right_title_label.setStyleSheet("color: #ffffff;")
        right_layout.addWidget(right_title_label)
        self.qty_table = DataTableWidget([
            "product_name", "total_sku_weight", "total_quantity"
        ], searchable=True, selectable=False)
        right_layout.addWidget(self.qty_table)
        splitter.addWidget(right_container)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

        # Action buttons footer
        action_layout = QHBoxLayout()

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        action_layout.addWidget(refresh_btn)

        export_btn = QPushButton("📤 Export CSV")
        export_btn.clicked.connect(self.export_products)
        action_layout.addWidget(export_btn)

        action_layout.addStretch()

        for btn in [refresh_btn, export_btn]:
            btn.setStyleSheet(
                """
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
                """
            )

        layout.addLayout(action_layout)

    # Details panel removed

    def refresh_data(self):
        try:
            self.load_products()
        except Exception as e:
            self.logger.error(f"Error refreshing product data: {e}")

    def load_products(self):
        try:
            products = self.csv_handler.read_csv('products')
            self.current_products = products
            self.populate_products_table(products)
            self.populate_quantity_table()
            self.logger.info(f"Loaded {len(products)} products from CSV")
        except Exception as e:
            self.logger.error(f"Error loading products: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load products: {e}")

    def populate_products_table(self, products):
        self.products_table.clear_data()
        for p in products:
            row = [
                p.get('product_id', ''),
                p.get('product_name', ''),
                p.get('sku_weight', ''),
                p.get('sku_location_id', ''),
            ]
            self.products_table.add_row(row)

    def on_product_selected(self, row):
        """No details panel to update; keep method for signal compatibility."""
        return

    def populate_quantity_table(self):
        try:
            rows = self.calculate_product_quantities(self.current_products or [])
            self.qty_table.set_data(rows)
        except Exception as e:
            self.logger.error(f"Error populating product quantity details: {e}")

    def calculate_product_quantities(self, products):
        totals = {}
        counts = {}
        for p in products:
            name = (p.get('product_name') or '').strip()
            if not name:
                continue
            weight_val = self.parse_weight(p.get('sku_weight', ''))
            totals[name] = totals.get(name, 0.0) + weight_val
            if name not in counts:
                counts[name] = {}
            counts[name][weight_val] = counts[name].get(weight_val, 0) + 1
        rows = []
        for name in sorted(totals.keys()):
            weight_sum = totals[name]
            if abs(weight_sum - int(weight_sum)) < 1e-9:
                weight_str = f"{int(weight_sum)} grams"
            else:
                weight_str = f"{weight_sum:.2f} grams"
            quantity_total = sum(counts.get(name, {}).values())
            rows.append([name, weight_str, quantity_total])
        return rows

    def parse_weight(self, value):
        try:
            if value is None:
                return 0.0
            s = str(value).strip().lower()
            if s == '':
                return 0.0
            m = re.search(r'[-+]?\d*\.?\d+', s)
            if m:
                return float(m.group())
            return float(s)
        except Exception:
            return 0.0

    def show_add_product_dialog(self):
        dialog = AddProductDialog(self)
        if dialog.exec_() == AddProductDialog.Accepted:
            product_data = dialog.get_product_data()
            self.add_product(product_data)

    def add_product(self, product_data):
        try:
            # Validate
            validation = self.csv_handler.validate_csv_data('products', product_data)
            if not validation['valid']:
                error_msg = '\n'.join(validation['errors'])
                QMessageBox.critical(self, "Validation Error", f"Cannot save product:\n{error_msg}")
                return

            product_data = validation['data']

            # Ensure timestamps
            current_time = datetime.now().isoformat()
            product_data['created_at'] = product_data.get('created_at') or current_time
            product_data['updated_at'] = current_time

            if self.csv_handler.append_to_csv('products', product_data):
                QMessageBox.information(self, "Success", f"Product '{product_data['product_name']}' added!")
                self.refresh_data()
                self.logger.info(f"Added product: {product_data['product_id']}")
            else:
                raise Exception("Failed to save to CSV")

        except Exception as e:
            self.logger.error(f"Error adding product: {e}")
            QMessageBox.critical(self, "Error", f"Failed to add product: {e}")

    def export_products(self):
        from PyQt5.QtWidgets import QFileDialog
        import shutil
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Products", "products_export.csv", "CSV Files (*.csv)"
        )
        if file_path:
            try:
                products_csv_path = self.csv_handler.CSV_FILES['products'] if hasattr(self.csv_handler, 'CSV_FILES') else None
                if products_csv_path is None:
                    from config.settings import CSV_FILES
                    products_csv_path = CSV_FILES['products']
                shutil.copy2(products_csv_path, file_path)
                QMessageBox.information(self, "Success", f"Products exported to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Export failed: {e}")
