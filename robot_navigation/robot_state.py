#!/usr/bin/env python3
"""
Robot State Management

Manages the current state of the robot including position, direction, and navigation status.
"""

import time
from datetime import datetime
from typing import Tuple, Optional, Dict, List
from dataclasses import dataclass, field

from .navigation_enums import Direction, NavigationStatus, NavigationConstants


@dataclass
class Position:
    """Represents a robot position with coordinates and zone information"""
    x: int = 0
    y: int = 0
    rotation_x: int = 0
    rotation_y: int = 0
    zone: int = 2
    timestamp: float = field(default_factory=time.time)
    
    def __post_init__(self):
        """Set timestamp if not provided"""
        if self.timestamp == 0:
            self.timestamp = time.time()
    
    @property
    def coordinates(self) -> Tuple[int, int, int, int, int]:
        """Get position as tuple (x, y, rotation_x, rotation_y, zone)"""
        return (self.x, self.y, self.rotation_x, self.rotation_y, self.zone)
    
    def distance_to(self, other: 'Position') -> float:
        """Calculate distance to another position"""
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5
    
    def __str__(self):
        return f"Position({self.x}, {self.y}, {self.rotation_x}, {self.rotation_y}, zone={self.zone})"


@dataclass
class NavigationHistory:
    """Records navigation history and movements"""
    positions: List[Position] = field(default_factory=list)
    directions: List[Direction] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    timestamps: List[float] = field(default_factory=list)
    max_history: int = 100
    
    def add_entry(self, position: Position, direction: Direction, action: str):
        """Add a navigation history entry"""
        self.positions.append(position)
        self.directions.append(direction)
        self.actions.append(action)
        self.timestamps.append(time.time())
        
        # Maintain max history limit
        if len(self.positions) > self.max_history:
            self.positions.pop(0)
            self.directions.pop(0)
            self.actions.pop(0)
            self.timestamps.pop(0)
    
    def get_recent_entries(self, count: int = 10) -> List[Dict]:
        """Get recent navigation entries"""
        recent_count = min(count, len(self.positions))
        entries = []
        
        for i in range(-recent_count, 0):
            entries.append({
                'position': self.positions[i],
                'direction': self.directions[i],
                'action': self.actions[i],
                'timestamp': self.timestamps[i],
                'datetime': datetime.fromtimestamp(self.timestamps[i])
            })
        
        return entries
    
    def clear(self):
        """Clear navigation history"""
        self.positions.clear()
        self.directions.clear()
        self.actions.clear()
        self.timestamps.clear()


