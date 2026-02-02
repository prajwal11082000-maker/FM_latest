#!/usr/bin/env python
"""
Robot Control Widget - PyQt5 Widget for Robot External Control
===============================================================
This widget provides a UI for controlling robots via CSV commands.
It writes commands to commands.csv which can be read by a server.
"""

import os
import csv
import json
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLabel, QFrame, QTabWidget,
    QFileDialog, QTextEdit, QGroupBox, QMessageBox, QSpinBox,
    QDoubleSpinBox, QScrollArea, QComboBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


# =============================================================================
# Configuration
# =============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(BASE_DIR, "..", "..")
COMMANDS_CSV = os.path.join(PROJECT_ROOT, "commands.csv")
DEVICE_LOGS_DIR = os.path.join(PROJECT_ROOT, "data", "device_logs")
DEVICES_CSV = os.path.join(PROJECT_ROOT, "data", "devices.csv")


# =============================================================================
# CSV Command Writer
# =============================================================================

class CommandWriter:
    """Writes commands to commands.csv file"""
    
    def __init__(self, csv_path):
        self.csv_path = csv_path
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Ensure CSV file exists with header"""
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['command', 'params', 'timestamp'])
    
    def write_command(self, command, params=None):
        """Write a command to CSV file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        params_str = json.dumps(params) if params else "{}"
        
        with open(self.csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['command', 'params', 'timestamp'])
            writer.writerow([command, params_str, timestamp])
        
        print(f"[Robot Control] Command written: {command} - {params}")
        return True
    
    def clear_command(self):
        """Clear the command (write empty)"""
        with open(self.csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['command', 'params', 'timestamp'])


# =============================================================================
# Robot Control Widget
# =============================================================================

