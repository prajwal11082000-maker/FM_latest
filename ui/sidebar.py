from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel,
                             QFrame, QHBoxLayout, QButtonGroup)
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QIcon

from config.settings import SIDEBAR_WIDTH, EXPANDED_SIDEBAR_WIDTH


class SidebarButton(QPushButton):
    def __init__(self, text, icon_text="", page_name=""):
        super().__init__()
        self.page_name = page_name
        self.icon_text = icon_text
        self.button_text = text
        self.is_expanded = False

        self.setFixedHeight(50)
        self.setCheckable(True)
        self.setup_style()
        self.update_content()

    def setup_style(self):
        """Setup button styling"""
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                text-align: left;
                padding: 10px;
                color: #cccccc;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #404040;
            }
            QPushButton:checked {
                background-color: #ff6b35;
                color: #ffffff;
            }
        """)

    def update_content(self):
        """Update button content based on expansion state"""
        if self.is_expanded:
            self.setText(f"{self.icon_text} {self.button_text}")
        else:
            self.setText(self.icon_text)

    def set_expanded(self, expanded):
        """Set expansion state"""
        self.is_expanded = expanded
        self.update_content()


class Sidebar(QWidget):
    # Signal emitted when page changes
    page_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.is_expanded = False
        self.setup_ui()
        self.setup_animation()

    def setup_ui(self):
        """Setup sidebar UI"""
        self.setFixedWidth(SIDEBAR_WIDTH)
        self.setStyleSheet("""
            QWidget {
                background-color: #1f1f1f;
                border-right: 1px solid #555555;
            }
        """)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header section
        self.create_header(layout)

        # Navigation buttons
        self.create_navigation(layout)

        # Footer
        layout.addStretch()
        self.create_footer(layout)

    def create_header(self, parent_layout):
        """Create header section"""
        header_frame = QFrame()
        header_frame.setFixedHeight(80)
        header_frame.setStyleSheet("border-bottom: 1px solid #555555;")

        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(10, 20, 10, 20)

        # Logo/App icon
        self.logo_label = QLabel("WMS")
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setFont(QFont("Arial", 16, QFont.Bold))
        self.logo_label.setStyleSheet("color: #ff6b35;")
        header_layout.addWidget(self.logo_label)

        parent_layout.addWidget(header_frame)

    def create_navigation(self, parent_layout):
        """Create navigation buttons"""
        nav_frame = QFrame()
        nav_layout = QVBoxLayout(nav_frame)
        nav_layout.setContentsMargins(0, 10, 0, 0)
        nav_layout.setSpacing(2)
        # Button group for exclusive selection
        self.button_group = QButtonGroup()

        # Navigation buttons
        buttons_config = [
            ("📊", "Dashboard", "dashboard"),
            ("🤖", "Devices", "devices"),
            ("🗄️", "Rack Management", "rack_management"),
            ("📦", "Add Product", "add_product"),
            ("➕", "Create Task", "create_task"),
            ("📋", "Monitor Tasks", "monitor_tasks"),
            ("👥", "Users", "users"),
            ("🗺️", "Maps", "maps"),
            ("📍", "Device Tracking", "device_tracking"),
            ("🎮", "Robot Control", "robot_control"),
        ]


        self.nav_buttons = []
        for icon, text, page_name in buttons_config:
            button = SidebarButton(text, icon, page_name)
            button.clicked.connect(lambda checked, name=page_name: self.on_button_clicked(name))
            self.button_group.addButton(button)
            nav_layout.addWidget(button)
            self.nav_buttons.append(button)

        # Set dashboard as default selected
        if self.nav_buttons:
            self.nav_buttons[0].setChecked(True)

        parent_layout.addWidget(nav_frame)

    def create_footer(self, parent_layout):
        """Create footer section"""
        footer_frame = QFrame()
        footer_frame.setFixedHeight(60)
        footer_frame.setStyleSheet("border-top: 1px solid #555555;")

        footer_layout = QVBoxLayout(footer_frame)
        footer_layout.setContentsMargins(10, 10, 10, 10)

        # Expand/collapse button
        self.toggle_button = QPushButton("☰")
        self.toggle_button.setFixedHeight(40)
        self.toggle_button.clicked.connect(self.toggle_expansion)
        self.toggle_button.setStyleSheet("""
            QPushButton {
                background-color: #404040;
                border: 1px solid #555555;
                border-radius: 4px;
                color: #ffffff;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        footer_layout.addWidget(self.toggle_button)

        parent_layout.addWidget(footer_frame)

    def setup_animation(self):
        """Setup width animation"""
        self.animation = QPropertyAnimation(self, b"minimumWidth")
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)

    def toggle_expansion(self):
        """Toggle sidebar expansion"""
        if self.is_expanded:
            self.collapse()
        else:
            self.expand()

    def expand(self):
        """Expand sidebar"""
        self.is_expanded = True

        # Update button content
        for button in self.nav_buttons:
            button.set_expanded(True)

        # Update logo
        self.logo_label.setText("Warehouse\nManagement")

        # Animate width
        self.animation.setStartValue(SIDEBAR_WIDTH)
        self.animation.setEndValue(EXPANDED_SIDEBAR_WIDTH)
        self.animation.finished.connect(lambda: self.setFixedWidth(EXPANDED_SIDEBAR_WIDTH))
        self.animation.start()

        # Update toggle button
        self.toggle_button.setText("◀")

    def collapse(self):
        """Collapse sidebar"""
        self.is_expanded = False

        # Update button content
        for button in self.nav_buttons:
            button.set_expanded(False)

        # Update logo
        self.logo_label.setText("WMS")

        # Animate width
        self.animation.setStartValue(EXPANDED_SIDEBAR_WIDTH)
        self.animation.setEndValue(SIDEBAR_WIDTH)
        self.animation.finished.connect(lambda: self.setFixedWidth(SIDEBAR_WIDTH))
        self.animation.start()

        # Update toggle button
        self.toggle_button.setText("☰")

    def on_button_clicked(self, page_name):
        """Handle navigation button clicks"""
        self.page_changed.emit(page_name)