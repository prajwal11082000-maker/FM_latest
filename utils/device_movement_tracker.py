from pathlib import Path
import csv
from datetime import datetime
from typing import Tuple, Optional, Dict
from .turn_validator import TurnValidator

class DeviceMovementTracker:
    @staticmethod
    def validate_motor_values(right_motor: float, left_motor: float) -> bool:
        """
        Validate that motor values are within the allowed range (-2 to 2)
        or are exact values for turns: (45.0, 45.0). U-turns also require 45/45 motors
        (plus specific drive ranges validated elsewhere), not 180/180.
        """
        return (
            (-2 <= right_motor <= 2 and -2 <= left_motor <= 2) or
            (right_motor == 45.0 and left_motor == 45.0)
        )

    @staticmethod
    def get_movement_direction(right_drive: int, left_drive: int) -> str:
        """
        Determine movement direction based on drive values
        Returns: 'forward', 'backward', or 'stationary'
        """
        if right_drive > 0 and left_drive > 0:
            return 'forward'
        elif right_drive < 0 and left_drive < 0:
            return 'backward'
        return 'stationary'

    @staticmethod
    def get_movement_distance(right_drive: int, left_drive: int) -> int:
        """
        Calculate movement distance in millimeters
        Uses average of absolute values of right and left drive
        """
        return abs(round((right_drive + left_drive) / 2))

    @staticmethod
    def log_device_movement(
        device_id: str,
        right_drive: int,
        left_drive: int,
        right_motor: float,
        left_motor: float,
        current_location: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Log device movement to its CSV file
        Returns: (success: bool, error_message: Optional[str])
        """
        try:
            # Validate motor values range
            if not DeviceMovementTracker.validate_motor_values(right_motor, left_motor):
                return False, "Motor values must be between -2 and 2"
            
            # Check if this is a potential turn and validate motor values are exactly 45
            # for turn conditions (when drive values suggest turning)
            is_potential_turn = (
                (right_drive > 0 and left_drive < 0) or  # Right turn pattern
                (right_drive < 0 and left_drive > 0)     # Left turn pattern
            )
            
            if is_potential_turn:
                turn_validator = TurnValidator()
                if not turn_validator.is_valid_turn_motor_values(right_motor, left_motor):
                    return False, (
                        f"Turn movement detected but motor values are not exactly 45.0: "
                        f"right_motor={right_motor}, left_motor={left_motor}. "
                        f"Robot will not turn unless both motor values are exactly 45.0"
                    )

            # Create file path
            device_file_path = Path('data/device_logs') / f"{device_id}.csv"
            device_file_path.parent.mkdir(parents=True, exist_ok=True)

            # Ensure file exists with headers
            if not device_file_path.exists():
                with open(device_file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        'timestamp',
                        'right_drive',
                        'left_drive',
                        'right_motor',
                        'left_motor',
                        'current_location'
                    ])

            # Add the movement log entry
            with open(device_file_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    right_drive,
                    left_drive,
                    right_motor,
                    left_motor,
                    current_location
                ])

            return True, None

        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_device_location_info(device_id: str) -> Dict:
        """
        Get information about device's current location and movement
        Returns a dictionary with:
        - current_location: The zone ID where the device is
        - movement_direction: forward/backward/stationary
        - distance_from_location: Distance in mm from the current location
        """
        try:
            device_file_path = Path('data/device_logs') / f"{device_id}.csv"
            if not device_file_path.exists():
                return {
                    'current_location': 'unknown',
                    'movement_direction': 'unknown',
                    'distance_from_location': 0
                }

            # Read the last entry from the CSV file
            with open(device_file_path, 'r', newline='', encoding='utf-8') as f:
                reader = list(csv.DictReader(f))
                if not reader:
                    return {
                        'current_location': 'unknown',
                        'movement_direction': 'unknown',
                        'distance_from_location': 0
                    }

                last_entry = reader[-1]
                right_drive = int(last_entry['right_drive'])
                left_drive = int(last_entry['left_drive'])

                return {
                    'current_location': last_entry['current_location'],
                    'movement_direction': DeviceMovementTracker.get_movement_direction(right_drive, left_drive),
                    'distance_from_location': DeviceMovementTracker.get_movement_distance(right_drive, left_drive)
                }

        except Exception as e:
            print(f"Error getting device location info: {e}")
            return {
                'current_location': 'error',
                'movement_direction': 'error',
                'distance_from_location': 0
            }

    @staticmethod
    def describe_device_position(device_id: str) -> str:
        """
        Get a human-readable description of the device's current position
        """
        info = DeviceMovementTracker.get_device_location_info(device_id)
        
        if info['movement_direction'] == 'stationary':
            return f"Device is at location {info['current_location']}"
        
        direction = 'forward' if info['movement_direction'] == 'forward' else 'backward'
        return f"Device has moved {direction} {info['distance_from_location']}mm from location {info['current_location']}"
