# Data formatters
from datetime import datetime
from typing import Optional


def format_datetime_display(dt_string: str) -> str:
    """Format datetime for display"""
    if not dt_string:
        return "N/A"

    try:
        if 'T' in dt_string:
            dt = datetime.fromisoformat(dt_string.replace('Z', ''))
            return dt.strftime('%m/%d/%Y %H:%M')
        return dt_string
    except:
        return dt_string


def format_duration(minutes: Optional[int]) -> str:
    """Format duration in minutes"""
    if not minutes:
        return "N/A"

    try:
        minutes = int(minutes)
        if minutes < 60:
            return f"{minutes} min"
        else:
            hours = minutes // 60
            mins = minutes % 60
            return f"{hours}h {mins}m"
    except:
        return "N/A"


def format_battery_level(level: Optional[int]) -> str:
    """Format battery level"""
    if level is None:
        return "N/A"

    try:
        level = int(level)
        return f"{level}%"
    except:
        return "N/A"