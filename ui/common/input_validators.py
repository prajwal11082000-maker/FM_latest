import re

from PyQt5.QtWidgets import QLineEdit, QTextEdit


# Characters that should NOT be accepted in certain text inputs
_DISALLOWED_CHARS_PATTERN = re.compile(r'[\\/:*?"\-<>~,;|#%{}&$@!\'+=^()\[\]]')


def apply_no_special_chars_validator(widget):
    """
    Strip disallowed special characters from text inputs.

    This helper can be attached to both QLineEdit and QTextEdit widgets.
    It silently removes the configured special characters whenever the
    user types them, so they never get stored in the field value.
    """

    if isinstance(widget, QLineEdit):

        def _on_text_changed():
            text = widget.text()
            cleaned = _DISALLOWED_CHARS_PATTERN.sub("", text)
            if cleaned != text:
                cursor_pos = widget.cursorPosition()
                widget.blockSignals(True)
                widget.setText(cleaned)
                widget.blockSignals(False)
                if cursor_pos > len(cleaned):
                    cursor_pos = len(cleaned)
                widget.setCursorPosition(cursor_pos)

        widget.textChanged.connect(_on_text_changed)

    elif isinstance(widget, QTextEdit):

        def _on_text_changed():
            text = widget.toPlainText()
            cleaned = _DISALLOWED_CHARS_PATTERN.sub("", text)
            if cleaned != text:
                widget.blockSignals(True)
                widget.setPlainText(cleaned)
                widget.blockSignals(False)

        widget.textChanged.connect(_on_text_changed)


