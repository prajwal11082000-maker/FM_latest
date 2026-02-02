"""
Form Components Module

Reusable UI components for task creation form.
"""
from PyQt5.QtWidgets import (QComboBox, QLineEdit, QListWidget, QLabel, 
                             QPushButton, QHBoxLayout, QGroupBox, QFormLayout)
from PyQt5.QtCore import Qt
from ui.common.input_validators import apply_no_special_chars_validator


class FormComponents:
    """Factory for creating form components"""
    
    @staticmethod
    def create_combo_box(placeholder: str = "", enabled: bool = True, 
                        min_height: int = 35) -> QComboBox:
        """Create a styled combo box"""
        combo = QComboBox()
        combo.setMinimumHeight(min_height)
        if placeholder:
            combo.addItem(placeholder, "")
        combo.setEnabled(enabled)
        return combo
    
    @staticmethod
    def create_line_edit(placeholder: str = "", enabled: bool = True,
                        min_height: int = 35, validator: bool = True) -> QLineEdit:
        """Create a styled line edit"""
        line_edit = QLineEdit()
        line_edit.setPlaceholderText(placeholder)
        line_edit.setMinimumHeight(min_height)
        line_edit.setEnabled(enabled)
        if validator:
            apply_no_special_chars_validator(line_edit)
        return line_edit
    
    @staticmethod
    def create_list_widget(selection_mode=QListWidget.MultiSelection,
                          min_height: int = 140, enabled: bool = True) -> QListWidget:
        """Create a styled list widget"""
        list_widget = QListWidget()
        list_widget.setSelectionMode(selection_mode)
        list_widget.setMinimumHeight(min_height)
        list_widget.setEnabled(enabled)
        list_widget.setStyleSheet("""
            QListWidget {
                background-color: #404040;
                border: 1px solid #555555;
                padding: 6px;
                border-radius: 4px;
                color: #ffffff;
                font-size: 13px;
            }
            QListWidget:disabled {
                background-color: #2b2b2b;
                border: 1px solid #444444;
                color: #888888;
            }
            QListWidget::item { padding: 4px; }
            QListWidget::item:selected { background-color: #ff6b35; color: white; }
            QListWidget::item:disabled { color: #666666; }
        """)
        return list_widget
    
    @staticmethod
    def create_group_box(title: str) -> QGroupBox:
        """Create a styled group box"""
        group_box = QGroupBox(title)
        group_box.setStyleSheet("""
            QGroupBox {
                color: #ffffff;
                border: 1px solid #666666;
                border-radius: 6px;
                padding-top: 20px;
                margin: 15px 0;
                font-weight: bold;
                font-size: 14px;
            }
            QGroupBox::title {
                color: #ff6b35;
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px 0 8px;
                font-size: 14px;
            }
        """)
        return group_box
    
    @staticmethod
    def apply_combo_style(combo: QComboBox):
        """Apply standard combo box styling"""
        combo.setStyleSheet("""
            QComboBox {
                background-color: #404040;
                border: 1px solid #555555;
                padding: 10px;
                padding-right: 35px;
                border-radius: 4px;
                color: #ffffff;
                min-width: 150px;
                font-size: 13px;
                min-height: 15px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 30px;
                border: none;
                border-left: 1px solid #555555;
                border-radius: 0 4px 4px 0;
                background: #ff6b35;
            }
            QComboBox::down-arrow {
                image: none;
                text: "˅";
                color: #ffffff;
                font-size: 20px;
                font-weight: bold;
                right: 8px;
                top: 1px;
            }
            QComboBox QAbstractItemView {
                background-color: #404040;
                color: #ffffff;
                selection-background-color: #ff6b35;
                padding: 5px;
                border: 1px solid #555555;
                border-radius: 4px;
            }
            QComboBox:disabled {
                background-color: #2b2b2b;
                border: 1px solid #444444;
                color: #888888;
            }
        """)
    
    @staticmethod
    def apply_input_style(widget):
        """Apply standard input styling"""
        widget.setStyleSheet("""
            QLineEdit, QSpinBox, QDateTimeEdit, QDoubleSpinBox {
                background-color: #404040;
                border: 1px solid #555555;
                padding: 10px;
                border-radius: 4px;
                color: #ffffff;
                font-size: 13px;
                min-height: 15px;
            }
            QLineEdit:focus, QSpinBox:focus, QDateTimeEdit:focus, QDoubleSpinBox:focus {
                border: 2px solid #ff6b35;
            }
            QLineEdit:disabled {
                background-color: #2b2b2b;
                border: 1px solid #444444;
                color: #888888;
            }
        """)