class RobotState:
    """
    Manages the complete state of the robot including position, direction, 
    status, and navigation history.
    """
    
    def __init__(self, initial_position: Optional[Tuple[int, int, int, int, int]] = None,
                 initial_direction: Optional[Direction] = None):
        """
        Initialize robot state
        
        Args:
            initial_position: Starting position tuple (x, y, rotation_x, rotation_y, zone)
            initial_direction: Starting direction
        """
        # Set initial position
        if initial_position is None:
            initial_position = NavigationConstants.DEFAULT_INITIAL_POSITION
        
        self.current_position = Position(*initial_position)
        
        # Set initial direction
        self.current_direction = initial_direction or NavigationConstants.DEFAULT_DIRECTION
        
        # Navigation status
        self.navigation_status = NavigationStatus.IDLE
        
        # Target information
        self.target_position: Optional[Position] = None
        self.target_direction: Optional[Direction] = None
        
        # Navigation history
        self.history = NavigationHistory()
        
        # State tracking
        self.last_update_time = time.time()
        self.state_lock = False  # Simple locking mechanism
        
        # Add initial state to history
        self.history.add_entry(self.current_position, self.current_direction, "initialized")
    
    def update_position(self, new_position: Tuple[int, int, int, int, int], 
                       action: str = "position_update"):
        """
        Update robot's current position
        
        Args:
            new_position: New position tuple (x, y, rotation_x, rotation_y, zone)
            action: Description of the action that caused this update
        """
        if self.state_lock:
            return False
            
        old_position = self.current_position
        self.current_position = Position(*new_position)
        self.last_update_time = time.time()
        
        # Add to history
        self.history.add_entry(self.current_position, self.current_direction, action)
        
        return True
    
    def update_direction(self, new_direction: Direction, action: str = "direction_change"):
        """
        Update robot's current direction
        
        Args:
            new_direction: New facing direction
            action: Description of the action that caused this update
        """
        if self.state_lock:
            return False
            
        old_direction = self.current_direction
        self.current_direction = new_direction
        self.last_update_time = time.time()
        
        # Add to history
        self.history.add_entry(self.current_position, self.current_direction, action)
        
        return True
    
    def set_target(self, target_position: Optional[Tuple[int, int, int, int, int]] = None,
                   target_direction: Optional[Direction] = None):
        """
        Set navigation target
        
        Args:
            target_position: Target position tuple
            target_direction: Target direction
        """
        if target_position:
            self.target_position = Position(*target_position)
        
        self.target_direction = target_direction
        
        if self.target_position or self.target_direction:
            self.navigation_status = NavigationStatus.NAVIGATING
    
    def clear_target(self):
        """Clear current navigation target"""
        self.target_position = None
        self.target_direction = None
        self.navigation_status = NavigationStatus.IDLE
    
    def set_status(self, status: NavigationStatus):
        """Update navigation status"""
        self.navigation_status = status
        self.last_update_time = time.time()
    
    def lock_state(self):
        """Lock state to prevent updates during critical operations"""
        self.state_lock = True
    
    def unlock_state(self):
        """Unlock state to allow updates"""
        self.state_lock = False
    
    def get_next_zone_position(self, direction: Direction) -> Position:
        """
        Calculate the next zone position based on current position and direction
        
        Args:
            direction: Direction to move in
            
        Returns:
            Position object representing the next zone
        """
        offset_x, offset_y = NavigationConstants.DIRECTION_OFFSETS[direction]
        
        new_x = self.current_position.x + offset_x
        new_y = self.current_position.y + offset_y
        
        # Keep rotation and zone the same, update coordinates
        return Position(
            x=new_x,
            y=new_y,
            rotation_x=self.current_position.rotation_x,
            rotation_y=self.current_position.rotation_y,
            zone=self.current_position.zone
        )
    
    def is_at_target(self, tolerance: float = 0.1) -> bool:
        """
        Check if robot is at the target position
        
        Args:
            tolerance: Distance tolerance for considering arrival
            
        Returns:
            True if at target, False otherwise
        """
        if not self.target_position:
            return True
            
        distance = self.current_position.distance_to(self.target_position)
        direction_match = (self.target_direction is None or 
                          self.current_direction == self.target_direction)
        
        return distance <= tolerance and direction_match
    
    def get_state_summary(self) -> Dict:
        """
        Get a complete summary of the current robot state
        
        Returns:
            Dictionary containing all state information
        """
        return {
            'current_position': {
                'coordinates': self.current_position.coordinates,
                'x': self.current_position.x,
                'y': self.current_position.y,
                'rotation_x': self.current_position.rotation_x,
                'rotation_y': self.current_position.rotation_y,
                'zone': self.current_position.zone,
                'timestamp': self.current_position.timestamp
            },
            'current_direction': self.current_direction.value,
            'navigation_status': self.navigation_status.value,
            'target_position': (self.target_position.coordinates 
                              if self.target_position else None),
            'target_direction': (self.target_direction.value 
                               if self.target_direction else None),
            'last_update_time': self.last_update_time,
            'is_locked': self.state_lock,
            'recent_history': self.history.get_recent_entries(5)
        }
    
    def reset_to_initial(self):
        """Reset robot to initial state"""
        self.current_position = Position(*NavigationConstants.DEFAULT_INITIAL_POSITION)
        self.current_direction = NavigationConstants.DEFAULT_DIRECTION
        self.navigation_status = NavigationStatus.IDLE
        self.target_position = None
        self.target_direction = None
        self.last_update_time = time.time()
        self.state_lock = False
        
        # Clear history and add reset entry
        self.history.clear()
        self.history.add_entry(self.current_position, self.current_direction, "reset_to_initial")
    
    def __str__(self):
        return (f"RobotState(pos={self.current_position}, "
                f"dir={self.current_direction}, status={self.navigation_status})")
    
    def __repr__(self):
        return str(self)
