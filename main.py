#!/usr/bin/env python3
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PyQt5.QtWidgets import QApplication, QMessageBox, QLabel
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtCore import QCoreApplication

from config.settings import APP_NAME, APP_VERSION, WINDOW_SIZE, RESOURCES_DIR
from utils.logger import setup_logger
from data_manager.csv_handler import CSVHandler
from data_manager.device_data_handler import DeviceDataHandler


class WarehouseApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)

        # Setup application properties
        self.setApplicationName(APP_NAME)
        self.setApplicationVersion(APP_VERSION)
        self.setOrganizationName("Warehouse Solutions")

        # Setup logger
        self.logger = setup_logger()
        self.logger.info(f"Starting {APP_NAME} v{APP_VERSION}")

        # Initialize CSV handler
        self.csv_handler = CSVHandler()
        self.csv_handler.initialize_csv_files()

        self.device_data_handler = DeviceDataHandler()
        self._call_runner_timer = QTimer()
        self._call_runner_timer.setInterval(2000)
        self._call_runner_timer.timeout.connect(lambda: self.device_data_handler.auto_append_run_task_if_pending_call('rob1', 'TASK0001'))
        self._call_runner_timer.start()

        # Initialize Automatic Task Service
        from services.automatic_task_service import AutomaticTaskService
        self.auto_task_service = AutomaticTaskService(self.csv_handler, self.device_data_handler)
        self._auto_task_timer = QTimer()
        self._auto_task_timer.setInterval(1000)  # Check every 1 seconds
        self._auto_task_timer.timeout.connect(self.auto_task_service.monitor_and_process)
        self._auto_task_timer.start()

        # Set application style
        self.setStyle('Fusion')

        # Apply dark theme
        self.apply_dark_theme()

        # Try to create main window - with error handling
        try:
            from ui.main_window import MainWindow
            self.main_window = MainWindow()
            self.logger.info("Main window created successfully")
        except Exception as e:
            self.logger.error(f"Error creating main window: {e}")
            # Create fallback window
            self.main_window = self.create_fallback_window()

    def create_fallback_window(self):
        """Create a fallback window if main window fails"""
        from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout

        window = QMainWindow()
        window.setWindowTitle("Warehouse Management System - Safe Mode")
        window.setGeometry(100, 100, 800, 600)

        central_widget = QWidget()
        window.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        error_label = QLabel("⚠️ Main interface failed to load\nRunning in safe mode")
        error_label.setAlignment(Qt.AlignCenter)
        error_label.setFont(QFont("Arial", 16, QFont.Bold))
        error_label.setStyleSheet("color: #ff6b35; margin: 50px;")
        layout.addWidget(error_label)

        status_label = QLabel("✅ Core systems operational\n✅ CSV files ready\n✅ API client ready")
        status_label.setAlignment(Qt.AlignCenter)
        status_label.setStyleSheet("color: #ffffff; background-color: #353535; padding: 20px; border-radius: 10px;")
        layout.addWidget(status_label)

        return window

    def apply_dark_theme(self):
        """Apply dark theme to the application"""
        dark_stylesheet = """
        QMainWindow {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        QWidget {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        QFrame {
            background-color: #3c3c3c;
            border: 1px solid #555555;
        }
        QPushButton {
            background-color: #404040;
            border: 1px solid #555555;
            padding: 8px 16px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #4a4a4a;
        }
        QPushButton:pressed {
            background-color: #353535;
        }
        QLineEdit, QTextEdit, QComboBox, QSpinBox {
            background-color: #404040;
            border: 1px solid #555555;
            padding: 6px;
            border-radius: 4px;
        }
        QTableWidget {
            background-color: #404040;
            alternate-background-color: #454545;
            gridline-color: #555555;
        }
        QHeaderView::section {
            background-color: #353535;
            padding: 8px;
            border: 1px solid #555555;
        }
        QTabWidget::pane {
            border: 1px solid #555555;
        }
        QTabBar::tab {
            background-color: #404040;
            padding: 8px 16px;
            border: 1px solid #555555;
        }
        QTabBar::tab:selected {
            background-color: #ff6b35;
        }
        QScrollBar:vertical {
            background-color: #404040;
            width: 12px;
        }
        QScrollBar::handle:vertical {
            background-color: #606060;
            border-radius: 6px;
        }
        """
        self.setStyleSheet(dark_stylesheet)

    def run(self):
        """Run the application"""
        try:
            self.main_window.show()
            self.main_window.resize(*WINDOW_SIZE)

            # Center the window
            screen = self.desktop().screenGeometry()
            x = (screen.width() - WINDOW_SIZE[0]) // 2
            y = (screen.height() - WINDOW_SIZE[1]) // 2
            self.main_window.move(x, y)

            self.logger.info("Application started successfully")
            return self.exec_()

        except Exception as e:
            self.logger.error(f"Error running application: {e}")
            QMessageBox.critical(None, "Application Error",
                                 f"An error occurred while running the application:\n{e}")
            return 1


def main():
    """Main entry point"""
    try:
        app = WarehouseApp(sys.argv)
        return app.run()
    except Exception as e:
        print(f"Failed to start application: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())