class RobotControlWidget(QWidget):
    """Robot control widget for main application integration"""
    
    def __init__(self, api_client=None, csv_handler=None):
        super().__init__()
        self.api_client = api_client
        self.csv_handler = csv_handler
        self.selected_device = None  # None means use global commands.csv
        self.cmd_writer = CommandWriter(COMMANDS_CSV)
        self.current_mode = "MANUAL"
        self.program_content = ""
        self.program_filename = ""
        self.status_message = ""
        self.setup_ui()
        self.load_devices()
        
    def setup_ui(self):
        """Setup the main UI"""
        self.setStyleSheet(self.get_stylesheet())
        
        # Main layout with scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Scroll area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        
        # Content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        self.setup_header(content_layout)
        
        # Mode selection
        self.setup_mode_selector(content_layout)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        self.setup_manual_tab()
        self.setup_program_tab()
        self.setup_advanced_tab()
        content_layout.addWidget(self.tab_widget)
        
        # Status label
        self.status_label = QLabel(f"Ready - Commands saved to: {os.path.basename(COMMANDS_CSV)}")
        self.status_label.setStyleSheet("color: #10B981; font-size: 12px; padding: 10px; background-color: #353535; border: 1px solid #555555; border-radius: 6px;")
        content_layout.addWidget(self.status_label)
        
        content_layout.addStretch()
        
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
    def get_stylesheet(self):
        """Return gray theme stylesheet matching other menus"""
        return """
            QWidget { background-color: transparent; color: #ffffff; font-family: 'Segoe UI', Arial; }
            QPushButton {
                background-color: #404040; border: 1px solid #555555; border-radius: 6px;
                padding: 12px 20px; font-size: 14px; font-weight: bold; color: white; min-height: 40px;
            }
            QPushButton:hover { background-color: #4a4a4a; border-color: #ff6b35; }
            QPushButton:pressed { background-color: #353535; }
            QPushButton:disabled { background-color: #2d2d2d; color: #666666; }
            QGroupBox {
                background-color: #353535;
                border: 1px solid #555555; border-radius: 6px; margin-top: 15px;
                padding: 15px; font-size: 14px; font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin; subcontrol-position: top left;
                padding: 5px 10px; background-color: #404040; border-radius: 4px; color: #ff6b35;
            }
            QTabWidget::pane { border: 1px solid #555555; border-radius: 6px; background-color: #353535; }
            QTabBar::tab {
                background-color: #404040; border: 1px solid #555555; border-bottom: none;
                border-radius: 6px 6px 0 0; padding: 10px 25px; margin-right: 5px; font-weight: bold;
            }
            QTabBar::tab:selected { background-color: #353535; border-color: #ff6b35; color: #ff6b35; }
            QTabBar::tab:hover { background-color: #4a4a4a; }
            QTextEdit {
                background-color: #404040; border: 1px solid #555555; border-radius: 6px;
                padding: 10px; font-family: 'Consolas', monospace; color: #ffffff;
            }
            QSpinBox, QDoubleSpinBox, QLineEdit {
                background-color: #404040; border: 1px solid #555555; border-radius: 4px;
                padding: 8px; font-size: 14px; color: #ffffff;
            }
            QLabel { font-size: 14px; background-color: transparent; }
            QScrollArea { background-color: transparent; }
        """
    
    def setup_header(self, layout):
        """Setup header with device selector"""
        header = QFrame()
        header.setStyleSheet("background-color: #353535; border: 1px solid #555555; border-radius: 6px; padding: 10px;")
        header_layout = QHBoxLayout(header)
        
        title = QLabel("🤖 Robot External Control Panel")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #ffffff;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Device selector
        device_label = QLabel("📡 Target Device:")
        device_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        header_layout.addWidget(device_label)
        
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(150)
        self.device_combo.setStyleSheet("""
            QComboBox {
                background-color: #404040; border: 1px solid #555555; border-radius: 4px;
                padding: 6px 10px; color: #ffffff; font-size: 13px;
            }
            QComboBox:hover { border-color: #ff6b35; }
            QComboBox::drop-down { border: none; padding-right: 10px; }
            QComboBox QAbstractItemView {
                background-color: #404040; color: #ffffff; selection-background-color: #ff6b35;
            }
        """)
        self.device_combo.currentIndexChanged.connect(self.on_device_changed)
        header_layout.addWidget(self.device_combo)
        
        # CSV indicator
        self.csv_label = QLabel("📄 Using: commands.csv")
        self.csv_label.setStyleSheet("color: #10B981;")
        header_layout.addWidget(self.csv_label)
        
        layout.addWidget(header)
    
    def setup_mode_selector(self, layout):
        """Setup mode selection buttons"""
        mode_group = QGroupBox("Robot Mode")
        mode_layout = QHBoxLayout(mode_group)
        
        self.manual_btn = QPushButton("🎮 MANUAL")
        self.manual_btn.setStyleSheet("background-color: #10B981;")
        self.manual_btn.clicked.connect(lambda: self.set_mode("MANUAL"))
        mode_layout.addWidget(self.manual_btn)
        
        self.program_btn = QPushButton("📋 PROGRAM")
        self.program_btn.clicked.connect(lambda: self.set_mode("PROGRAM"))
        mode_layout.addWidget(self.program_btn)
        
        self.auto_btn = QPushButton("🔄 AUTO")
        self.auto_btn.clicked.connect(lambda: self.set_mode("AUTO"))
        mode_layout.addWidget(self.auto_btn)
        
        layout.addWidget(mode_group)
    
    def setup_manual_tab(self):
        """Setup manual control tab"""
        manual_widget = QWidget()
        layout = QVBoxLayout(manual_widget)
        layout.setSpacing(20)
        
        # D-Pad Controls
        dpad_group = QGroupBox("Movement Controls")
        dpad_layout = QGridLayout(dpad_group)
        dpad_layout.setSpacing(10)
        
        # Forward
        self.btn_forward = QPushButton("▲\nForward")
        self.btn_forward.setMinimumSize(100, 80)
        self.btn_forward.setStyleSheet("background-color: #3498db;")
        self.btn_forward.pressed.connect(lambda: self.send_command("JOG_FORWARD"))
        dpad_layout.addWidget(self.btn_forward, 0, 1)
        
        # Left
        self.btn_left = QPushButton("◄\nLeft")
        self.btn_left.setMinimumSize(100, 80)
        self.btn_left.setStyleSheet("background-color: #9b59b6;")
        self.btn_left.pressed.connect(lambda: self.send_command("JOG_LEFT"))
        self.btn_left.released.connect(lambda: self.send_command("JOG_STOP"))
        dpad_layout.addWidget(self.btn_left, 1, 0)
        
        # Stop
        self.btn_stop = QPushButton("⬛\nSTOP")
        self.btn_stop.setMinimumSize(100, 80)
        self.btn_stop.setStyleSheet("background-color: #e74c3c;")
        self.btn_stop.clicked.connect(lambda: self.send_command("JOG_STOP"))
        dpad_layout.addWidget(self.btn_stop, 1, 1)
        
        # Right
        self.btn_right = QPushButton("►\nRight")
        self.btn_right.setMinimumSize(100, 80)
        self.btn_right.setStyleSheet("background-color: #9b59b6;")
        self.btn_right.pressed.connect(lambda: self.send_command("JOG_RIGHT"))
        dpad_layout.addWidget(self.btn_right, 1, 2)
        
        # Backward
        self.btn_backward = QPushButton("▼\nBackward")
        self.btn_backward.setMinimumSize(100, 80)
        self.btn_backward.setStyleSheet("background-color: #3498db;")
        self.btn_backward.pressed.connect(lambda: self.send_command("JOG_BACKWARD"))
        dpad_layout.addWidget(self.btn_backward, 2, 1)
        
        layout.addWidget(dpad_group)
        
        # Quick Actions
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QHBoxLayout(actions_group)
        
        btn_rotate_left = QPushButton("↺ Rotate 90° Left")
        btn_rotate_left.setStyleSheet("background-color: #f39c12;")
        btn_rotate_left.clicked.connect(lambda: self.send_command("ROTATE_LEFT_90"))
        actions_layout.addWidget(btn_rotate_left)
        
        btn_rotate_right = QPushButton("↻ Rotate 90° Right")
        btn_rotate_right.setStyleSheet("background-color: #f39c12;")
        btn_rotate_right.clicked.connect(lambda: self.send_command("ROTATE_RIGHT_90"))
        actions_layout.addWidget(btn_rotate_right)
        
        btn_home = QPushButton("🏠 Home All")
        btn_home.setStyleSheet("background-color: #1abc9c;")
        btn_home.clicked.connect(lambda: self.send_command("HOME_ALL"))
        actions_layout.addWidget(btn_home)
        
        btn_clear = QPushButton("🔔 Clear Alarms")
        btn_clear.setStyleSheet("background-color: #e67e22;")
        btn_clear.clicked.connect(lambda: self.send_command("CLEAR_ALARMS"))
        actions_layout.addWidget(btn_clear)
        
        layout.addWidget(actions_group)
        
        # Emergency stop button inside manual tab
        btn_emergency = QPushButton("⚠️ EMERGENCY STOP ⚠️")
        btn_emergency.setMinimumHeight(50)
        btn_emergency.setFont(QFont("Segoe UI", 14, QFont.Bold))
        btn_emergency.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c; border: 2px solid #c0392b; border-radius: 6px;
            }
            QPushButton:hover { background-color: #c0392b; }
        """)
        btn_emergency.clicked.connect(self.emergency_stop)
        layout.addWidget(btn_emergency)
        
        self.tab_widget.addTab(manual_widget, "🎮 Manual Control")
    
    def setup_program_tab(self):
        """Setup program mode tab"""
        program_widget = QWidget()
        layout = QVBoxLayout(program_widget)
        layout.setSpacing(15)
        
        # File upload
        upload_group = QGroupBox("Program File")
        upload_layout = QVBoxLayout(upload_group)
        
        btn_layout = QHBoxLayout()
        self.btn_browse = QPushButton("📁 Browse CSV File...")
        self.btn_browse.clicked.connect(self.browse_program_file)
        btn_layout.addWidget(self.btn_browse)
        
        self.file_label = QLabel("No file selected")
        self.file_label.setStyleSheet("color: #7f8c8d;")
        btn_layout.addWidget(self.file_label)
        btn_layout.addStretch()
        upload_layout.addLayout(btn_layout)
        
        layout.addWidget(upload_group)
        
        # Program preview
        preview_group = QGroupBox("Program Preview")
        preview_layout = QVBoxLayout(preview_group)
        self.program_preview = QTextEdit()
        self.program_preview.setReadOnly(True)
        self.program_preview.setPlaceholderText("Program content will appear here...")
        self.program_preview.setMinimumHeight(200)
        preview_layout.addWidget(self.program_preview)
        layout.addWidget(preview_group)
        
        # Execution controls
        exec_group = QGroupBox("Execution")
        exec_layout = QHBoxLayout(exec_group)
        
        self.btn_execute = QPushButton("▶️ Execute Program")
        self.btn_execute.setStyleSheet("background-color: #27ae60;")
        self.btn_execute.clicked.connect(self.execute_program)
        self.btn_execute.setEnabled(False)
        exec_layout.addWidget(self.btn_execute)
        
        self.btn_stop_program = QPushButton("⏹️ Stop Program")
        self.btn_stop_program.setStyleSheet("background-color: #e74c3c;")
        self.btn_stop_program.clicked.connect(self.stop_program)
        exec_layout.addWidget(self.btn_stop_program)
        
        layout.addWidget(exec_group)
        layout.addStretch()
        
        self.tab_widget.addTab(program_widget, "📋 Program Mode")
    
    def setup_advanced_tab(self):
        """Setup advanced controls tab"""
        advanced_widget = QWidget()
        layout = QVBoxLayout(advanced_widget)
        layout.setSpacing(15)
        
        # Move distance
        move_group = QGroupBox("Move Distance")
        move_layout = QHBoxLayout(move_group)
        
        move_layout.addWidget(QLabel("Distance (mm):"))
        self.distance_input = QSpinBox()
        self.distance_input.setRange(-99999, 99999)
        self.distance_input.setValue(500)
        move_layout.addWidget(self.distance_input)
        
        move_layout.addWidget(QLabel("Velocity:"))
        self.move_velocity = QSpinBox()
        self.move_velocity.setRange(50, 1000)
        self.move_velocity.setValue(300)
        move_layout.addWidget(self.move_velocity)
        
        btn_move = QPushButton("Move")
        btn_move.setStyleSheet("background-color: #3498db;")
        btn_move.clicked.connect(self.move_distance)
        move_layout.addWidget(btn_move)
        
        layout.addWidget(move_group)
        
        # Rotate angle
        rotate_group = QGroupBox("Rotate Angle")
        rotate_layout = QHBoxLayout(rotate_group)
        
        rotate_layout.addWidget(QLabel("Angle (deg):"))
        self.angle_input = QDoubleSpinBox()
        self.angle_input.setRange(-360, 360)
        self.angle_input.setValue(90)
        rotate_layout.addWidget(self.angle_input)
        
        rotate_layout.addWidget(QLabel("Velocity:"))
        self.rotate_velocity = QSpinBox()
        self.rotate_velocity.setRange(50, 1000)
        self.rotate_velocity.setValue(300)
        rotate_layout.addWidget(self.rotate_velocity)
        
        btn_rotate = QPushButton("Rotate")
        btn_rotate.setStyleSheet("background-color: #9b59b6;")
        btn_rotate.clicked.connect(self.rotate_angle)
        rotate_layout.addWidget(btn_rotate)
        
        layout.addWidget(rotate_group)
        
        # CSV file info
        info_group = QGroupBox("Command File")
        info_layout = QVBoxLayout(info_group)
        
        info_label = QLabel(f"Commands are written to:\n{COMMANDS_CSV}")
        info_label.setStyleSheet("color: #27ae60;")
        info_layout.addWidget(info_label)
        
        layout.addWidget(info_group)
        layout.addStretch()
        
        self.tab_widget.addTab(advanced_widget, "⚙️ Advanced")
    
    def setup_emergency_stop(self, layout):
        """Setup emergency stop button"""
        btn_emergency = QPushButton("⚠️ EMERGENCY STOP ⚠️")
        btn_emergency.setMinimumHeight(60)
        btn_emergency.setFont(QFont("Segoe UI", 16, QFont.Bold))
        btn_emergency.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c; border: 3px solid #c0392b; border-radius: 10px;
            }
            QPushButton:hover { background-color: #c0392b; }
        """)
        btn_emergency.clicked.connect(self.emergency_stop)
        layout.addWidget(btn_emergency)
    
    # ==========================================================================
    # Command Actions
    # ==========================================================================
    
    def send_command(self, command, params=None):
        """Write command to CSV file"""
        self.cmd_writer.write_command(command, params)
        self.update_status(f"Command: {command}")
    
    def update_status(self, message):
        """Update status label"""
        self.status_message = message
        if hasattr(self, 'status_label'):
            self.status_label.setText(message)
    
    def set_mode(self, mode):
        """Set robot mode"""
        self.current_mode = mode
        self.send_command("SET_MODE", {"mode": mode})
        self.update_mode_buttons()
        
        if mode == "MANUAL":
            self.tab_widget.setCurrentIndex(0)
        elif mode == "PROGRAM":
            self.tab_widget.setCurrentIndex(1)
        elif mode == "AUTO":
            self.send_command("AUTO_PROGRAM")
    
    def update_mode_buttons(self):
        """Update mode button styles"""
        self.manual_btn.setStyleSheet("background-color: #404040;")
        self.program_btn.setStyleSheet("background-color: #404040;")
        self.auto_btn.setStyleSheet("background-color: #404040;")
        
        if self.current_mode == "MANUAL":
            self.manual_btn.setStyleSheet("background-color: #10B981;")
        elif self.current_mode == "PROGRAM":
            self.program_btn.setStyleSheet("background-color: #3B82F6;")
        elif self.current_mode == "AUTO":
            self.auto_btn.setStyleSheet("background-color: #8B5CF6;")
    
    def emergency_stop(self):
        """Emergency stop"""
        self.send_command("EMERGENCY_STOP")
        QMessageBox.warning(self, "Emergency Stop", "Emergency stop activated!")
    
    def browse_program_file(self):
        """Browse for program file"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select Program File", "", "CSV Files (*.csv);;All Files (*)"
        )
        if filename:
            try:
                with open(filename, 'r') as f:
                    content = f.read()
                self.program_content = content
                self.program_filename = filename
                self.file_label.setText(filename.split('/')[-1].split('\\')[-1])
                self.program_preview.setText(content)
                self.btn_execute.setEnabled(True)
                
                # Write upload command
                self.send_command("UPLOAD_PROGRAM", {
                    "filename": os.path.basename(filename),
                    "content": content
                })
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {e}")
    
    def execute_program(self):
        """Execute program"""
        self.send_command("EXECUTE_PROGRAM")
    
    def stop_program(self):
        """Stop program"""
        self.send_command("STOP_PROGRAM")
    
    def move_distance(self):
        """Move specific distance"""
        distance = self.distance_input.value()
        velocity = self.move_velocity.value()
        self.send_command("MOVE_DISTANCE", {
            "distance": distance,
            "velocity": velocity,
            "acceleration": 5000,
            "deceleration": 5000
        })
    
    def rotate_angle(self):
        """Rotate specific angle"""
        angle = self.angle_input.value()
        velocity = self.rotate_velocity.value()
        self.send_command("ROTATE_ANGLE", {
            "angle": angle,
            "velocity": velocity,
            "acceleration": 5000,
            "deceleration": 5000
        })

    def refresh_data(self):
        """Refresh data - reload device list"""
        self.load_devices()
    
    def load_devices(self):
        """Load available devices from devices.csv"""
        try:
            # Store current selection
            current_selection = self.device_combo.currentData() if hasattr(self, 'device_combo') else None
            
            self.device_combo.blockSignals(True)
            self.device_combo.clear()
            
            # Add "None" option for global commands.csv
            self.device_combo.addItem("📝 Global (commands.csv)", None)
            
            # Read devices from CSV
            if os.path.exists(DEVICES_CSV):
                with open(DEVICES_CSV, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        device_id = row.get('device_id', '')
                        device_name = row.get('device_name', device_id)
                        if device_id:
                            self.device_combo.addItem(f"🤖 {device_id} ({device_name})", device_id)
            
            # Restore previous selection if it still exists
            if current_selection:
                index = self.device_combo.findData(current_selection)
                if index >= 0:
                    self.device_combo.setCurrentIndex(index)
            
            self.device_combo.blockSignals(False)
            
        except Exception as e:
            print(f"[Robot Control] Error loading devices: {e}")
    
    def on_device_changed(self, index):
        """Handle device selection change"""
        self.selected_device = self.device_combo.currentData()
        
        if self.selected_device:
            # Use device-specific command file
            command_file = os.path.join(DEVICE_LOGS_DIR, f"{self.selected_device}_command.csv")
            self.cmd_writer = CommandWriter(command_file)
            self.csv_label.setText(f"📄 Using: {self.selected_device}_command.csv")
            self.update_status(f"Target: {self.selected_device}")
        else:
            # Use global commands.csv
            self.cmd_writer = CommandWriter(COMMANDS_CSV)
            self.csv_label.setText("📄 Using: commands.csv")
            self.update_status("Target: Global commands.csv")
