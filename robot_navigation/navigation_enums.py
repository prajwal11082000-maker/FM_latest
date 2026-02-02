#!/usr/bin/env python3
"""
Navigation Enums and Constants

Defines the core enumerations and constants used throughout the robot navigation system.
"""

from enum import Enum, IntEnum
from typing import Tuple, Dict


class Direction(Enum):
    """Enumeration for cardinal directions"""
    NORTH = "north"
    SOUTH = "south" 
    EAST = "east"
    WEST = "west"
    
    def __str__(self):
        return self.value
        
    @classmethod
    def from_string(cls, direction_str: str) -> 'Direction':
        """Convert string to Direction enum"""
        direction_map = {
            'north': cls.NORTH,
            'south': cls.SOUTH,
            'east': cls.EAST,
            'west': cls.WEST,
            'n': cls.NORTH,
            's': cls.SOUTH,
            'e': cls.EAST,
            'w': cls.WEST
        }
        return direction_map.get(direction_str.lower(), cls.NORTH)


class TurnAction(Enum):
    """Enumeration for turn actions"""
    LEFT = "left"
    RIGHT = "right"
    STRAIGHT = "straight"
    UTURN = "u_turn"
    
    def __str__(self):
        return self.value


class NavigationStatus(Enum):
    """Enumeration for navigation status"""
    IDLE = "idle"
    NAVIGATING = "navigating"
    TURNING = "turning"
    ARRIVED = "arrived"
    ERROR = "error"
    
    def __str__(self):
        return self.value


# Navigation Constants
class NavigationConstants:
    """Constants for robot navigation system"""
    
    # Default robot starting position (x, y, rotation_x, rotation_y, zone)
    DEFAULT_INITIAL_POSITION: Tuple[int, int, int, int, int] = (0, 0, 0, 0, 2)
    
    # Default facing direction
    DEFAULT_DIRECTION = Direction.NORTH
    
    # Sensor value ranges for turn detection
    # CRITICAL: Motor values must be EXACTLY 45 for turns to happen
    RIGHT_TURN_RANGES = {
        'right_drive': (300, 600),      # between 500 to 600
        'left_drive': (-600, -300),     # between -500 to -600
        'right_motor': 45.0,            # EXACTLY 45 - no tolerance allowed
        'left_motor': 45.0,             # EXACTLY 45 - no tolerance allowed
    }
    
    LEFT_TURN_RANGES = {
        'right_drive': (-600, -300),    # between -500 to -600  
        'left_drive': (300, 600),       # between 500 to 600
        'right_motor': 45.0,            # EXACTLY 45 - no tolerance allowed
        'left_motor': 45.0,             # EXACTLY 45 - no tolerance allowed
    }
    
    # Direction mappings for turns
    RIGHT_TURN_MAP: Dict[Direction, Direction] = {
        Direction.NORTH: Direction.EAST,
        Direction.EAST: Direction.SOUTH,
        Direction.SOUTH: Direction.WEST,
        Direction.WEST: Direction.NORTH
    }
    
    LEFT_TURN_MAP: Dict[Direction, Direction] = {
        Direction.NORTH: Direction.WEST,
        Direction.WEST: Direction.SOUTH,
        Direction.SOUTH: Direction.EAST,
        Direction.EAST: Direction.NORTH
    }
    
    # Direction mapping for U-turn (180° flip)
    U_TURN_MAP: Dict[Direction, Direction] = {
        Direction.NORTH: Direction.SOUTH,
        Direction.SOUTH: Direction.NORTH,
        Direction.EAST: Direction.WEST,
        Direction.WEST: Direction.EAST
    }
    
    # Zone coordinate offsets by direction
    DIRECTION_OFFSETS: Dict[Direction, Tuple[int, int]] = {
        Direction.NORTH: (0, 1),   # Move up
        Direction.SOUTH: (0, -1),  # Move down
        Direction.EAST: (1, 0),    # Move right
        Direction.WEST: (-1, 0)    # Move left
    }

    # U-turn detection criteria (updated):
    # - Motors must be EXACTLY 45.0 (no tolerance)
    # - Drives must be high-magnitude, opposite-signed in either order:
    #   (right_drive 1000..1200, left_drive -1200..-1000) OR
    #   (right_drive -1200..-1000, left_drive 1000..1200)
    U_TURN_MOTOR_VALUE: float = 45.0
    U_TURN_DRIVE_RANGES = [
        {
            'right_drive': (610, 1200),
            'left_drive': (-1200, -610)
        },
        {
            'right_drive': (-1200, -610),
            'left_drive': (610, 1200)
        }
    ]


class SensorData:
    """Container for robot sensor data"""
    
    def __init__(self, right_drive: float, left_drive: float, 
                 right_motor: float, left_motor: float, current_location: int):
        self.right_drive = right_drive
        self.left_drive = left_drive
        self.right_motor = right_motor
        self.left_motor = left_motor
        self.current_location = current_location
    
    def __repr__(self):
        return (f"SensorData(right_drive={self.right_drive}, "
                f"left_drive={self.left_drive}, right_motor={self.right_motor}, "
                f"left_motor={self.left_motor}, current_location={self.current_location})")
    
    def to_dict(self) -> Dict:
        """Convert sensor data to dictionary"""
        return {
            'right_drive': self.right_drive,
            'left_drive': self.left_drive, 
            'right_motor': self.right_motor,
            'left_motor': self.left_motor,
            'current_location': self.current_location
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SensorData':
        """Create SensorData from dictionary"""
        return cls(
            right_drive=data['right_drive'],
            left_drive=data['left_drive'],
            right_motor=data['right_motor'],
            left_motor=data['left_motor'],
            current_location=data['current_location']
        )
