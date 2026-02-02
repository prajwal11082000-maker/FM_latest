from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class SimpleDashboardWidget(QWidget):
    def __init__(self, api_client=None, csv_handler=None):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        """Setup simple dashboard UI"""
        layout = QVBoxLayout(self)

        title = QLabel("Dashboard Working!")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 20, QFont.Bold))
        title.setStyleSheet("color: #ffffff; margin: 50px;")
        layout.addWidget(title)

        status = QLabel("✅ Dashboard initialized successfully")
        status.setAlignment(Qt.AlignCenter)
        status.setStyleSheet("color: #cccccc;")
        layout.addWidget(status)

    def refresh_data(self):
        """Refresh data method"""
        pass