from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QLineEdit, QComboBox, QPushButton, QLabel, QFrame,
                             QMessageBox, QCheckBox, QGroupBox)
from PyQt5.QtCore import Qt
from ui.common.base_dialog import BaseDialog
from PyQt5.QtGui import QFont
from datetime import datetime
import re
from PyQt5.QtWidgets import QFileDialog
from ui.common.input_validators import apply_no_special_chars_validator


class AddUserDialog(BaseDialog):
    def __init__(self, parent=None, user_data=None):
        super().__init__(parent)
        self.user_data = user_data
        self.is_edit_mode = user_data is not None

        self.setup_ui()
        self.setup_validation()

        if self.is_edit_mode:
            self.populate_fields()

    def setup_ui(self):
        """Setup dialog UI"""
        self.setWindowTitle("Edit User" if self.is_edit_mode else "Add New User")
        self.setModal(True)
        self.setFixedSize(600, 850)  # Made bigger: was 450x650, now 550x750

        # Apply dark theme
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QLineEdit, QComboBox {
                background-color: #404040;
                border: 1px solid #555555;
                padding: 8px;
                border-radius: 4px;
                color: #ffffff;
                min-height: 20px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 2px solid #ff6b35;
            }
            QCheckBox {
                color: #ffffff;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #404040;
                border: 1px solid #555555;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #ff6b35;
                border: 1px solid #ff6b35;
                border-radius: 3px;
            }
            QGroupBox {
                color: #ffffff;
                border: 1px solid #555555;
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
            QPushButton {
                background-color: #555555;
                border: 1px solid #666666;
                padding: 10px 20px;
                border-radius: 4px;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #666666;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("Edit User Details" if self.is_edit_mode else "Add New User")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #ff6b35; margin-bottom: 10px;")
        layout.addWidget(title)

        # Form sections
        self.create_basic_info_section(layout)
        self.create_contact_section(layout)
        self.create_employee_section(layout)
        self.create_account_section(layout)

        # Validation info
        validation_label = QLabel("* Required fields")
        validation_label.setStyleSheet("color: #cccccc; font-size: 12px;")
        layout.addWidget(validation_label)

        # Buttons
        self.create_buttons(layout)

    def create_basic_info_section(self, parent_layout):
        """Create basic information section"""
        section = QGroupBox("Basic Information")
        form_layout = QFormLayout(section)
        form_layout.setSpacing(12)

        # Username
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter username")
        apply_no_special_chars_validator(self.username_input)
        form_layout.addRow("Username *:", self.username_input)

        # Profile Picture
        self.profile_picture_layout = QHBoxLayout()
        self.profile_picture_input = QLineEdit()
        self.profile_picture_input.setPlaceholderText("No file selected")
        self.profile_picture_input.setReadOnly(True)
        self.profile_picture_button = QPushButton("Browse...")
        self.profile_picture_button.setAutoDefault(False)
        self.profile_picture_button.clicked.connect(self.select_profile_picture)
        self.profile_picture_layout.addWidget(self.profile_picture_input)
        self.profile_picture_layout.addWidget(self.profile_picture_button)
        form_layout.addRow("Profile Picture:", self.profile_picture_layout)

        parent_layout.addWidget(section)

    def create_contact_section(self, parent_layout):
        """Create contact information section"""
        section = QGroupBox("Contact Information")
        form_layout = QFormLayout(section)
        form_layout.setSpacing(12)

        # Email
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("user@company.com")
        form_layout.addRow("Email *:", self.email_input)

        parent_layout.addWidget(section)

    def create_employee_section(self, parent_layout):
        """Create employee information section"""
        section = QGroupBox("Employee Information")
        form_layout = QFormLayout(section)
        form_layout.setSpacing(12)

        # Employee ID
        self.employee_id_input = QLineEdit()
        self.employee_id_input.setPlaceholderText("e.g., EMP001, 12345")
        apply_no_special_chars_validator(self.employee_id_input)
        form_layout.addRow("Employee ID:", self.employee_id_input)

        # Role/Department
        self.role_input = QLineEdit()
        self.role_input.setPlaceholderText("e.g., Warehouse Staff, Supervisor")
        apply_no_special_chars_validator(self.role_input)
        form_layout.addRow("Role:", self.role_input)

        parent_layout.addWidget(section)

    def create_account_section(self, parent_layout):
        """Create account settings section"""
        section = QGroupBox("Account Settings")
        section_layout = QVBoxLayout(section)

        # Password (only for new users)
        if not self.is_edit_mode:
            form_layout = QFormLayout()

            self.password_input = QLineEdit()
            self.password_input.setPlaceholderText("Enter password")
            self.password_input.setEchoMode(QLineEdit.Password)
            form_layout.addRow("Password *:", self.password_input)

            self.confirm_password_input = QLineEdit()
            self.confirm_password_input.setPlaceholderText("Confirm password")
            self.confirm_password_input.setEchoMode(QLineEdit.Password)
            form_layout.addRow("Confirm Password *:", self.confirm_password_input)

            section_layout.addLayout(form_layout)

        # Active status
        self.is_active_checkbox = QCheckBox("Active User")
        self.is_active_checkbox.setChecked(True)
        section_layout.addWidget(self.is_active_checkbox)

        parent_layout.addWidget(section)

    def create_buttons(self, parent_layout):
        """Create dialog buttons"""
        button_layout = QHBoxLayout()

        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setAutoDefault(False)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        # Save button
        save_btn = QPushButton("Update User" if self.is_edit_mode else "Create User")
        save_btn.setAutoDefault(False)
        save_btn.clicked.connect(self.save_user)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff6b35;
                color: white;
            }
            QPushButton:hover {
                background-color: #e55a2b;
            }
        """)
        button_layout.addWidget(save_btn)

        parent_layout.addLayout(button_layout)

    def setup_validation(self):
        """Setup input validation"""
        # Connect validation to input changes
        self.username_input.textChanged.connect(self.validate_inputs)
        self.email_input.textChanged.connect(self.validate_inputs)

        if not self.is_edit_mode:
            self.password_input.textChanged.connect(self.validate_inputs)
            self.confirm_password_input.textChanged.connect(self.validate_inputs)

    def select_profile_picture(self):
        """Open file dialog to select profile picture"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Profile Picture",
            "",
            "Image Files (*.jpg *.jpeg *.png)"
        )
        
        if file_path:
            # Validate file extension
            import os
            _, ext = os.path.splitext(file_path)
            if ext.lower() in ['.jpg', '.jpeg', '.png']:
                self.profile_picture_input.setText(file_path)
            else:
                QMessageBox.warning(self, "Invalid File", "Please select a JPG or PNG file only.")

    def validate_inputs(self):
        """Validate required inputs"""
        username = self.username_input.text().strip()
        email = self.email_input.text().strip()

        # Validate email format
        email_valid = self.is_valid_email(email) if email else False

        # Change border color based on validation
        inputs_validation = [
            (self.username_input, bool(username)),
            (self.email_input, email_valid),
        ]

        # Add password validation for new users
        if not self.is_edit_mode:
            password = self.password_input.text()
            confirm_password = self.confirm_password_input.text()
            password_valid = len(password) >= 6
            passwords_match = password == confirm_password and len(password) > 0

            inputs_validation.extend([
                (self.password_input, password_valid),
                (self.confirm_password_input, passwords_match)
            ])

        for widget, is_valid in inputs_validation:
            if is_valid:
                widget.setStyleSheet(widget.styleSheet().replace("border: 2px solid #ff0000;", ""))
            else:
                if "border: 2px solid #ff0000;" not in widget.styleSheet():
                    current_style = widget.styleSheet()
                    widget.setStyleSheet(current_style + "border: 2px solid #ff0000;")

    def is_valid_email(self, email):
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    def populate_fields(self):
        """Populate fields with existing user data"""
        if not self.user_data:
            return

        self.username_input.setText(self.user_data.get('username', ''))
        self.email_input.setText(self.user_data.get('email', ''))

        # Employee ID from profile or direct field
        employee_id = self.user_data.get('employee_id', '')
        self.employee_id_input.setText(employee_id)

        # Role
        role = self.user_data.get('role', '')
        self.role_input.setText(role)

        # Profile picture
        profile_picture = self.user_data.get('profile_picture', '')
        self.profile_picture_input.setText(profile_picture)

        # Active status
        is_active = self.user_data.get('is_active', True)
        if isinstance(is_active, str):
            is_active = is_active.lower() == 'true'
        self.is_active_checkbox.setChecked(bool(is_active))

    def save_user(self):
        """Save user data"""
        # Validate required fields
        username = self.username_input.text().strip()
        email = self.email_input.text().strip()

        if not username:
            QMessageBox.warning(self, "Validation Error", "Username is required")
            self.username_input.setFocus()
            return

        if not email:
            QMessageBox.warning(self, "Validation Error", "Email is required")
            self.email_input.setFocus()
            return

        if not self.is_valid_email(email):
            QMessageBox.warning(self, "Validation Error", "Please enter a valid email address")
            self.email_input.setFocus()
            return

        # Validate passwords for new users
        if not self.is_edit_mode:
            password = self.password_input.text()
            confirm_password = self.confirm_password_input.text()

            if not password:
                QMessageBox.warning(self, "Validation Error", "Password is required")
                self.password_input.setFocus()
                return

            if len(password) < 6:
                QMessageBox.warning(self, "Validation Error", "Password must be at least 6 characters long")
                self.password_input.setFocus()
                return

            if password != confirm_password:
                QMessageBox.warning(self, "Validation Error", "Passwords do not match")
                self.confirm_password_input.setFocus()
                return

        self.accept()

    def get_user_data(self):
        """Get user data from form"""
        current_time = datetime.now().isoformat()

        data = {
            'username': self.username_input.text().strip(),
            'email': self.email_input.text().strip(),
            'employee_id': self.employee_id_input.text().strip(),
            'role': self.role_input.text().strip(),
            'profile_picture': self.profile_picture_input.text().strip(),
            'is_active': self.is_active_checkbox.isChecked()
        }

        # Add password for new users
        if not self.is_edit_mode:
            data['password'] = self.password_input.text()
            data['created_at'] = current_time

        return data