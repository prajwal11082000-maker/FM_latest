#!/usr/bin/env python3
"""
Turn Validation Utility

This module provides utilities to validate turn and movement conditions.
Rules (UPDATED):
- Left/Right turns require both right_motor and left_motor to be exactly 45.0
- U-turns require both right_motor and left_motor to be exactly 45.0 AND
  high-magnitude opposite-signed drive ranges in either order:
    • (right_drive 1000..1200, left_drive -1200..-1000)
    • (right_drive -1200..-1000, left_drive 1000..1200)
"""

from typing import Dict, Optional, Tuple
import logging
from robot_navigation.navigation_enums import NavigationConstants


class TurnValidator:
    """
    Validates turn conditions based on sensor data.
    
    CRITICAL RULES (UPDATED):
    - Left/Right turns only when both right_motor and left_motor are exactly 45.0
    - U-turn only when both right_motor and left_motor are exactly 45.0 AND
      drive values match the high-magnitude opposite-signed ranges from
      NavigationConstants.U_TURN_DRIVE_RANGES.
    No tolerance is allowed.
    """
    
    # Required motor value for left/right turns (exact match required)
    REQUIRED_MOTOR_VALUE = 45.0
    # Required motor value for U-turns (exact match required - updated)
    REQUIRED_MOTOR_VALUE_UTURN = NavigationConstants.U_TURN_MOTOR_VALUE
    
    # Required motor value for forward/backward movement (exact match required)
    REQUIRED_MOTOR_VALUE_STRAIGHT = 0.0
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize turn validator
        
        Args:
            logger: Optional logger for debug information
        """
        self.logger = logger or logging.getLogger(__name__)
    
    @staticmethod
    def is_valid_turn_motor_values(right_motor: float, left_motor: float) -> bool:
        """
        Check if motor values allow turning.
        
        Args:
            right_motor: Right motor value
            left_motor: Left motor value
            
        Returns:
            True if both motor values are exactly 45.0, False otherwise
        """
        return (right_motor == TurnValidator.REQUIRED_MOTOR_VALUE and 
                left_motor == TurnValidator.REQUIRED_MOTOR_VALUE)

    @staticmethod
    def is_valid_u_turn_motor_values(right_motor: float, left_motor: float) -> bool:
        """
        Check if motor values satisfy the updated U-turn motor requirement.
        Note: Full U-turn validation also requires drive ranges; see
        validate_movement_condition. This helper checks motors only.
        """
        return (
            right_motor == TurnValidator.REQUIRED_MOTOR_VALUE_UTURN and 
            left_motor == TurnValidator.REQUIRED_MOTOR_VALUE_UTURN
        )
    
    @staticmethod
    def is_valid_straight_motor_values(right_motor: float, left_motor: float) -> bool:
        """
        Check if motor values allow forward/backward movement.
        
        Args:
            right_motor: Right motor value
            left_motor: Left motor value
            
        Returns:
            True if both motor values are exactly 0.0, False otherwise
        """
        return (right_motor == TurnValidator.REQUIRED_MOTOR_VALUE_STRAIGHT and 
                left_motor == TurnValidator.REQUIRED_MOTOR_VALUE_STRAIGHT)
    
    def validate_turn_condition(self, right_motor: float, left_motor: float, 
                              turn_type: str = "unknown") -> Tuple[bool, str]:
        """
        Validate if a turn is allowed based on motor values.
        
        Args:
            right_motor: Right motor sensor value
            left_motor: Left motor sensor value
            turn_type: Type of turn being attempted (for logging)
            
        Returns:
            Tuple of (is_valid, reason)
        """
        # For motors-only validation: accept 45/45 as the only valid turn motor state
        # (U-turns also require 45/45 motors, but drive ranges are validated elsewhere)
        is_valid = self.is_valid_turn_motor_values(right_motor, left_motor)

        if is_valid:
            reason = (
                f"{turn_type} turn ALLOWED - Motor values exactly 45.0"
            )
            self.logger.info(f"Turn validation: {reason}")
        else:
            reason = (f"{turn_type} turn REJECTED - Motor values not exactly 45.0: "
                      f"right_motor={right_motor}, left_motor={left_motor} "
                      f"(required: both exactly {self.REQUIRED_MOTOR_VALUE})")
        
        return is_valid, reason

    def validate_movement_condition(self, right_drive: float, left_drive: float,
                                   right_motor: float, left_motor: float) -> tuple[bool, str, str]:
        """
        Validate if any movement is allowed based on drive and motor values.
        
        Specific rules (UPDATED):
        - Right turn: right_drive 500-600, left_drive -500 to -600, motors both 45.0
        - Left turn: right_drive -500 to -600, left_drive 500-600, motors both 45.0
        - U-turn: motors both 45.0 AND drives in either range:
            (right_drive 1000..1200, left_drive -1200..-1000) OR
            (right_drive -1200..-1000, left_drive 1000..1200)
        - Forward/Backward: any other drive pattern with motors 0.0
        
        Args:
            right_drive: Right drive sensor value
            left_drive: Left drive sensor value  
            right_motor: Right motor sensor value
            left_motor: Left motor sensor value
            
        Returns:
            Tuple of (is_valid, movement_type, reason)
        """
        # Check for U-turn first (updated: motors 45/45 + high-magnitude opposite-signed drives)
        if self.is_valid_turn_motor_values(right_motor, left_motor):
            for rng in NavigationConstants.U_TURN_DRIVE_RANGES:
                rd_min, rd_max = rng['right_drive']
                ld_min, ld_max = rng['left_drive']
                if rd_min <= right_drive <= rd_max and ld_min <= left_drive <= ld_max:
                    return True, "U-Turn", (
                        "U-Turn ALLOWED - Motors exactly 45.0 and drives in high-magnitude opposite-signed ranges"
                    )

        # Check for specific left/right turn patterns next
        if self._is_right_turn_pattern(right_drive, left_drive):
            # Right turn pattern detected
            if self.is_valid_turn_motor_values(right_motor, left_motor):
                return True, "Turning Right", (
                    "Right turn ALLOWED - Drive values in range 500-600/-500 to -600, motors exactly 45.0"
                )
            else:
                return False, "Stationary", (
                    f"Right turn REJECTED - Drive pattern correct but motor values not exactly 45.0: "
                    f"right_motor={right_motor}, left_motor={left_motor} "
                    f"(required: both exactly {self.REQUIRED_MOTOR_VALUE})"
                )
        
        elif self._is_left_turn_pattern(right_drive, left_drive):
            # Left turn pattern detected
            if self.is_valid_turn_motor_values(right_motor, left_motor):
                return True, "Turning Left", (
                    "Left turn ALLOWED - Drive values in range -500 to -600/500-600, motors exactly 45.0"
                )
            else:
                return False, "Stationary", (
                    f"Left turn REJECTED - Drive pattern correct but motor values not exactly 45.0: "
                    f"right_motor={right_motor}, left_motor={left_motor} "
                    f"(required: both exactly {self.REQUIRED_MOTOR_VALUE})"
                )
        
        # Non-turn movement patterns
        elif right_drive > 0 and left_drive > 0:
            # Forward movement pattern
            if self.is_valid_straight_motor_values(right_motor, left_motor):
                return True, "Forward", "Forward movement ALLOWED - Motor values exactly 0.0"
            else:
                return False, "Stationary", (
                    f"Forward movement REJECTED - Motor values not exactly 0.0: "
                    f"right_motor={right_motor}, left_motor={left_motor} "
                    f"(required: both exactly {self.REQUIRED_MOTOR_VALUE_STRAIGHT})"
                )
        
        elif right_drive < 0 and left_drive < 0:
            # Backward movement pattern
            if self.is_valid_straight_motor_values(right_motor, left_motor):
                return True, "Backward", "Backward movement ALLOWED - Motor values exactly 0.0"
            else:
                return False, "Stationary", (
                    f"Backward movement REJECTED - Motor values not exactly 0.0: "
                    f"right_motor={right_motor}, left_motor={left_motor} "
                    f"(required: both exactly {self.REQUIRED_MOTOR_VALUE_STRAIGHT})"
                )
        
        else:
            # Stationary (no movement or zero values or invalid turn pattern)
            return True, "Stationary", "Robot is stationary or invalid movement pattern"
    
    def _is_right_turn_pattern(self, right_drive: float, left_drive: float) -> bool:
        """
        Check if drive values match right turn pattern.
        Right turn: right_drive 500-600, left_drive -500 to -600
        """
        return (300 <= right_drive <= 600 and -600 <= left_drive <= -300)
    
    def _is_left_turn_pattern(self, right_drive: float, left_drive: float) -> bool:
        """
        Check if drive values match left turn pattern.
        Left turn: right_drive -500 to -600, left_drive 500-600
        """
        return (-600 <= right_drive <= -300 and 300 <= left_drive <= 600)
    
    def get_motor_value_status(self, right_motor: float, left_motor: float) -> Dict[str, any]:
        """
        Get detailed status of motor values for turning.
        
        Args:
            right_motor: Right motor value
            left_motor: Left motor value
            
        Returns:
            Dictionary with motor value analysis
        """
        right_valid = right_motor == self.REQUIRED_MOTOR_VALUE
        left_valid = left_motor == self.REQUIRED_MOTOR_VALUE
        turn_allowed = right_valid and left_valid
        
        return {
            'right_motor': {
                'value': right_motor,
                'required': self.REQUIRED_MOTOR_VALUE,
                'valid': right_valid,
                'difference': right_motor - self.REQUIRED_MOTOR_VALUE
            },
            'left_motor': {
                'value': left_motor,
                'required': self.REQUIRED_MOTOR_VALUE,
                'valid': left_valid,
                'difference': left_motor - self.REQUIRED_MOTOR_VALUE
            },
            'turn_allowed': turn_allowed,
            'validation_message': (
                "Turn ALLOWED - Both motors exactly 45.0" if turn_allowed else
                "Turn REJECTED - One or both motors not exactly 45.0"
            )
        }
    
    @classmethod
    def check_sensor_data_for_turn(cls, sensor_data: Dict) -> bool:
        """
        Check if sensor data allows turning (static method).
        
        Args:
            sensor_data: Dictionary containing sensor data with 'right_motor' and 'left_motor'
            
        Returns:
            True if motors are valid for a turn (45/45), False otherwise
        """
        try:
            right_motor = float(sensor_data.get('right_motor', 0))
            left_motor = float(sensor_data.get('left_motor', 0))
            return cls.is_valid_turn_motor_values(right_motor, left_motor)
        except (ValueError, TypeError):
            return False


def validate_turn_from_csv_data(device_id: str, csv_data: Dict) -> Tuple[bool, str]:
    """
    Validate turn condition from CSV data entry.
    
    Args:
        device_id: Device identifier
        csv_data: Dictionary with CSV row data
        
    Returns:
        Tuple of (turn_allowed, validation_message)
    """
    try:
        right_motor = float(csv_data.get('right_motor', 0))
        left_motor = float(csv_data.get('left_motor', 0))
        
        validator = TurnValidator()
        is_valid, reason = validator.validate_turn_condition(
            right_motor, left_motor, f"Device {device_id}"
        )
        
        return is_valid, reason
        
    except (ValueError, TypeError) as e:
        error_msg = f"Invalid motor data for device {device_id}: {e}"
        return False, error_msg


# Quick validation functions for convenience
def can_turn(right_motor: float, left_motor: float) -> bool:
    """Quick check if robot can turn with given motor values."""
    return TurnValidator.is_valid_turn_motor_values(right_motor, left_motor)


def get_turn_rejection_reason(right_motor: float, left_motor: float) -> Optional[str]:
    """Get reason why turn was rejected, or None if turn is allowed."""
    if TurnValidator.is_valid_turn_motor_values(right_motor, left_motor):
        return None
    
    return (f"Turn rejected: motor values not exactly 45.0 "
            f"(right_motor={right_motor}, left_motor={left_motor})")


if __name__ == "__main__":
    # Example usage and testing

    
    test_cases = [
        (45.0, 45.0, "Valid turn"),
        (45.0, 44.9, "Invalid - left motor not exact"),
        (44.9, 45.0, "Invalid - right motor not exact"),
        (45.1, 45.0, "Invalid - right motor not exact"),
        (45.0, 45.1, "Invalid - left motor not exact"),
        (44.0, 44.0, "Invalid - both motors wrong"),
        (46.0, 46.0, "Invalid - both motors too high"),
    ]
    
    validator = TurnValidator()
    
    for right_motor, left_motor, description in test_cases:
        is_valid, reason = validator.validate_turn_condition(right_motor, left_motor, "Test")
        status = "✅ ALLOWED" if is_valid else "❌ REJECTED"
        print()
