from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QFrame, QPushButton, QScrollArea, QSizePolicy,
                             QProgressBar)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont

from .status_cards import StatusCardWidget
from api.client import APIClient
from api.devices import DevicesAPI
from api.tasks import TasksAPI
from data_manager.csv_handler import CSVHandler
from data_manager.notification_monitor import NotificationMonitor
from utils.logger import setup_logger


class DashboardWidget(QWidget):
    refresh_requested = pyqtSignal()
    navigation_requested = pyqtSignal(str)  # Signal to request navigation to a page

    def __init__(self, api_client: APIClient, csv_handler: CSVHandler):
        super().__init__()
        self.api_client = api_client
        self.csv_handler = csv_handler
        self.devices_api = DevicesAPI(api_client)
        self.tasks_api = TasksAPI(api_client)
        self.logger = setup_logger('dashboard')
        
        # Initialize notification monitor for device-specific alerts
        self.notification_monitor = NotificationMonitor(csv_handler)

        self.setup_ui()
        self.setup_timer()
        self.refresh_data()

    def setup_ui(self):
        """Setup dashboard UI with proper responsive design"""
        # Main layout - no margins since we don't want the duplicate title
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 20)  # No top margin to remove extra space
        layout.setSpacing(20)

        # Status cards section
        self.create_status_cards_section(layout)

        # Content area with scroll
        self.create_content_area(layout)

        # Refresh button at bottom
        self.create_refresh_button(layout)

    def create_status_cards_section(self, parent_layout):
        """Create responsive status cards grid"""
        cards_frame = QFrame()
        cards_frame.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
            }
        """)
        cards_layout = QGridLayout(cards_frame)
        cards_layout.setSpacing(20)
        cards_layout.setContentsMargins(5, 5, 5, 5)

        # Create status cards with proper sizing
        self.device_working_card = StatusCardWidget("Working Devices", "0", "#10B981", "🤖")
        self.device_charging_card = StatusCardWidget("Charging", "0", "#F59E0B", "🔋")
        self.device_issues_card = StatusCardWidget("Issues", "0", "#EF4444", "⚠️")
        self.device_total_card = StatusCardWidget("Total Devices", "0", "#6B7280", "📟")

        self.task_pending_card = StatusCardWidget("Pending Tasks", "0", "#3B82F6", "📋")
        self.task_running_card = StatusCardWidget("Running Tasks", "0", "#10B981", "🏃")
        self.task_completed_card = StatusCardWidget("Completed Today", "0", "#8B5CF6", "✅")
        self.task_failed_card = StatusCardWidget("Failed Tasks", "0", "#EF4444", "❌")

        # Add cards to responsive grid (4 columns, 2 rows)
        cards = [
            self.device_working_card, self.device_charging_card, self.device_issues_card, self.device_total_card,
            self.task_pending_card, self.task_running_card, self.task_completed_card, self.task_failed_card
        ]

        for i, card in enumerate(cards):
            row = i // 4
            col = i % 4
            cards_layout.addWidget(card, row, col)
            # Make columns expand equally
            cards_layout.setColumnStretch(col, 1)

        parent_layout.addWidget(cards_frame)

    def create_content_area(self, parent_layout):
        """Create scrollable content area"""
        # Main scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameStyle(QFrame.NoFrame)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Scroll content widget
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(20)
        scroll_layout.setContentsMargins(0, 0, 0, 0)

        # Main panels layout (Quick Actions + Fleet Battery Status side by side)
        panels_layout = QHBoxLayout()
        panels_layout.setSpacing(20)

        # Quick Actions Section (left side)
        self.create_quick_actions_section(panels_layout)

        # Fleet Battery Status Section (right side)
        self.create_fleet_battery_section(panels_layout)

        scroll_layout.addLayout(panels_layout)

        # System Alerts Section
        self.create_system_alerts_section(scroll_layout)

        scroll_area.setWidget(scroll_widget)
        parent_layout.addWidget(scroll_area)

    def create_quick_actions_section(self, parent_layout):
        """Create Quick Actions section with action buttons"""
        # Section frame
        actions_frame = QFrame()
        actions_frame.setStyleSheet("""
            QFrame {
                background-color: #353535;
                border: 1px solid #555555;
                border-radius: 8px;
            }
        """)
        actions_layout = QVBoxLayout(actions_frame)
        actions_layout.setSpacing(15)
        actions_layout.setContentsMargins(20, 20, 20, 20)

        # Section header with lightning icon
        header_layout = QHBoxLayout()
        header_icon = QLabel("⚡")
        header_icon.setStyleSheet("font-size: 16px; color: #F59E0B;")
        header_layout.addWidget(header_icon)
        
        actions_title = QLabel("Quick Actions")
        actions_title.setFont(QFont("Arial", 14, QFont.Bold))
        actions_title.setStyleSheet("color: #ffffff; margin-left: 5px;")
        header_layout.addWidget(actions_title)
        header_layout.addStretch()
        actions_layout.addLayout(header_layout)

        # Buttons grid layout (2 rows for 3 buttons)
        buttons_layout = QGridLayout()
        buttons_layout.setSpacing(15)

        # Button style template
        def create_action_button(text, icon_text, bg_color, hover_color):
            btn = QPushButton()
            btn.setMinimumSize(120, 90)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg_color};
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 11px;
                    font-weight: bold;
                    text-align: center;
                    padding: 10px;
                }}
                QPushButton:hover {{
                    background-color: {hover_color};
                }}
            """)
            
            # Create button with icon and text using layout
            btn_layout = QVBoxLayout(btn)
            btn_layout.setAlignment(Qt.AlignCenter)
            btn_layout.setSpacing(8)
            
            icon_label = QLabel(icon_text)
            icon_label.setAlignment(Qt.AlignCenter)
            icon_label.setStyleSheet("font-size: 24px; color: white; background: transparent;")
            btn_layout.addWidget(icon_label)
            
            text_label = QLabel(text)
            text_label.setAlignment(Qt.AlignCenter)
            text_label.setStyleSheet("font-size: 11px; font-weight: bold; color: white; background: transparent;")
            text_label.setWordWrap(True)
            btn_layout.addWidget(text_label)
            
            return btn

        # Create 3 action buttons
        self.view_tasks_btn = create_action_button("View All\nTasks", "📋", "#10B981", "#059669")
        self.view_tasks_btn.clicked.connect(lambda: self.emit_navigation("tasks"))
        
        self.track_devices_btn = create_action_button("Track\nDevices", "📍", "#F59E0B", "#D97706")
        self.track_devices_btn.clicked.connect(lambda: self.emit_navigation("tracking"))
        
        self.manual_control_btn = create_action_button("Manual\nControl", "🎮", "#3B82F6", "#2563EB")
        self.manual_control_btn.clicked.connect(lambda: self.emit_navigation("robot_control"))

        # Add buttons to grid (first row: 3 buttons)
        buttons_layout.addWidget(self.view_tasks_btn, 0, 0)
        buttons_layout.addWidget(self.track_devices_btn, 0, 1)
        buttons_layout.addWidget(self.manual_control_btn, 0, 2)

        actions_layout.addLayout(buttons_layout)
        actions_layout.addStretch()

        parent_layout.addWidget(actions_frame, 1)  # Stretch factor 1

    def emit_navigation(self, target):
        """Emit navigation signal to navigate to a specific page"""
        # Map internal targets to main_window page names
        page_mapping = {
            'tasks': 'monitor_tasks',
            'tracking': 'device_tracking',
            'robot_control': 'robot_control'
        }
        page_name = page_mapping.get(target, target)
        self.logger.info(f"Navigation requested: {page_name}")
        self.navigation_requested.emit(page_name)

    def create_fleet_battery_section(self, parent_layout):
        """Create Fleet Battery Status section with progress bars"""
        # Section frame
        battery_frame = QFrame()
        battery_frame.setStyleSheet("""
            QFrame {
                background-color: #353535;
                border: 1px solid #555555;
                border-radius: 8px;
            }
        """)
        battery_layout = QVBoxLayout(battery_frame)
        battery_layout.setSpacing(12)
        battery_layout.setContentsMargins(20, 20, 20, 20)

        # Section header
        header_layout = QHBoxLayout()
        header_icon = QLabel("🔋")
        header_icon.setStyleSheet("font-size: 16px; color: #10B981;")
        header_layout.addWidget(header_icon)
        
        battery_title = QLabel("Fleet Battery Status")
        battery_title.setFont(QFont("Arial", 14, QFont.Bold))
        battery_title.setStyleSheet("color: #ffffff; margin-left: 5px;")
        header_layout.addWidget(battery_title)
        header_layout.addStretch()
        
        # Low battery indicator
        low_battery_label = QLabel("🔺 3 on battery")
        low_battery_label.setStyleSheet("color: #EF4444; font-size: 11px;")
        header_layout.addWidget(low_battery_label)
        self.low_battery_label = low_battery_label
        
        battery_layout.addLayout(header_layout)

        # Container for device battery rows
        self.battery_container = QVBoxLayout()
        self.battery_container.setSpacing(8)
        battery_layout.addLayout(self.battery_container)
        
        battery_layout.addStretch()
        parent_layout.addWidget(battery_frame, 1)  # Stretch factor 1

    def create_battery_row(self, device_name, battery_level, status):
        """Create a single battery row widget"""
        row_widget = QWidget()
        row_widget.setStyleSheet("background-color: transparent;")
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 6, 0, 6)
        row_layout.setSpacing(10)
        
        # Status indicator dot
        status_colors = {
            'working': '#10B981',
            'charging': '#F59E0B',
            'issues': '#EF4444',
            'maintenance': '#8B5CF6',
            'idle': '#6B7280',
            'low battery': '#EF4444'
        }
        dot_color = status_colors.get(status.lower(), '#6B7280')
        
        status_dot = QLabel("●")
        status_dot.setStyleSheet(f"color: {dot_color}; font-size: 10px;")
        status_dot.setFixedWidth(15)
        row_layout.addWidget(status_dot)
        
        # Device name
        name_label = QLabel(device_name)
        name_label.setStyleSheet("color: #ffffff; font-size: 12px;")
        name_label.setFixedWidth(60)
        row_layout.addWidget(name_label)
        
        # Battery progress bar
        progress_bar = QProgressBar()
        progress_bar.setValue(battery_level)
        progress_bar.setTextVisible(False)
        progress_bar.setFixedHeight(12)
        
        # Color based on battery level
        if battery_level < 20:
            bar_color = "#EF4444"  # Red
        elif battery_level < 50:
            bar_color = "#F59E0B"  # Orange
        else:
            bar_color = "#10B981"  # Green
        
        progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #404040;
                border: none;
                border-radius: 6px;
            }}
            QProgressBar::chunk {{
                background-color: {bar_color};
                border-radius: 6px;
            }}
        """)
        row_layout.addWidget(progress_bar, 1)
        
        # Battery percentage
        percent_label = QLabel(f"{battery_level}%")
        percent_label.setStyleSheet("color: #9CA3AF; font-size: 11px;")
        percent_label.setFixedWidth(35)
        row_layout.addWidget(percent_label)
        
        # Status label
        status_label = QLabel(status.title())
        status_label.setStyleSheet(f"""
            color: white;
            background-color: {dot_color};
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 10px;
            font-weight: bold;
        """)
        status_label.setFixedWidth(75)
        status_label.setAlignment(Qt.AlignCenter)
        row_layout.addWidget(status_label)
        
        return row_widget

    def create_system_alerts_section(self, parent_layout):
        """Create System Alerts section"""
        # Section frame
        alerts_frame = QFrame()
        alerts_frame.setStyleSheet("""
            QFrame {
                background-color: #353535;
                border: 1px solid #555555;
                border-radius: 8px;
            }
        """)
        alerts_layout = QVBoxLayout(alerts_frame)
        alerts_layout.setSpacing(12)
        alerts_layout.setContentsMargins(20, 20, 20, 20)

        # Section header
        header_layout = QHBoxLayout()
        header_icon = QLabel("⚠️")
        header_icon.setStyleSheet("font-size: 16px; color: #F59E0B;")
        header_layout.addWidget(header_icon)
        
        alerts_title = QLabel("System Alerts")
        alerts_title.setFont(QFont("Arial", 14, QFont.Bold))
        alerts_title.setStyleSheet("color: #ffffff; margin-left: 5px;")
        header_layout.addWidget(alerts_title)
        header_layout.addStretch()
        alerts_layout.addLayout(header_layout)

        # Alerts container
        self.alerts_container = QVBoxLayout()
        self.alerts_container.setSpacing(8)
        alerts_layout.addLayout(self.alerts_container)
        
        # Default message when no alerts
        self.no_alerts_label = QLabel("No active alerts")
        self.no_alerts_label.setStyleSheet("color: #6B7280; font-size: 12px; padding: 10px;")
        self.alerts_container.addWidget(self.no_alerts_label)

        parent_layout.addWidget(alerts_frame)

    def add_alert(self, message, alert_type="warning"):
        """Add an alert to the alerts section"""
        alert_colors = {
            'warning': '#F59E0B',
            'error': '#EF4444',
            'info': '#3B82F6',
            'success': '#10B981'
        }
        color = alert_colors.get(alert_type, '#F59E0B')
        
        alert_widget = QWidget()
        alert_layout = QHBoxLayout(alert_widget)
        alert_layout.setContentsMargins(10, 8, 10, 8)
        
        # Alert indicator bar
        bar = QFrame()
        bar.setFixedWidth(4)
        bar.setStyleSheet(f"background-color: {color}; border-radius: 2px;")
        alert_layout.addWidget(bar)
        
        # Alert message
        msg_label = QLabel(message)
        msg_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold; margin-left: 10px;")
        msg_label.setWordWrap(True)
        alert_layout.addWidget(msg_label, 1)
        
        alert_widget.setStyleSheet(f"""
            QWidget {{
                background-color: #353535;
                border-radius: 6px;
                border-left: 3px solid {color};
            }}
        """)
        
        # Hide "no alerts" message
        self.no_alerts_label.hide()
        self.alerts_container.addWidget(alert_widget)

    def create_refresh_button(self, parent_layout):
        """Create refresh button"""
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        refresh_btn = QPushButton("🔄 Refresh Dashboard")
        refresh_btn.setFixedHeight(40)
        refresh_btn.clicked.connect(self.refresh_data)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff6b35;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                padding: 0 30px;
            }
            QPushButton:hover {
                background-color: #e55a2b;
            }
        """)
        button_layout.addWidget(refresh_btn)
        button_layout.addStretch()

        parent_layout.addLayout(button_layout)

    def setup_timer(self):
        """Setup refresh timers"""
        # Main dashboard refresh timer (30 seconds for full UI updates including status cards)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(30000)  # Refresh every 30 seconds
        
        # Notification sync timer (500ms for real-time monitoring - faster than 1 second)
        self.notification_sync_timer = QTimer()
        self.notification_sync_timer.timeout.connect(self.sync_device_notifications)
        self.notification_sync_timer.start(500)  # Sync every 500ms (half second)

    def sync_device_notifications(self):
        """Sync device notifications every 1 second - updates devices.csv, alerts, and battery display"""
        try:
            # This runs the notification monitor which:
            # 1. Updates battery_level in devices.csv from Battery_status files
            # 2. Updates status in devices.csv when charging
            # 3. Collects alarm and obstacle notifications
            self.notification_monitor.scan_for_notifications()
            
            # Refresh the System Alerts section to show new notifications immediately
            self.load_system_alerts()
            
            # Refresh the Fleet Battery Status to show updated battery levels
            self.load_fleet_battery_status()
            
        except Exception as e:
            self.logger.error(f"Error syncing device notifications: {e}")

    def refresh_data(self):
        """Refresh all dashboard data (called every 30 seconds for full refresh)"""
        self.load_device_status()
        self.load_task_status()
        self.load_fleet_battery_status()
        self.load_system_alerts()

    def load_device_status(self):
        """Load device status from CSV and API"""
        try:
            # Try API first
            if self.api_client.is_authenticated():
                response = self.devices_api.get_status_summary()
                if 'error' not in response:
                    self.update_device_cards(response)
                    return

            # Fallback to CSV
            devices = self.csv_handler.read_csv('devices')
            status_counts = {
                'working': 0,
                'charging': 0,
                'issues': 0,
                'total': len(devices)
            }

            for device in devices:
                status = device.get('status', '').lower()
                if status in status_counts:
                    status_counts[status] += 1

            self.update_device_cards(status_counts)

        except Exception as e:
            self.logger.error(f"Error loading device status: {e}")
            # Set default values on error
            self.update_device_cards({'working': 0, 'charging': 0, 'issues': 0, 'total': 0})

    def update_device_cards(self, data):
        """Update device status cards"""
        self.device_working_card.update_value(str(data.get('working', 0)))
        self.device_charging_card.update_value(str(data.get('charging', 0)))
        self.device_issues_card.update_value(str(data.get('issues', 0)))
        self.device_total_card.update_value(str(data.get('total', 0)))

    def load_task_status(self):
        """Load task status from CSV and API"""
        try:
            # Try API first
            if self.api_client.is_authenticated():
                response = self.tasks_api.get_task_summary()
                if 'error' not in response:
                    self.update_task_cards(response)
                    return

            # Fallback to CSV
            tasks = self.csv_handler.read_csv('tasks')
            status_counts = {
                'pending': 0,
                'running': 0,
                'completed': 0,
                'failed': 0
            }

            for task in tasks:
                status = task.get('status', '').lower()
                if status in status_counts:
                    status_counts[status] += 1

            self.update_task_cards(status_counts)

        except Exception as e:
            self.logger.error(f"Error loading task status: {e}")
            # Set default values on error
            self.update_task_cards({'pending': 0, 'running': 0, 'completed': 0, 'failed': 0})

    def update_task_cards(self, data):
        """Update task status cards"""
        self.task_pending_card.update_value(str(data.get('pending', 0)))
        self.task_running_card.update_value(str(data.get('running', 0)))
        self.task_completed_card.update_value(str(data.get('completed', 0)))
        self.task_failed_card.update_value(str(data.get('failed', 0)))

    def load_fleet_battery_status(self):
        """Load fleet battery status and populate the battery panel"""
        try:
            # Clear existing battery rows
            while self.battery_container.count():
                item = self.battery_container.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            devices = []
            
            # Try API first
            if self.api_client.is_authenticated():
                response = self.devices_api.list_devices({})
                if 'error' not in response:
                    devices = response.get('results', response) if isinstance(response, dict) else response
            
            # Fallback to CSV
            if not devices:
                devices = self.csv_handler.read_csv('devices')
            
            # Count low battery devices
            low_battery_count = 0
            
            for device in devices:
                device_name = device.get('device_id', device.get('device_name', 'Unknown'))
                battery_level = device.get('battery_level', 50)
                status = device.get('status', 'idle')
                
                # Ensure battery_level is an integer
                try:
                    battery_level = int(battery_level) if battery_level else 50
                except (ValueError, TypeError):
                    battery_level = 50
                
                # Count low battery
                if battery_level < 30:
                    low_battery_count += 1
                
                # Create battery row
                row_widget = self.create_battery_row(device_name, battery_level, status)
                self.battery_container.addWidget(row_widget)
            
            # Update low battery label
            self.low_battery_label.setText(f"🔺 {low_battery_count} on battery")
            
        except Exception as e:
            self.logger.error(f"Error loading fleet battery status: {e}")

    def load_system_alerts(self):
        """Load system alerts for various device conditions"""
        try:
            # Clear existing alerts (except "no alerts" label)
            for i in range(self.alerts_container.count() - 1, -1, -1):
                item = self.alerts_container.itemAt(i)
                if item.widget() and item.widget() != self.no_alerts_label:
                    item.widget().deleteLater()
            
            has_alerts = False
            
            # Get notifications from the notification monitor (obstacle, alarms, charging)
            try:
                device_notifications = self.notification_monitor.scan_for_notifications()
                for notif in device_notifications:
                    self.add_alert(notif['message'], notif['alert_type'])
                    has_alerts = True
            except Exception as e:
                self.logger.error(f"Error getting device notifications: {e}")
            
            # Get devices data for status-based alerts
            devices = []
            if self.api_client.is_authenticated():
                response = self.devices_api.list_devices({})
                if 'error' not in response:
                    devices = response.get('results', response) if isinstance(response, dict) else response
            
            if not devices:
                devices = self.csv_handler.read_csv('devices')
            
            for device in devices:
                status = device.get('status', '').lower()
                battery_level = device.get('battery_level', 100)
                device_id = device.get('device_id', device.get('device_name', 'Unknown'))
                
                try:
                    battery_level = int(battery_level) if battery_level else 100
                except (ValueError, TypeError):
                    battery_level = 100
                
                # Alert 1: Device has issues
                if status == 'issues':
                    self.add_alert(f"Device {device_id} has issues", "error")
                    has_alerts = True
                
                # Alert 2: Device is charging (from status, not log file)
                if status == 'charging':
                    self.add_alert(f"Device {device_id} is charging", "info")
                    has_alerts = True
                
                # Alert 3: Device is in maintenance
                if status == 'maintenance':
                    self.add_alert(f"Device {device_id} is under maintenance", "warning")
                    has_alerts = True
                
                # Alert 4: Low battery (<=20%)
                if battery_level <= 20:
                    self.add_alert(f"Device {device_id} battery critically low ({battery_level}%)", "error")
                    has_alerts = True
            
            # Show "no alerts" if there are no alerts
            if not has_alerts:
                self.no_alerts_label.show()
            else:
                self.no_alerts_label.hide()
                
        except Exception as e:
            self.logger.error(f"Error loading system alerts: {e}")