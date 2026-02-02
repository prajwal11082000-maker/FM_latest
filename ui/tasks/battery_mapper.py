"""
Battery-to-Distance Mapping Module

Maps battery levels to maximum travel distances for autonomous warehouse robots.
"""
from typing import Dict, Tuple


class BatteryMapper:
    """Maps battery percentage to maximum travel distance in millimeters"""
    
    # Battery range to distance mapping (in millimeters)
    BATTERY_RANGES: Dict[Tuple[int, int], int] = {
        (0, 20): 0,
        (21, 30): 150000,
        (31, 40): 300000,
        (41, 50): 450000,
        (51, 60): 600000,
        (61, 70): 750000,
        (71, 80): 900000,
        (81, 90): 1050000,
        (91, 100): 2000000,
    }
    
    @staticmethod
    def get_max_travel_distance(battery_level: int) -> int:
        """
        Get maximum travel distance for a given battery level.
        
        Args:
            battery_level: Battery percentage (0-100)
            
        Returns:
            Maximum travel distance in millimeters
        """
        if battery_level <= 20:
            return 0
        elif 21 <= battery_level <= 30:
            return 150000
        elif 31 <= battery_level <= 40:
            return 300000
        elif 41 <= battery_level <= 50:
            return 450000
        elif 51 <= battery_level <= 60:
            return 600000
        elif 61 <= battery_level <= 70:
            return 750000
        elif 71 <= battery_level <= 80:
            return 900000
        elif 81 <= battery_level <= 90:
            return 105000
        elif 91 <= battery_level <= 100:
            return 2000000
        return 0
    
    @staticmethod
    def parse_battery(battery_value) -> int:
        """
        Parse battery value from various formats to integer percentage.
        
        Args:
            battery_value: Battery value (string, int, float, or None)
            
        Returns:
            Battery percentage as integer (0-100)
        """
        try:
            if battery_value is None:
                return 0
            battery_str = str(battery_value).strip()
            if not battery_str:
                return 0
            return int(float(battery_str))
        except (ValueError, TypeError):
            return 0
    
    @staticmethod
    def get_battery_range_label(battery_level: int) -> str:
        """
        Get human-readable label for battery range.
        
        Args:
            battery_level: Battery percentage
            
        Returns:
            Range label like "21-30%" or "Low Battery"
        """
        if battery_level <= 20:
            return "Low Battery (≤20%)"
        elif 21 <= battery_level <= 30:
            return "21-30%"
        elif 31 <= battery_level <= 40:
            return "31-40%"
        elif 41 <= battery_level <= 50:
            return "41-50%"
        elif 51 <= battery_level <= 60:
            return "51-60%"
        elif 61 <= battery_level <= 70:
            return "61-70%"
        elif 71 <= battery_level <= 80:
            return "71-80%"
        elif 81 <= battery_level <= 90:
            return "81-90%"
        elif 91 <= battery_level <= 100:
            return "91-100%"
        return "Unknown"



