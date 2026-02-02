from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QComboBox, QMessageBox, QFrame, QSplitter,
                             QTabWidget, QScrollArea, QGroupBox, QFormLayout,
                             QLineEdit, QCheckBox, QTableWidget, QTableWidgetItem,
                             QHeaderView, QAbstractItemView, QMenu, QAction)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QDate
from PyQt5.QtGui import QFont, QIcon, QPixmap, QColor, QPainter, QRegion
import os

from .add_user_dialog import AddUserDialog
from ui.common.table_widget import DataTableWidget
from api.client import APIClient
from api.users import UsersAPI
from data_manager.csv_handler import CSVHandler
from data_manager.sync_manager import SyncManager
from utils.logger import setup_logger
from datetime import datetime
import re


class UserManagementWidget(QWidget):
    user_updated = pyqtSignal()

    def __init__(self, api_client: APIClient, csv_handler: CSVHandler):
        super().__init__()
        self.api_client = api_client
        self.csv_handler = csv_handler
        self.users_api = UsersAPI(api_client)
        self.sync_manager = SyncManager(api_client, csv_handler)
        self.logger = setup_logger('user_management')

        # Data storage
        self.current_users = []
        self.filtered_users = []
        self.selected_user = None
        self.selected_user_index = None

        self.setup_ui()
        self.refresh_data()

    def setup_ui(self):
        """Setup user management UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Main content with tabs
        self.create_main_content(layout)

        # Action buttons
        self.create_action_buttons(layout)

    def create_header(self, parent_layout):
        """Create header section"""
        # Header section removed as per requirements
        pass

    def create_main_content(self, parent_layout):
        """Create main content with tabs"""
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #555555;
                background-color: #2b2b2b;
            }
            QTabBar::tab {
                background-color: #404040;
                color: #ffffff;
                padding: 10px 20px;
                margin-right: 2px;
                border: 1px solid #555555;
                border-bottom: none;
                border-radius: 6px 6px 0 0;
            }
            QTabBar::tab:selected {
                background-color: #ff6b35;
                color: #ffffff;
            }
            QTabBar::tab:hover:!selected {
                background-color: #4a4a4a;
            }
        """)

        # Create user statistics labels
        self.total_users_label = QLabel("Total Users: 0")
        self.total_users_label.setStyleSheet("color: #3B82F6; font-weight: bold; margin-left: 10px;")
        
        self.active_users_label = QLabel("Active: 0")
        self.active_users_label.setStyleSheet("color: #10B981; font-weight: bold; margin-left: 10px;")
        
        self.inactive_users_label = QLabel("Inactive: 0")
        self.inactive_users_label.setStyleSheet("color: #EF4444; font-weight: bold; margin-left: 10px;")
        
        # Create Add New User button
        add_user_btn = QPushButton("➕ Add New User")
        add_user_btn.clicked.connect(self.show_add_user_dialog)
        add_user_btn.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: white;
                border: none;
                padding: 8px 12px;
                border-radius: 6px;
                font-weight: bold;
                margin-left: 15px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        
        # Create a widget to hold both stats and the button
        corner_widget = QWidget()
        corner_layout = QHBoxLayout(corner_widget)
        corner_layout.setContentsMargins(0, 0, 10, 0)
        corner_layout.addWidget(self.total_users_label)
        corner_layout.addWidget(self.active_users_label)
        corner_layout.addWidget(self.inactive_users_label)
        corner_layout.addWidget(add_user_btn)
        
        # Add stats and button to the top right corner of the tab widget
        self.tab_widget.setCornerWidget(corner_widget, Qt.TopRightCorner)

        # Tab 1: User List & Management
        self.users_tab = self.create_users_tab()
        self.tab_widget.addTab(self.users_tab, "👥 User Directory")

        # Tab 2: User Details & Profile
        #self.profile_tab = self.create_profile_tab()
        #self.tab_widget.addTab(self.profile_tab, "👤 User Profile")


        parent_layout.addWidget(self.tab_widget)

    def create_users_tab(self):
        """Create users list and management tab"""
        tab_widget = QWidget()
        layout = QHBoxLayout(tab_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Left panel - Users table with filters
        left_panel = self.create_users_table_panel()
        layout.addWidget(left_panel, 3)

        # Right panel - Quick actions
        right_panel = self.create_quick_actions_panel()
        layout.addWidget(right_panel, 1)

        return tab_widget

    def create_users_table_panel(self):
        """Create users table panel"""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: #353535;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 15px;
            }
        """)
        layout = QVBoxLayout(panel)

        # Filters section
        filters_layout = QHBoxLayout()

        # Status filter
        status_label = QLabel("Filter:")
        status_label.setStyleSheet("color: #cccccc; font-weight: bold;")
        filters_layout.addWidget(status_label)

        self.status_filter = QComboBox()
        self.status_filter.addItem("All Users", "all")
        self.status_filter.addItem("✅ Active Only", "active")
        self.status_filter.addItem("❌ Inactive Only", "inactive")
        self.status_filter.addItem("🆕 Recent (30 days)", "recent")
        self.status_filter.currentTextChanged.connect(self.filter_users)
        self.apply_combo_style(self.status_filter)
        filters_layout.addWidget(self.status_filter)

        # Search box
        search_label = QLabel("Search:")
        search_label.setStyleSheet("color: #cccccc; font-weight: bold;")
        filters_layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name, email, or employee ID...")
        self.search_input.textChanged.connect(self.search_users)
        self.apply_input_style(self.search_input)
        filters_layout.addWidget(self.search_input)

        # Clear search
        clear_search_btn = QPushButton("❌")
        clear_search_btn.setFixedSize(30, 30)
        clear_search_btn.clicked.connect(self.clear_search)
        clear_search_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)
        filters_layout.addWidget(clear_search_btn)

        layout.addLayout(filters_layout)

        # Users table
        self.users_table = DataTableWidget([
            "Status", "Username", "Email", "Employee ID", "Role", "Created"
        ], searchable=False, selectable=True)  # We handle search ourselves

        self.users_table.row_selected.connect(self.on_user_selected)
        self.users_table.row_double_clicked.connect(self.on_user_double_clicked)

        # Add context menu to table
        self.users_table.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.users_table.table.customContextMenuRequested.connect(self.show_context_menu)

        layout.addWidget(self.users_table)

        return panel

    def create_quick_actions_panel(self):
        """Create quick actions panel"""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: #353535;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 15px;
            }
        """)
        layout = QVBoxLayout(panel)

        # Selected user info
        self.selected_user_info = QGroupBox("Selected User")
        self.selected_user_info.setStyleSheet(self.get_groupbox_style())
        info_layout = QVBoxLayout(self.selected_user_info)

        self.user_avatar_label = QLabel()
        self.user_avatar_label.setAlignment(Qt.AlignCenter)
        self.user_avatar_label.setStyleSheet("margin: 5px;")
        self.user_avatar_label.setMinimumHeight(200)
        self.user_avatar_label.setMinimumWidth(400)
        self.user_avatar_label.setMaximumHeight(200)
        self.user_avatar_label.setMaximumWidth(400)
        info_layout.addWidget(self.user_avatar_label)

        self.user_name_label = QLabel("No user selected")
        self.user_name_label.setAlignment(Qt.AlignCenter)
        self.user_name_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 14px;")
        info_layout.addWidget(self.user_name_label)

        self.user_role_label = QLabel("")
        self.user_role_label.setAlignment(Qt.AlignCenter)
        self.user_role_label.setStyleSheet("color: #cccccc; font-size: 12px;")
        info_layout.addWidget(self.user_role_label)

        self.user_status_label = QLabel("")
        self.user_status_label.setAlignment(Qt.AlignCenter)
        self.user_status_label.setStyleSheet("font-size: 12px; margin: 5px;")
        info_layout.addWidget(self.user_status_label)

        layout.addWidget(self.selected_user_info)

        # User actions
        actions_group = QGroupBox("User Actions")
        actions_group.setStyleSheet(self.get_groupbox_style())
        actions_layout = QVBoxLayout(actions_group)

        # Edit user
        self.edit_user_btn = QPushButton("✏️ Edit User")
        self.edit_user_btn.clicked.connect(self.edit_selected_user)
        self.edit_user_btn.setEnabled(False)
        self.apply_button_style(self.edit_user_btn)
        actions_layout.addWidget(self.edit_user_btn)

        # Toggle status
        self.toggle_status_btn = QPushButton("🔄 Toggle Status")
        self.toggle_status_btn.clicked.connect(self.toggle_user_status)
        self.toggle_status_btn.setEnabled(False)
        self.apply_button_style(self.toggle_status_btn)
        actions_layout.addWidget(self.toggle_status_btn)

        # Reset password
        self.reset_password_btn = QPushButton("🔑 Reset Password")
        self.reset_password_btn.clicked.connect(self.reset_user_password)
        self.reset_password_btn.setEnabled(False)
        self.apply_button_style(self.reset_password_btn)
        actions_layout.addWidget(self.reset_password_btn)

        # Delete user
        self.delete_user_btn = QPushButton("🗑️ Delete User")
        self.delete_user_btn.clicked.connect(self.delete_selected_user)
        self.delete_user_btn.setEnabled(False)
        self.delete_user_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
        """)
        actions_layout.addWidget(self.delete_user_btn)

        layout.addWidget(actions_group)

        layout.addStretch()

        return panel

    def create_profile_tab(self):
        """Create user profile details tab"""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setContentsMargins(20, 20, 20, 20)

        # Profile view (shows when user is selected)
        self.profile_frame = QFrame()
        self.profile_frame.setStyleSheet("""
            QFrame {
                background-color: #353535;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 20px;
            }
        """)
        profile_layout = QVBoxLayout(self.profile_frame)

        # Profile header
        header_layout = QHBoxLayout()

        # Avatar and basic info
        avatar_layout = QVBoxLayout()
        self.profile_avatar = QLabel()
        self.profile_avatar.setAlignment(Qt.AlignCenter)
        self.profile_avatar.setStyleSheet("margin: 10px;")
        self.profile_avatar.setMinimumHeight(96)
        self.profile_avatar.setMinimumWidth(96)
        self.profile_avatar.setMaximumHeight(96)
        self.profile_avatar.setMaximumWidth(96)
        avatar_layout.addWidget(self.profile_avatar)

        self.profile_name = QLabel("Select a user")
        self.profile_name.setAlignment(Qt.AlignCenter)
        self.profile_name.setFont(QFont("Arial", 18, QFont.Bold))
        self.profile_name.setStyleSheet("color: #ffffff; margin: 10px;")
        avatar_layout.addWidget(self.profile_name)

        header_layout.addLayout(avatar_layout)

        # Profile details
        details_layout = QFormLayout()

        self.profile_username = QLabel("-")
        self.profile_email = QLabel("-")
        self.profile_employee_id = QLabel("-")
        self.profile_status = QLabel("-")
        self.profile_last_login = QLabel("-")
        self.profile_created = QLabel("-")

        details_layout.addRow("Username:", self.profile_username)
        details_layout.addRow("Email:", self.profile_email)
        details_layout.addRow("Employee ID:", self.profile_employee_id)
        details_layout.addRow("Status:", self.profile_status)
        details_layout.addRow("Last Login:", self.profile_last_login)
        details_layout.addRow("Account Created:", self.profile_created)

        # Style profile labels
        for i in range(details_layout.rowCount()):
            label = details_layout.itemAt(i, QFormLayout.LabelRole)
            field = details_layout.itemAt(i, QFormLayout.FieldRole)
            if label:
                label.widget().setStyleSheet("color: #cccccc; font-weight: bold;")
            if field:
                field.widget().setStyleSheet("color: #ffffff;")

        header_layout.addLayout(details_layout)
        profile_layout.addLayout(header_layout)

        # Activity section
        activity_group = QGroupBox("Recent Activity")
        activity_group.setStyleSheet(self.get_groupbox_style())
        activity_layout = QVBoxLayout(activity_group)

        self.activity_list = QLabel("No recent activity")
        self.activity_list.setStyleSheet("color: #cccccc; padding: 10px;")
        self.activity_list.setWordWrap(True)
        activity_layout.addWidget(self.activity_list)

        profile_layout.addWidget(activity_group)

        layout.addWidget(self.profile_frame)

        return tab_widget


    def create_action_buttons(self, parent_layout):
        """Create action buttons"""
        action_layout = QHBoxLayout()

        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh Data")
        refresh_btn.clicked.connect(self.refresh_data)
        self.apply_button_style(refresh_btn)
        action_layout.addWidget(refresh_btn)

        # Sync button
        sync_btn = QPushButton("🔄 Sync with API")
        sync_btn.clicked.connect(self.sync_with_api)
        self.apply_button_style(sync_btn)
        action_layout.addWidget(sync_btn)

        # Bulk actions
        bulk_btn = QPushButton("📋 Bulk Actions")
        bulk_btn.clicked.connect(self.show_bulk_actions)
        self.apply_button_style(bulk_btn)
        action_layout.addWidget(bulk_btn)

        action_layout.addStretch()

        # Export button
        export_btn = QPushButton("📤 Export Users")
        export_btn.clicked.connect(self.export_users)
        self.apply_button_style(export_btn)
        action_layout.addWidget(export_btn)

        # Import button
        import_btn = QPushButton("📥 Import Users")
        import_btn.clicked.connect(self.import_users)
        self.apply_button_style(import_btn)
        action_layout.addWidget(import_btn)

        parent_layout.addLayout(action_layout)

    def get_groupbox_style(self):
        """Get groupbox styling"""
        return """
            QGroupBox {
                color: #ffffff;
                border: 1px solid #666666;
                border-radius: 6px;
                padding-top: 15px;
                margin: 10px 0;
                font-weight: bold;
            }
            QGroupBox::title {
                color: #ff6b35;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """

    def apply_combo_style(self, combo):
        """Apply combobox styling"""
        combo.setStyleSheet("""
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

    def apply_input_style(self, widget):
        """Apply input styling"""
        widget.setStyleSheet("""
            QLineEdit {
                background-color: #404040;
                border: 1px solid #555555;
                padding: 8px;
                border-radius: 4px;
                color: #ffffff;
            }
            QLineEdit:focus {
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
            QPushButton:disabled {
                background-color: #444444;
                color: #888888;
            }
        """)

    def get_default_avatar_path(self):
        """Return absolute path to default avatar asset"""
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'resources', 'default_avatar.svg'))

    def build_full_layout_avatar(self, image_path: str, size: int) -> QPixmap:
        """Load image and scale to fill size x size with full layout (no clipping)"""
        pix = QPixmap(image_path)
        if pix.isNull():
            return None
        # Scale to fit the size while maintaining aspect ratio
        scaled = pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return scaled

    def build_circular_avatar(self, image_path: str, size: int) -> QPixmap:
        """Load image, scale to fill size x size, and clip to a circle"""
        pix = QPixmap(image_path)
        if pix.isNull():
            return None
        scaled = pix.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        result = QPixmap(size, size)
        result.fill(Qt.transparent)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setClipRegion(QRegion(0, 0, size, size, QRegion.Ellipse))
        # center the scaled image
        x = (size - scaled.width()) // 2
        y = (size - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        painter.end()
        return result

    def set_avatar_pixmap(self, label: QLabel, profile_picture: str, size: int):
        """Helper to set avatar image on a label using full layout"""
        image_path = None
        if profile_picture and os.path.exists(profile_picture):
            image_path = profile_picture
        else:
            default_path = self.get_default_avatar_path()
            if os.path.exists(default_path):
                image_path = default_path

        if image_path:
            pix = self.build_full_layout_avatar(image_path, size)
            if pix:
                label.setPixmap(pix)
                label.setAlignment(Qt.AlignCenter)
                return

        # Fallback to emoji/text if everything fails
        label.setText("👤")
        label.setPixmap(QPixmap())
        label.setAlignment(Qt.AlignCenter)

    def refresh_data(self):
        """Refresh user data"""
        self.logger.info("Refreshing user data...")
        self.load_users()

    def load_users(self):
        """Load users from API or CSV - MAIN CRUD READ OPERATION"""
        try:
            # Try API first
            if self.api_client.is_authenticated():
                response = self.users_api.list_users()
                if 'error' not in response:
                    users_data = response.get('results', response) if isinstance(response, dict) else response
                    self.current_users = users_data
                    self.apply_current_filters()
                    self.update_user_stats()
                    self.logger.info(f"Loaded {len(users_data)} users from API")
                    return

            # Fallback to CSV
            users = self.csv_handler.read_csv('users')
            self.current_users = users
            self.apply_current_filters()
            self.update_user_stats()
            self.logger.info(f"Loaded {len(users)} users from CSV")

        except Exception as e:
            self.logger.error(f"Error loading users: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load users: {e}")
            # Try to repair CSV if loading failed
            self.csv_handler.repair_csv_file('users')
            try:
                users = self.csv_handler.read_csv('users')
                self.current_users = users
                self.apply_current_filters()
                self.update_user_stats()
                self.logger.info(f"Loaded {len(users)} users from repaired CSV")
            except Exception as repair_error:
                self.logger.error(f"Even repair failed: {repair_error}")
                self.current_users = []
                self.apply_current_filters()
                self.update_user_stats()

    def apply_current_filters(self):
        """Apply current filter and search settings"""
        self.filter_users()

    def filter_users(self):
        """Filter users based on status and search - CRUD READ with filtering"""
        filtered = self.current_users.copy()

        # Apply status filter
        status_filter = self.status_filter.currentData()
        if status_filter == "active":
            filtered = [u for u in filtered if self.is_user_active(u)]
        elif status_filter == "inactive":
            filtered = [u for u in filtered if not self.is_user_active(u)]
        elif status_filter == "recent":
            # Users created in last 30 days
            from datetime import datetime, timedelta
            thirty_days_ago = datetime.now() - timedelta(days=30)
            filtered = [u for u in filtered if self.is_user_recent(u, thirty_days_ago)]

        # Apply search filter
        search_term = self.search_input.text().lower().strip()
        if search_term:
            filtered = [u for u in filtered if self.user_matches_search(u, search_term)]

        self.filtered_users = filtered
        self.populate_users_table()

    def search_users(self):
        """Handle search input changes"""
        self.filter_users()

    def clear_search(self):
        """Clear search input"""
        self.search_input.clear()

    def is_user_active(self, user):
        """Check if user is active"""
        is_active = user.get('is_active', True)
        if isinstance(is_active, str):
            return is_active.lower() == 'true'
        return bool(is_active)

    def is_user_recent(self, user, cutoff_date):
        """Check if user was created recently"""
        created_at = user.get('created_at') or user.get('date_joined', '')
        if created_at:
            try:
                user_date = datetime.fromisoformat(created_at.replace('Z', ''))
                return user_date >= cutoff_date
            except:
                pass
        return False

    def user_matches_search(self, user, search_term):
        """Check if user matches search term"""
        searchable_fields = [
            user.get('username', ''),
            user.get('email', ''),
            user.get('employee_id', '')
        ]

        return any(search_term in field.lower() for field in searchable_fields if field)

    def populate_users_table(self):
        """Populate users table with filtered data"""
        self.users_table.clear_data()

        for user in self.filtered_users:
            # Status with emoji
            is_active = self.is_user_active(user)
            status = "✅ Active" if is_active else "❌ Inactive"

            # Username for display
            username = user.get('username', 'Unknown')

            # Employee ID with fallback
            employee_id = user.get('employee_id', '') or 'N/A'

            # Role (derived or default)
            role = user.get('role', 'Staff')

            # Last login formatting
            last_login = user.get('last_login', '')
            if last_login and last_login != 'Never':
                try:
                    last_login = last_login[:16].replace('T', ' ')
                except:
                    pass
            else:
                last_login = 'Never'

            # Created date
            created_at = user.get('created_at') or user.get('date_joined', '')
            if created_at:
                created_at = created_at[:10]
            else:
                created_at = 'Unknown'

            row_data = [
                status,
                user.get('username', ''),
                user.get('email', ''),
                employee_id,
                role,
                created_at
            ]
            self.users_table.add_row(row_data)

    def update_user_stats(self):
        """Update user statistics"""
        total = len(self.current_users)
        active = len([u for u in self.current_users if self.is_user_active(u)])
        inactive = total - active

        self.total_users_label.setText(f"Total Users: {total}")
        self.active_users_label.setText(f"Active: {active}")
        self.inactive_users_label.setText(f"Inactive: {inactive}")


    def show_add_user_dialog(self):
        """Show add user dialog - CRUD CREATE OPERATION"""
        dialog = AddUserDialog(self)
        if dialog.exec_() == AddUserDialog.Accepted:
            user_data = dialog.get_user_data()
            self.create_user(user_data)

    def create_user(self, user_data):
        """Create new user - CRUD CREATE OPERATION"""
        try:
            # Validate the data first
            validation_result = self.csv_handler.validate_csv_data('users', user_data)

            if not validation_result['valid']:
                error_msg = '\n'.join(validation_result['errors'])
                QMessageBox.critical(self, "Validation Error", f"Cannot create user:\n{error_msg}")
                return

            # Use validated data
            user_data = validation_result['data']

            # Try API first
            if self.api_client.is_authenticated():
                response = self.users_api.create_user(user_data)
                if 'error' not in response:
                    QMessageBox.information(self, "Success", f"User '{user_data['username']}' created successfully!")
                    self.refresh_data()
                    self.user_updated.emit()
                    return
                else:
                    self.logger.warning(f"API failed: {response['error']}, falling back to CSV")

            # Fallback to CSV
            if 'id' not in user_data or not user_data['id']:
                user_data['id'] = self.csv_handler.get_next_id('users')

            # Ensure timestamps and proper boolean conversion
            current_time = datetime.now().isoformat()
            user_data['created_at'] = current_time

            # Convert boolean to string for CSV
            user_data['is_active'] = 'true' if user_data.get('is_active', True) else 'false'

            if self.csv_handler.append_to_csv('users', user_data):
                QMessageBox.information(self, "Success", f"User '{user_data['username']}' created and saved!")
                self.refresh_data()
                self.user_updated.emit()
                self.logger.info(f"Successfully created user: {user_data['username']}")
            else:
                raise Exception("Failed to save to CSV")

        except Exception as e:
            self.logger.error(f"Error creating user: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create user: {e}")

    def on_user_selected(self, row):
        """Handle user selection"""
        if row < len(self.filtered_users):
            # Find the actual index in current_users
            selected_user = self.filtered_users[row]
            self.selected_user = selected_user
            self.selected_user_index = self.current_users.index(selected_user)

            self.show_user_details(selected_user)
            #self.show_user_profile(selected_user)
            self.enable_user_actions(True)

    def on_user_double_clicked(self, row):
        """Handle user double click"""
        self.edit_selected_user()

    def show_context_menu(self, position):
        """Show context menu for user table"""
        if self.selected_user:
            menu = QMenu(self)

            edit_action = QAction("✏️ Edit User", self)
            edit_action.triggered.connect(self.edit_selected_user)
            menu.addAction(edit_action)

            toggle_action = QAction("🔄 Toggle Status", self)
            toggle_action.triggered.connect(self.toggle_user_status)
            menu.addAction(toggle_action)

            menu.addSeparator()

            reset_action = QAction("🔑 Reset Password", self)
            reset_action.triggered.connect(self.reset_user_password)
            menu.addAction(reset_action)

            menu.addSeparator()

            delete_action = QAction("🗑️ Delete User", self)
            delete_action.triggered.connect(self.delete_selected_user)
            menu.addAction(delete_action)

            menu.exec_(self.users_table.table.mapToGlobal(position))

    def show_user_details(self, user):
       """Show user details in quick actions panel"""
       username = user.get('username', 'Unknown')
       self.user_name_label.setText(username)

       # Role
       role = user.get('role', 'Staff')
       employee_id = user.get('employee_id', '')
       if employee_id:
           role_text = f"{role} ({employee_id})"
       else:
           role_text = role
       self.user_role_label.setText(role_text)

       # Status
       is_active = self.is_user_active(user)
       if is_active:
           self.user_status_label.setText("✅ Active")
           self.user_status_label.setStyleSheet("color: #10B981; font-size: 12px; margin: 5px;")
       else:
           self.user_status_label.setText("❌ Inactive")
           self.user_status_label.setStyleSheet("color: #EF4444; font-size: 12px; margin: 5px;")

       # Update user avatar - fill and clip to circle
       profile_picture = user.get('profile_picture', '')
       self.set_avatar_pixmap(self.user_avatar_label, profile_picture, 200)

    def show_user_profile(self, user):
       """Show user profile in profile tab"""
       username = user.get('username', 'Unknown')
       #self.profile_name.setText(username)
       self.profile_username.setText(user.get('username', 'N/A'))
       self.profile_email.setText(user.get('email', 'N/A'))
       self.profile_employee_id.setText(user.get('employee_id', 'N/A'))

       # Status
       is_active = self.is_user_active(user)
       status_text = "✅ Active" if is_active else "❌ Inactive"
       color = "#10B981" if is_active else "#EF4444"
       self.profile_status.setText(status_text)
       self.profile_status.setStyleSheet(f"color: {color};")

       # Last login
       last_login = user.get('last_login', 'Never')
       if last_login and last_login != 'Never':
           last_login = last_login[:19].replace('T', ' ')
       self.profile_last_login.setText(last_login)

       # Created date
       created_at = user.get('created_at') or user.get('date_joined', '')
       if created_at:
           created_at = created_at[:19].replace('T', ' ')
       else:
           created_at = 'Unknown'
       self.profile_created.setText(created_at)

       # Update profile avatar - fill and clip to circle
       profile_picture = user.get('profile_picture', '')
       self.set_avatar_pixmap(self.profile_avatar, profile_picture, 96)

       # Mock activity data
       self.activity_list.setText("• Account created\n• Email verified\n• Profile updated")

    def enable_user_actions(self, enabled):
        """Enable/disable user action buttons"""
        self.edit_user_btn.setEnabled(enabled)
        self.toggle_status_btn.setEnabled(enabled)
        self.reset_password_btn.setEnabled(enabled)
        self.delete_user_btn.setEnabled(enabled)

    def edit_selected_user(self):
        """Edit selected user - CRUD UPDATE OPERATION"""
        if not self.selected_user:
            QMessageBox.warning(self, "No Selection", "Please select a user to edit")
            return

        dialog = AddUserDialog(self, self.selected_user)
        if dialog.exec_() == AddUserDialog.Accepted:
            updated_data = dialog.get_user_data()
            self.update_user(self.selected_user.get('id'), updated_data)

    def update_user(self, user_id, updated_data):
        """Update user - CRUD UPDATE OPERATION"""
        try:
            # Convert boolean to string for CSV
            if 'is_active' in updated_data:
                updated_data['is_active'] = 'true' if updated_data['is_active'] else 'false'

            # Try API first
            if self.api_client.is_authenticated():
                response = self.users_api.update_user(user_id, updated_data)
                if 'error' not in response:
                    QMessageBox.information(self, "Success", "User updated successfully!")
                    self.refresh_data()
                    self.user_updated.emit()
                    return
                else:
                    self.logger.warning(f"API failed: {response['error']}, falling back to CSV")

            # Fallback to CSV
            if self.csv_handler.update_csv_row('users', user_id, updated_data):
                QMessageBox.information(self, "Success", "User updated in local storage!")

                # Update the selected user data
                if self.selected_user_index is not None:
                    self.current_users[self.selected_user_index].update(updated_data)
                    self.selected_user.update(updated_data)

                self.apply_current_filters()
                self.show_user_details(self.selected_user)
                self.show_user_profile(self.selected_user)
                self.user_updated.emit()
                self.logger.info(f"Successfully updated user: {user_id}")
            else:
                raise Exception("Failed to update CSV")

        except Exception as e:
            self.logger.error(f"Error updating user: {e}")
            QMessageBox.critical(self, "Error", f"Failed to update user: {e}")

    def toggle_user_status(self):
        """Toggle user active status - CRUD UPDATE OPERATION"""
        if not self.selected_user:
            return

        username = self.selected_user.get('username', 'Unknown')
        current_status = self.is_user_active(self.selected_user)
        new_status = not current_status
        action = "activate" if new_status else "deactivate"

        reply = QMessageBox.question(
            self, "Confirm Status Change",
            f"Are you sure you want to {action} user '{username}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.update_user(self.selected_user.get('id'), {'is_active': new_status})

    def reset_user_password(self):
        """Reset user password"""
        if not self.selected_user:
            return

        username = self.selected_user.get('username', 'Unknown')

        from PyQt5.QtWidgets import QInputDialog

        new_password, ok = QInputDialog.getText(
            self, 'Reset Password',
            f'Enter new password for {username}:',
            text='temp123'
        )

        if ok and new_password.strip():
            # In a real system, you'd hash the password and update it
            QMessageBox.information(
                self, "Password Reset",
                f"Password for '{username}' has been reset.\nNew password: {new_password}\n\nUser should change this on next login."
            )

    def delete_selected_user(self):
        """Delete selected user - CRUD DELETE OPERATION"""
        if not self.selected_user:
            return

        username = self.selected_user.get('username', 'Unknown')

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete user '{username}'?\n\nThis action cannot be undone.\nAll user data and history will be permanently removed.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.delete_user(self.selected_user.get('id'))

    def delete_user(self, user_id):
        """Delete user - CRUD DELETE OPERATION"""
        try:
            # Try API first
            if self.api_client.is_authenticated():
                response = self.users_api.delete_user(user_id)
                if 'error' not in response:
                    QMessageBox.information(self, "Success", "User deleted successfully!")
                    self.refresh_data()
                    self.clear_user_selection()
                    self.user_updated.emit()
                    return
                else:
                    self.logger.warning(f"API failed: {response['error']}, falling back to CSV")

            # Fallback to CSV
            if self.csv_handler.delete_csv_row('users', user_id):
                QMessageBox.information(self, "Success", "User deleted from local storage!")
                self.refresh_data()
                self.clear_user_selection()
                self.user_updated.emit()
                self.logger.info(f"Successfully deleted user: {user_id}")
            else:
                raise Exception("Failed to delete from CSV")

        except Exception as e:
            self.logger.error(f"Error deleting user: {e}")
            QMessageBox.critical(self, "Error", f"Failed to delete user: {e}")

    def clear_user_selection(self):
       """Clear user selection"""
       self.selected_user = None
       self.selected_user_index = None

       # Clear quick actions panel
       self.user_name_label.setText("No user selected")
       self.user_role_label.setText("")
       self.user_status_label.setText("")
       
       # Clear user avatar
       self.user_avatar_label.setText("👤")
       self.user_avatar_label.setPixmap(None)

       # Clear profile tab
       self.profile_name.setText("Select a user")
       self.profile_username.setText("-")
       self.profile_email.setText("-")
       self.profile_employee_id.setText("-")
       self.profile_status.setText("-")
       self.profile_last_login.setText("-")
       self.profile_created.setText("-")
       self.activity_list.setText("No recent activity")
       
       # Clear profile avatar
       self.profile_avatar.setText("👤")
       self.profile_avatar.setPixmap(None)

       self.enable_user_actions(False)

    def show_bulk_actions(self):
        """Show bulk actions dialog"""
        QMessageBox.information(
            self, "Bulk Actions",
            "Bulk actions feature coming soon!\n\nWill include:\n• Bulk status changes\n• Bulk password resets\n• Bulk role assignments\n• Bulk exports"
        )

    def sync_with_api(self):
        """Sync users with API"""
        if not self.api_client.is_authenticated():
            QMessageBox.warning(self, "Not Connected", "Please connect to API first")
            return

        try:
            success = self.sync_manager.sync_data_type('users')
            if success:
                QMessageBox.information(self, "Success", "Users synced successfully!")
                self.refresh_data()
            else:
                QMessageBox.warning(self, "Sync Failed", "Failed to sync users")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Sync error: {e}")

    def export_users(self):
        """Export users to CSV"""
        from PyQt5.QtWidgets import QFileDialog
        import shutil

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Users", "users_export.csv", "CSV Files (*.csv)"
        )

        if file_path:
            try:
                users_csv_path = self.csv_handler.CSV_FILES['users']
                shutil.copy2(users_csv_path, file_path)
                QMessageBox.information(self, "Success", f"Users exported to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Export failed: {e}")

    def import_users(self):
        """Import users from CSV"""
        from PyQt5.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Users", "", "CSV Files (*.csv);;All Files (*)"
        )

        if file_path:
            try:
                import pandas as pd

                # Read the CSV file
                df = pd.read_csv(file_path)

                # Validate required columns
                required_columns = ['username', 'email']
                missing_columns = [col for col in required_columns if col not in df.columns]

                if missing_columns:
                    QMessageBox.critical(
                        self, "Import Error",
                        f"Missing required columns: {', '.join(missing_columns)}"
                    )
                    return

                # Process and import users
                imported_count = 0
                for _, row in df.iterrows():
                    user_data = {
                        'username': row['username'],
                        'email': row['email'],
                        'employee_id': row.get('employee_id', ''),
                        'is_active': True,
                        'created_at': datetime.now().isoformat()
                    }

                    # Add to CSV
                    user_data['id'] = self.csv_handler.get_next_id('users')
                    user_data['is_active'] = 'true'

                    if self.csv_handler.append_to_csv('users', user_data):
                        imported_count += 1

                QMessageBox.information(
                    self, "Import Complete",
                    f"Successfully imported {imported_count} users!"
                )
                self.refresh_data()

            except Exception as e:
                self.logger.error(f"Import error: {e}")
                QMessageBox.critical(self, "Import Error", f"Failed to import users: {e}")

    def refresh_data_external(self):
        """External refresh method for other components"""
        self.refresh_data()
