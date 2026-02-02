#!/usr/bin/env python
"""
Robot External Control - PyQt5 GUI Application
===============================================
This is the UI application that runs on the EXTERNAL DEVICE.
It writes commands to commands.csv which the server reads and sends to robot.

Usage:
    1. Install: pip install PyQt5
    2. Run: python ui.py
"""

import sys
import os
import csv
import json
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLabel, QFrame, QTabWidget,
    QFileDialog, QTextEdit, QGroupBox, QMessageBox, QSpinBox,
    QDoubleSpinBox, QLineEdit, QStatusBar
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPalette, QColor


# =============================================================================
# Configuration
# =============================================================================
COMMANDS_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "commands.csv")


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
        
        print(f"[UI] Command written: {command} - {params}")
        return True
    
    def clear_command(self):
        """Clear the command (write empty)"""
        with open(self.csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['command', 'params', 'timestamp'])


# =============================================================================
# Main Window
# =============================================================================

class RobotControlUI(QMainWindow):
    """Main robot control window"""
    
    def __init__(self):
        super().__init__()
        self.cmd_writer = CommandWriter(COMMANDS_CSV)
        self.current_mode = "MANUAL"
        self.program_content = ""
        self.program_filename = ""
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the main UI"""
        self.setWindowTitle("🤖 Robot External Control Panel")
        self.setMinimumSize(800, 700)
        self.setStyleSheet(self.get_stylesheet())
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        self.setup_header(main_layout)
        
        # Mode selection
        self.setup_mode_selector(main_layout)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        self.setup_manual_tab()
        self.setup_program_tab()
        self.setup_advanced_tab()
        main_layout.addWidget(self.tab_widget)
        
        # Emergency stop
        self.setup_emergency_stop(main_layout)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(f"Ready - Commands saved to: {COMMANDS_CSV}")
        
    def get_stylesheet(self):
        """Return dark theme stylesheet"""
        return """
            QMainWindow { background-color: #1a1a2e; }
            QWidget { background-color: #1a1a2e; color: #ffffff; font-family: 'Segoe UI', Arial; }
            QPushButton {
                background-color: #16213e; border: 2px solid #0f3460; border-radius: 8px;
                padding: 12px 20px; font-size: 14px; font-weight: bold; color: white; min-height: 40px;
            }
            QPushButton:hover { background-color: #0f3460; border-color: #00d4ff; }
            QPushButton:pressed { background-color: #0a2647; }
            QPushButton:disabled { background-color: #2d2d44; color: #666666; }
            QGroupBox {
                border: 2px solid #0f3460; border-radius: 10px; margin-top: 15px;
                padding-top: 15px; font-size: 14px; font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin; subcontrol-position: top left;
                padding: 5px 10px; background-color: #16213e; border-radius: 5px; color: #00d4ff;
            }
            QTabWidget::pane { border: 2px solid #0f3460; border-radius: 10px; background-color: #16213e; }
            QTabBar::tab {
                background-color: #16213e; border: 2px solid #0f3460; border-bottom: none;
                border-radius: 8px 8px 0 0; padding: 10px 25px; margin-right: 5px; font-weight: bold;
            }
            QTabBar::tab:selected { background-color: #0f3460; border-color: #00d4ff; }
            QTextEdit {
                background-color: #0a0a14; border: 2px solid #0f3460; border-radius: 8px;
                padding: 10px; font-family: 'Consolas', monospace;
            }
            QSpinBox, QDoubleSpinBox, QLineEdit {
                background-color: #0a0a14; border: 2px solid #0f3460; border-radius: 5px;
                padding: 8px; font-size: 14px;
            }
            QLabel { font-size: 14px; }
            QStatusBar { background-color: #0f3460; color: white; font-weight: bold; }
        """
    
    def setup_header(self, layout):
        """Setup header"""
        header = QFrame()
        header.setStyleSheet("background-color: #16213e; border-radius: 10px; padding: 10px;")
        header_layout = QHBoxLayout(header)
        
        title = QLabel("🤖 Robot External Control Panel")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00d4ff;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # CSV indicator
        csv_label = QLabel("📄 Using: commands.csv")
        csv_label.setStyleSheet("color: #27ae60;")
        header_layout.addWidget(csv_label)
        
        layout.addWidget(header)
    
    def setup_mode_selector(self, layout):
        """Setup mode selection buttons"""
        mode_group = QGroupBox("Robot Mode")
        mode_layout = QHBoxLayout(mode_group)
        
        self.manual_btn = QPushButton("🎮 MANUAL")
        self.manual_btn.setStyleSheet("background-color: #27ae60;")
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
        #self.btn_forward.released.connect(lambda: self.send_command("JOG_STOP"))
        dpad_layout.addWidget(self.btn_forward, 0, 1)
        
        # Left
        self.btn_left = QPushButton("◄\nLeft")
        self.btn_left.setMinimumSize(100, 80)
        self.btn_left.setStyleSheet("background-color: #9b59b6;")
        self.btn_left.pressed.connect(lambda: self.send_command("JOG_LEFT"))
        #self.btn_left.released.connect(lambda: self.send_command("JOG_STOP"))
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
        #self.btn_right.released.connect(lambda: self.send_command("JOG_STOP"))
        dpad_layout.addWidget(self.btn_right, 1, 2)
        
        # Backward
        self.btn_backward = QPushButton("▼\nBackward")
        self.btn_backward.setMinimumSize(100, 80)
        self.btn_backward.setStyleSheet("background-color: #3498db;")
        self.btn_backward.pressed.connect(lambda: self.send_command("JOG_BACKWARD"))
        #self.btn_backward.released.connect(lambda: self.send_command("JOG_STOP"))
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
        layout.addStretch()
        
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
        self.status_bar.showMessage(f"Command: {command}")
    
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
        self.manual_btn.setStyleSheet("background-color: #16213e;")
        self.program_btn.setStyleSheet("background-color: #16213e;")
        self.auto_btn.setStyleSheet("background-color: #16213e;")
        
        if self.current_mode == "MANUAL":
            self.manual_btn.setStyleSheet("background-color: #27ae60;")
        elif self.current_mode == "PROGRAM":
            self.program_btn.setStyleSheet("background-color: #3498db;")
        elif self.current_mode == "AUTO":
            self.auto_btn.setStyleSheet("background-color: #8e44ad;")
    
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


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Dark palette
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(26, 26, 46))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(10, 10, 20))
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(22, 33, 62))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.Highlight, QColor(0, 212, 255))
    app.setPalette(palette)
    
    window = RobotControlUI()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
