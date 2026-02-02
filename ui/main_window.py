from PyQt5.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                             QStackedWidget, QLabel, QFrame, QMessageBox, QStatusBar, QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont

from .sidebar import Sidebar

from api.client import APIClient
from api.auth import AuthAPI
from data_manager.csv_handler import CSVHandler
from data_manager.sync_manager import SyncManager
from utils.logger import setup_logger
from sync_device_locations import DeviceLocationSyncer


class MainWindow(QMainWindow):
    # Signals
    authentication_changed = pyqtSignal(bool)
    data_updated = pyqtSignal(str)  # Signal when data is updated

    def __init__(self):
        super().__init__()
        self.logger = setup_logger('main_window')

        # Initialize core components
        self.api_client = APIClient()
        self.auth_api = AuthAPI(self.api_client)
        self.csv_handler = CSVHandler()
        self.sync_manager = SyncManager(self.api_client, self.csv_handler)

        # Current user info
        self.current_user = None

        # Ensure CSV files exist with proper headers (including products)
        try:
            self.csv_handler.initialize_csv_files()
        except Exception as e:
            self.logger.debug(f"CSV initialization skipped or failed: {e}")

        # Setup UI
        self.setup_ui()
        self.setup_timers()
        self.setup_connections()

        # Try to connect to API (but don't fail if it's not available)
        self.check_api_connection()

    def setup_ui(self):
        """Setup the main user interface"""
        self.setWindowTitle("Warehouse Management System")
        self.setMinimumSize(1200, 800)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create sidebar
        self.sidebar = Sidebar()
        main_layout.addWidget(self.sidebar)

        # Create content area
        self.content_frame = QFrame()
        self.content_frame.setFrameStyle(QFrame.StyledPanel)
        main_layout.addWidget(self.content_frame)

        # Setup content layout
        content_layout = QVBoxLayout(self.content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # Create header
        self.create_header(content_layout)

        # Create stacked widget for different pages
        self.stacked_widget = QStackedWidget()
        content_layout.addWidget(self.stacked_widget)

        # Create and add pages
        self.create_pages()

        # Create status bar
        self.create_status_bar()

    def create_header(self, parent_layout):
        """Create the header section"""
        header_frame = QFrame()
        header_frame.setFixedHeight(60)
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #1f1f1f;
                border-bottom: 2px solid #ff6b35;
            }
        """)

        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(20, 0, 20, 0)

        # Title
        self.page_title = QLabel("Dashboard")
        self.page_title.setFont(QFont("Arial", 18, QFont.Bold))
        self.page_title.setStyleSheet("color: #ffffff;")
        header_layout.addWidget(self.page_title)

        header_layout.addStretch()

        # User info
        self.user_label = QLabel("CSV Mode - No API needed")
        self.user_label.setStyleSheet("color: #10B981; font-size: 12px; font-weight: bold;")
        header_layout.addWidget(self.user_label)

        parent_layout.addWidget(header_frame)

    def create_pages(self):
        """Create all application pages"""
        # Import widgets inside the method to avoid circular imports
        try:
            from ui.dashboard.dashboard_widget import DashboardWidget
            self.dashboard_widget = DashboardWidget(self.api_client, self.csv_handler)
            self.stacked_widget.addWidget(self.dashboard_widget)
            self.logger.info("Dashboard widget loaded successfully")
        except Exception as e:
            self.logger.error(f"Dashboard failed: {e}")
            self.dashboard_widget = self.create_placeholder("Dashboard", "📊 Dashboard data ready!")
            self.stacked_widget.addWidget(self.dashboard_widget)

        try:
            from ui.devices.device_list import DeviceListWidget
            self.device_list_widget = DeviceListWidget(self.api_client, self.csv_handler)
            self.stacked_widget.addWidget(self.device_list_widget)
            self.logger.info("Device Management widget loaded successfully")
        except Exception as e:
            self.logger.error(f"Device Management failed: {e}")
            self.device_list_widget = self.create_placeholder("Device Management", "🤖 12 devices available")
            self.stacked_widget.addWidget(self.device_list_widget)

        # Rack Management page (after Devices menu)
        try:
            from ui.racks.rack_management_widget import RackManagementWidget
            self.rack_management_widget = RackManagementWidget(self.api_client, self.csv_handler)
            self.stacked_widget.addWidget(self.rack_management_widget)
            self.logger.info("Rack Management widget loaded successfully")
        except Exception as e:
            self.logger.error(f"Rack Management failed: {e}")
            self.rack_management_widget = self.create_placeholder("Rack Management", "🗄️ View and manage racks from racks.csv")
            self.stacked_widget.addWidget(self.rack_management_widget)

        try:
            from ui.products.product_management import ProductManagementWidget
            self.product_management_widget = ProductManagementWidget(self.api_client, self.csv_handler)
            self.stacked_widget.addWidget(self.product_management_widget)
            self.logger.info("Product Management widget loaded successfully")
        except Exception as e:
            self.logger.error(f"Product Management failed: {e}")
            self.product_management_widget = self.create_placeholder("Product Management", "📦 Add and view products")
            self.stacked_widget.addWidget(self.product_management_widget)

        try:
            # Use the simple working task creation widget
            from ui.tasks.task_creation import TaskCreationWidget
            self.task_creation_widget = TaskCreationWidget(self.api_client, self.csv_handler)
            self.stacked_widget.addWidget(self.task_creation_widget)
            self.logger.info("Task Creation widget loaded successfully")
        except Exception as e:
            self.logger.error(f"Task Creation failed: {e}")
            # Create a simple working task creation widget as fallback
            self.task_creation_widget = self.create_simple_task_widget()
            self.stacked_widget.addWidget(self.task_creation_widget)

        try:
            from ui.tasks.task_monitor import TaskMonitorWidget
            self.task_monitor_widget = TaskMonitorWidget(self.api_client, self.csv_handler)
            self.stacked_widget.addWidget(self.task_monitor_widget)
            self.logger.info("Task Monitor widget loaded successfully")
        except Exception as e:
            self.logger.error(f"Task Monitor failed: {e}")
            self.task_monitor_widget = self.create_placeholder("Task Monitor", "📋 12 tasks in progress")
            self.stacked_widget.addWidget(self.task_monitor_widget)

        try:
            from ui.users.user_management import UserManagementWidget
            self.user_management_widget = UserManagementWidget(self.api_client, self.csv_handler)
            self.stacked_widget.addWidget(self.user_management_widget)
            self.logger.info("User Management widget loaded successfully")
        except Exception as e:
            self.logger.error(f"User Management failed: {e}")
            self.user_management_widget = self.create_placeholder("User Management", "👥 10 active users")
            self.stacked_widget.addWidget(self.user_management_widget)

        try:
            # Use the simple working map management widget
            from ui.maps.map_management import MapManagementWidget
            self.map_management_widget = MapManagementWidget(self.api_client, self.csv_handler)
            self.stacked_widget.addWidget(self.map_management_widget)
            self.logger.info("Map Management widget loaded successfully")
        except Exception as e:
            self.logger.error(f"Map Management failed: {e}")
            # Create a simple working map widget as fallback
            self.map_management_widget = self.create_simple_map_widget()
            self.stacked_widget.addWidget(self.map_management_widget)

        try:
            from ui.devices.device_tracking import DeviceTrackingWidget
            self.device_tracking_widget = DeviceTrackingWidget(self.api_client, self.csv_handler)
            self.stacked_widget.addWidget(self.device_tracking_widget)
            self.logger.info("Device Tracking widget loaded successfully")
        except Exception as e:
            self.logger.error(f"Device Tracking failed: {e}")
            self.device_tracking_widget = self.create_placeholder("Device Tracking", "📍 Real-time device tracking")
            self.stacked_widget.addWidget(self.device_tracking_widget)

        try:
            from ui.robot_control.robot_control_widget import RobotControlWidget
            self.robot_control_widget = RobotControlWidget(self.api_client, self.csv_handler)
            self.stacked_widget.addWidget(self.robot_control_widget)
            self.logger.info("Robot Control widget loaded successfully")
        except Exception as e:
            self.logger.error(f"Robot Control failed: {e}")
            self.robot_control_widget = self.create_placeholder("Robot Control", "🎮 Robot external control panel")
            self.stacked_widget.addWidget(self.robot_control_widget)

        # Set default page
        self.stacked_widget.setCurrentWidget(self.dashboard_widget)

    def create_placeholder(self, page_title, subtitle="Feature available"):
        """Create a better placeholder widget"""
        placeholder = QWidget()
        layout = QVBoxLayout(placeholder)
        layout.setAlignment(Qt.AlignCenter)

        # Title
        title_label = QLabel(page_title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Arial", 24, QFont.Bold))
        title_label.setStyleSheet("color: #ffffff; margin-bottom: 20px;")
        layout.addWidget(title_label)

        # Subtitle
        subtitle_label = QLabel(subtitle)
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setFont(QFont("Arial", 16))
        subtitle_label.setStyleSheet("color: #cccccc; margin-bottom: 20px;")
        layout.addWidget(subtitle_label)

        # Status message
        status_label = QLabel("✅ CSV data loaded and ready\n📊 Click refresh to view data")
        status_label.setAlignment(Qt.AlignCenter)
        status_label.setStyleSheet("color: #10B981; background-color: #353535; padding: 20px; border-radius: 10px;")
        layout.addWidget(status_label)

        return placeholder

    def create_simple_task_widget(self):
        """Create simple task creation widget as fallback"""
        from ui.tasks.task_creation import TaskCreationWidget
        try:
            return TaskCreationWidget(self.api_client, self.csv_handler)
        except Exception as e:
            self.logger.error(f"Even simple task widget failed: {e}")
            return self.create_placeholder("Task Creation", "➕ Task creation form loading...")

    def create_simple_map_widget(self):
        """Create simple map widget as fallback"""
        from ui.maps.map_management import MapManagementWidget
        try:
            return MapManagementWidget(self.api_client, self.csv_handler)
        except Exception as e:
            self.logger.error(f"Even simple map widget failed: {e}")
            return self.create_placeholder("Map Management", "🗺️ Map management loading...")

    def create_status_bar(self):
        """Create status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Add permanent widgets
        self.sync_status_label = QLabel("CSV Mode Ready")
        self.sync_status_label.setStyleSheet("color: #10B981;")
        self.status_bar.addPermanentWidget(self.sync_status_label)

        self.status_bar.showMessage("Application started - CSV data available")

    def setup_timers(self):
        """Setup periodic timers"""
        # API connection check timer (optional)
        self.connection_timer = QTimer()
        self.connection_timer.timeout.connect(self.check_api_connection)
        self.connection_timer.start(60000)  # Check every minute

        # Data refresh timer (for CSV mode)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_csv_data)
        self.refresh_timer.start(30000)  # Refresh every 30 seconds

    def setup_connections(self):
        """Setup signal connections"""
        # Sidebar navigation
        self.sidebar.page_changed.connect(self.change_page)

        # Data update signals
        self.data_updated.connect(self.on_data_updated)
        
        # Connect dashboard navigation (Quick Actions)
        if hasattr(self, 'dashboard_widget') and hasattr(self.dashboard_widget, 'navigation_requested'):
            self.dashboard_widget.navigation_requested.connect(self.change_page)
        
        # Connect task creation to monitor refresh
        if hasattr(self, 'task_creation_widget') and hasattr(self, 'task_monitor_widget'):
            self.task_creation_widget.task_created.connect(lambda _: self.task_monitor_widget.refresh_data())

    def change_page(self, page_name: str):
        """Change to specified page"""

        page_mapping = {
            'dashboard': (self.dashboard_widget, "Dashboard"),
            'devices': (self.device_list_widget, "Device Management"),
            'rack_management': (self.rack_management_widget, "Rack Management"),
            'add_product': (self.product_management_widget, "Product Management"),
            'create_task': (self.task_creation_widget, "Create Task"),
            'monitor_tasks': (self.task_monitor_widget, "Task Monitor"),
            'users': (self.user_management_widget, "User Management"),
            'maps': (self.map_management_widget, "Map Management"),
            'device_tracking': (self.device_tracking_widget, "Device Tracking"),
            'robot_control': (self.robot_control_widget, "Robot Control"),
        }

        if page_name in page_mapping:
            widget, page_title = page_mapping[page_name]
            self.stacked_widget.setCurrentWidget(widget)
            self.page_title.setText(page_title)

            # Refresh data when switching pages
            if hasattr(widget, 'refresh_data'):
                try:
                    widget.refresh_data()
                    self.logger.info(f"Refreshed data for {page_title}")
                except Exception as e:
                    self.logger.error(f"Failed to refresh data for {page_title}: {e}")

    def check_api_connection(self):
        """Check API connection status"""
        # Set default to CSV mode
        self.user_label.setText("CSV Mode - No API needed")
        self.user_label.setStyleSheet("color: #10B981; font-size: 12px; font-weight: bold;")
        
        # Only attempt API connection if explicitly configured
        try:
            import socket
            socket.setdefaulttimeout(2)  # Set timeout to 2 seconds
            if hasattr(self.api_client, 'base_url') and self.api_client.base_url:
                if self.api_client.test_connection():
                    self.user_label.setText("API Connected - Hybrid Mode")
                    self.user_label.setStyleSheet("color: #3B82F6; font-size: 12px; font-weight: bold;")
        except (ConnectionRefusedError, socket.timeout) as e:
            self.logger.debug(f"API not available: {e}")
        except Exception as e:
            self.logger.debug(f"API connection check failed: {e}")
        finally:
            socket.setdefaulttimeout(None)  # Reset timeout to default

    def refresh_csv_data(self):
        """Refresh CSV data periodically"""
        try:
            # Keep devices.csv in sync with per-device logs before emitting updates
            try:
                syncer = DeviceLocationSyncer()
                syncer.sync_device_locations()
            except Exception as sync_err:
                self.logger.debug(f"Device location sync skipped or failed: {sync_err}")

            # Signal that data might have been updated
            self.data_updated.emit("all")
        except Exception as e:
            self.logger.error(f"Error refreshing CSV data: {e}")

    def sync_data(self):
        """Sync data between API and local CSV"""
        if not self.api_client.is_authenticated():
            return

        try:
            self.sync_status_label.setText("Syncing...")

            # Perform sync in background
            success = self.sync_manager.sync_all_data()

            if success:
                self.sync_status_label.setText("Synced")
                self.sync_status_label.setStyleSheet("color: #10B981;")
                self.data_updated.emit("all")
            else:
                self.sync_status_label.setText("Sync failed")
                self.sync_status_label.setStyleSheet("color: #EF4444;")

        except Exception as e:
            self.logger.error(f"Sync error: {e}")
            self.sync_status_label.setText("Sync error")
            self.sync_status_label.setStyleSheet("color: #EF4444;")

    def on_data_updated(self, data_type: str):
        """Handle data update signals"""
        # Refresh current widget that might be affected
        current_widget = self.stacked_widget.currentWidget()
        if hasattr(current_widget, 'refresh_data'):
            try:
                current_widget.refresh_data()
                self.logger.debug(f"Refreshed current widget for data type: {data_type}")
            except Exception as e:
                self.logger.error(f"Failed to refresh current widget: {e}")

    def show_message(self, message_title: str, message_text: str, message_type: str = 'info'):
        """Show message box"""
        if message_type == 'error':
            QMessageBox.critical(self, message_title, message_text)
        elif message_type == 'warning':
            QMessageBox.warning(self, message_title, message_text)
        else:
            QMessageBox.information(self, message_title, message_text)

    def closeEvent(self, event):
        """Handle application close"""
        # Logout if authenticated
        if self.api_client.is_authenticated():
            self.auth_api.logout()

        # Stop timers
        if hasattr(self, 'connection_timer'):
            self.connection_timer.stop()
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()

        self.logger.info("Application closing")
        event.accept()