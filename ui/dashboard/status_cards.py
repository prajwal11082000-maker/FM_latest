from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont


class StatusCardWidget(QWidget):
    def __init__(self, title, value, color, icon=""):
        super().__init__()
        self.title = title
        self.current_value = value
        self.color = color
        self.icon = icon

        self.setup_ui()
        self.setup_animation()

    def setup_ui(self):
        """Setup status card UI matching the reference design exactly"""
        self.setMinimumSize(140, 120)
        self.setMaximumHeight(130)

        # Main layout for this widget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main frame - dark background with ONLY colored left border
        self.frame = QFrame()
        self.frame.setObjectName("statusCard")
        self.frame.setStyleSheet(f"""
            QFrame#statusCard {{
                background-color: #2a2a2a;
                border: none;
                border-left: 4px solid {self.color};
                border-radius: 6px;
            }}
        """)
        layout.addWidget(self.frame)

        # Card content layout
        card_layout = QVBoxLayout(self.frame)
        card_layout.setContentsMargins(15, 12, 15, 12)
        card_layout.setSpacing(8)

        # Top row - icon box and value
        top_layout = QHBoxLayout()
        top_layout.setSpacing(10)

        # Icon in colored rounded box
        if self.icon:
            self.icon_container = QFrame()
            self.icon_container.setObjectName("iconBox")
            self.icon_container.setFixedSize(38, 38)
            self.icon_container.setStyleSheet(f"""
                QFrame#iconBox {{
                    background-color: {self.color};
                    border: none;
                    border-radius: 6px;
                }}
            """)
            icon_inner_layout = QVBoxLayout(self.icon_container)
            icon_inner_layout.setContentsMargins(0, 0, 0, 0)
            
            icon_label = QLabel(self.icon)
            icon_label.setFont(QFont("Segoe UI Emoji", 16))
            icon_label.setAlignment(Qt.AlignCenter)
            icon_label.setStyleSheet("color: #ffffff; background: transparent; border: none;")
            icon_inner_layout.addWidget(icon_label)
            
            top_layout.addWidget(self.icon_container)

        top_layout.addStretch()

        # Large value number on the right - in a bracket style container
        value_container = QFrame()
        value_container.setObjectName("valueContainer")
        value_container.setStyleSheet(f"""
            QFrame#valueContainer {{
                background-color: transparent;
                border: 2px solid {self.color};
                border-radius: 6px;
                padding: 2px 8px;
            }}
        """)
        value_layout = QHBoxLayout(value_container)
        value_layout.setContentsMargins(8, 4, 8, 4)
        
        self.value_label = QLabel(self.current_value)
        self.value_label.setFont(QFont("Arial", 28, QFont.Bold))
        self.value_label.setStyleSheet(f"""
            color: {self.color}; 
            background: transparent; 
            border: none;
        """)
        self.value_label.setAlignment(Qt.AlignCenter)
        value_layout.addWidget(self.value_label)
        
        top_layout.addWidget(value_container)

        card_layout.addLayout(top_layout)

        # Title label at bottom - centered with colored underline
        self.title_label = QLabel(self.title)
        self.title_label.setFont(QFont("Arial", 10))
        self.title_label.setStyleSheet(f"""
            color: {self.color}; 
            background: transparent;
            border: none;
            border-bottom: 2px solid {self.color};
            padding-bottom: 2px;
        """)
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.title_label)

    def setup_animation(self):
        """Setup value change animation"""
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)

    def update_value(self, new_value):
        """Update the card value with animation"""
        if new_value != self.current_value:
            old_value = self.current_value
            self.current_value = new_value

            # Animate opacity change
            self.animation.setStartValue(1.0)
            self.animation.setEndValue(0.7)
            self.animation.finished.connect(lambda: self._update_text(old_value))
            self.animation.start()

    def _update_text(self, old_value):
        """Update text after fade out"""
        self.value_label.setText(self.current_value)

        # Fade back in
        self.animation.finished.disconnect()
        self.animation.setStartValue(0.7)
        self.animation.setEndValue(1.0)
        self.animation.start()

    def set_color(self, color):
        """Change card accent color"""
        self.color = color
        self.value_label.setStyleSheet(f"""
            color: {color}; 
            background: transparent; 
            border: none;
        """)

        # Update frame border
        if hasattr(self, 'frame'):
            self.frame.setStyleSheet(f"""
                QFrame#statusCard {{
                    background-color: #2a2a2a;
                    border: none;
                    border-left: 4px solid {color};
                    border-radius: 6px;
                }}
            """)