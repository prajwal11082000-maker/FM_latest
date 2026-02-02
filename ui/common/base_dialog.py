from PyQt5.QtWidgets import QDialog
from PyQt5.QtCore import Qt


class BaseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(True)

        # Apply dark theme
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
        """)

    def keyPressEvent(self, event):
        """Ignore Enter/Return keys to prevent accidental dialog closing"""
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # If the focus is on a button, we might want to allow it to be clicked
            # But the user specifically asked that Enter does NOT trigger close behavior.
            # So we ignore it completely.
            return
        super().keyPressEvent(event)