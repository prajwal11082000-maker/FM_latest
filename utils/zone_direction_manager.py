#!/usr/bin/env python3
"""
Zone Direction Manager

Manages turn-based zone navigation where:
1. Each zone can have an "active direction" set by a valid turn
2. Once a turn direction is locked in a zone, robot continues in that direction
3. Non-turn movements are ignored until a new valid turn is detected in the same zone
4. Each zone maintains its own independent direction state
"""

import json
import os
import time
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class ZoneDirectionState:
    """Represents the navigation state of a specific zone"""
    zone_id: int
    active_direction: Optional[str] = None  # 'north', 'south', 'east', 'west', or None
    turn_type: Optional[str] = None  # 'left', 'right', or None
    locked_at: Optional[float] = None  # Timestamp when direction was locked
    locked_by_device: Optional[str] = None  # Device that set this direction
    last_updated: Optional[float] = None  # Last time this zone state was accessed
    
    def is_locked(self) -> bool:
        """Check if this zone has a locked direction"""
        return self.active_direction is not None
    
    def lock_direction(self, direction: str, turn_type: str, device_id: str):
        """Lock a direction for this zone"""
        self.active_direction = direction
        self.turn_type = turn_type
        self.locked_at = time.time()
        self.locked_by_device = device_id
        self.last_updated = time.time()
    
    def clear_direction(self):
        """Clear the locked direction"""
        self.active_direction = None
        self.turn_type = None
        self.locked_at = None
        self.locked_by_device = None
        self.last_updated = time.time()
    
    def update_access_time(self):
        """Update the last accessed timestamp"""
        self.last_updated = time.time()


class ZoneDirectionManager:
    """
    Manages zone-based turn navigation system.
    
    Key Features:
    - Each zone can have one active turn direction
    - Turn directions are locked until overridden by new turns
    - Non-turn movements are processed based on zone's active direction
    - Persistent storage of zone states
    - Device-specific zone state tracking
    """
    
    def __init__(self, storage_path: str = 'data/zone_directions.json', 
                 logger: Optional[logging.Logger] = None):
        """
        Initialize Zone Direction Manager
        
        Args:
            storage_path: Path to store zone direction states
            logger: Optional logger instance
        """
        self.storage_path = Path(storage_path)
        self.logger = logger or logging.getLogger(__name__)
        
        # In-memory zone states: {zone_id: ZoneDirectionState}
        self.zone_states: Dict[int, ZoneDirectionState] = {}
        
        # Device-specific zone tracking: {device_id: {zone_id: ZoneDirectionState}}
        self.device_zone_states: Dict[str, Dict[int, ZoneDirectionState]] = {}
        
        # Ensure storage directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing states
        self.load_states()
        
        self.logger.info("ZoneDirectionManager initialized")
    
    def detect_and_process_movement(self, device_id: str, zone_id: int, 
                                   right_drive: float, left_drive: float,
                                   right_motor: float, left_motor: float, 
                                   robot_current_direction: str = None) -> Tuple[bool, str, str]:
        """
        Process movement and determine navigation action based on zone direction logic.
        
        Args:
            device_id: Device identifier
            zone_id: Current zone number
            right_drive, left_drive: Drive sensor values
            right_motor, left_motor: Motor sensor values
            robot_current_direction: Robot's current facing direction (optional)
            
        Returns:
            Tuple of (movement_allowed, movement_type, reason)
        """
        from .turn_validator import TurnValidator
        
        # Get current zone state for this device
        zone_state = self.get_device_zone_state(device_id, zone_id)
        
        # Validate the raw movement using TurnValidator
        validator = TurnValidator()
        is_valid_movement, raw_movement_type, validation_reason = validator.validate_movement_condition(
            right_drive, left_drive, right_motor, left_motor
        )
        
        # Check if this is a valid turn movement first (include U-turn)
        is_turn_movement = raw_movement_type in ["Turning Left", "Turning Right", "U-Turn"] if is_valid_movement else False
        
        # If this is NOT a turn movement but zone has a locked direction, use zone direction
        if not is_turn_movement and zone_state.is_locked():
            # Zone direction overrides - continue in locked direction regardless of current sensor validity
            zone_state.update_access_time()
            self.set_device_zone_state(device_id, zone_id, zone_state)
            
            movement_type = f"Moving {zone_state.active_direction.title()}"
            reason = f"Zone {zone_id} locked direction: {zone_state.active_direction} (set by {zone_state.turn_type} turn) - ignoring sensor pattern"
            
            self.logger.info(f"Device {device_id}: {reason}")
            return True, movement_type, reason
        
        # If raw movement is invalid and no zone override, reject
        if not is_valid_movement:
            self.logger.warning(f"Device {device_id} zone {zone_id}: {validation_reason}")
            return False, "Stationary", validation_reason
        
        if is_turn_movement:
            # Valid turn detected - this sets/updates the zone direction
            if raw_movement_type == "Turning Left":
                turn_direction = "left"
            elif raw_movement_type == "Turning Right":
                turn_direction = "right"
            else:
                turn_direction = "u_turn"
            compass_direction = self._turn_to_compass_direction(turn_direction, zone_state, robot_current_direction)
            
            # Lock this direction for the zone
            zone_state.lock_direction(compass_direction, turn_direction, device_id)
            self.set_device_zone_state(device_id, zone_id, zone_state)
            
            reason = (
                f"Zone {zone_id} direction locked to {compass_direction} ({turn_direction} turn)"
                if turn_direction in ("left", "right")
                else f"Zone {zone_id} direction locked to {compass_direction} (u-turn)"
            )
            self.logger.info(f"Device {device_id}: {reason}")
            
            return True, raw_movement_type, reason
        
        else:
            # Valid non-turn movement detected
            if not zone_state.is_locked():
                # If no zone direction is set, need to establish a direction from previous zone
                # For now, allow raw movement but don't lock direction yet
                zone_state.update_access_time()
                self.set_device_zone_state(device_id, zone_id, zone_state)
                
                reason = f"No zone direction set - allowing raw movement: {raw_movement_type}"
                self.logger.info(f"Device {device_id} zone {zone_id}: {reason}")
                return True, raw_movement_type, reason
            else:
                # Zone direction is locked - continue in that direction
                zone_state.update_access_time()
                self.set_device_zone_state(device_id, zone_id, zone_state)
                
                movement_type = f"Moving {zone_state.active_direction.title()}"
                reason = f"Zone {zone_id} continuing in locked direction: {zone_state.active_direction}"
                
                self.logger.info(f"Device {device_id}: {reason}")
                return True, movement_type, reason
    
    def _turn_to_compass_direction(self, turn_direction: str, current_zone_state: ZoneDirectionState, robot_current_direction: str = None) -> str:
        """
        Convert turn direction to compass direction based on current zone state or robot direction.
        
        Args:
            turn_direction: 'left', 'right', or 'u_turn'
            current_zone_state: Current state of the zone
            robot_current_direction: Robot's current facing direction (if available)
            
        Returns:
            Compass direction ('north', 'south', 'east', 'west')
        """
        # Priority 1: Use robot's current direction if provided
        if robot_current_direction:
            current_dir = robot_current_direction
 
        # Priority 2: If zone already has a direction, use that
        elif current_zone_state.is_locked():
            current_dir = current_zone_state.active_direction

        else:
            # Default initial directions for turns
            result = 'west' if turn_direction == 'left' else 'east'

            return result
        
        # Direction mapping for turns including U-turn
        if turn_direction == 'u_turn':
            u_map = {
                'north': 'south',
                'south': 'north',
                'east': 'west',
                'west': 'east'
            }
            result = u_map.get(current_dir, 'south')

            return result
        else:
            direction_map = {
                'north': {'left': 'west', 'right': 'east'},
                'south': {'left': 'east', 'right': 'west'},
                'east': {'left': 'north', 'right': 'south'},
                'west': {'left': 'south', 'right': 'north'}
            }
            new_direction = direction_map.get(current_dir, {}).get(turn_direction, 'north')

            return new_direction
    
    def get_device_zone_state(self, device_id: str, zone_id: int) -> ZoneDirectionState:
        """Get zone state for a specific device and zone"""
        if device_id not in self.device_zone_states:
            self.device_zone_states[device_id] = {}
        
        if zone_id not in self.device_zone_states[device_id]:
            self.device_zone_states[device_id][zone_id] = ZoneDirectionState(zone_id=zone_id)
        
        return self.device_zone_states[device_id][zone_id]
    
    def set_device_zone_state(self, device_id: str, zone_id: int, state: ZoneDirectionState):
        """Set zone state for a specific device and zone"""
        if device_id not in self.device_zone_states:
            self.device_zone_states[device_id] = {}
        
        self.device_zone_states[device_id][zone_id] = state
        self.save_states()
    
    def clear_zone_direction(self, device_id: str, zone_id: int):
        """Clear the direction lock for a specific zone"""
        zone_state = self.get_device_zone_state(device_id, zone_id)
        zone_state.clear_direction()
        self.set_device_zone_state(device_id, zone_id, zone_state)
        self.logger.info(f"Cleared direction for device {device_id} zone {zone_id}")
    
    def inherit_direction_from_previous_zone(self, device_id: str, current_zone_id: int, previous_zone_id: int):
        """
        Inherit direction from previous zone when no turn is detected.
        This implements the rule: "if the robot does not encounter any turn in the current zone,
        then its next zone direction will be same as its current zone direction."
        
        Args:
            device_id: Device identifier
            current_zone_id: Current zone number
            previous_zone_id: Previous zone number
        """
        current_zone_state = self.get_device_zone_state(device_id, current_zone_id)
        previous_zone_state = self.get_device_zone_state(device_id, previous_zone_id)
        
        # Only inherit if current zone doesn't have a direction and previous zone does
        if not current_zone_state.is_locked() and previous_zone_state.is_locked():
            # Inherit the direction from previous zone
            current_zone_state.lock_direction(
                previous_zone_state.active_direction,
                "inherited",  # Mark as inherited rather than turn-based
                device_id
            )
            self.set_device_zone_state(device_id, current_zone_id, current_zone_state)
            
            self.logger.info(f"Device {device_id}: Zone {current_zone_id} inherited direction {previous_zone_state.active_direction} from zone {previous_zone_id}")
            
            return previous_zone_state.active_direction
        
        return None
    
    def set_initial_zone_direction(self, device_id: str, zone_id: int, direction: str, source: str = "initial"):
        """
        Set initial direction for a zone (used when robot enters a new zone with a known direction).
        
        Args:
            device_id: Device identifier
            zone_id: Zone number
            direction: Direction to set ('north', 'south', 'east', 'west')
            source: Source of the direction (for logging)
        """
        zone_state = self.get_device_zone_state(device_id, zone_id)
        
        # Only set if zone doesn't already have a direction
        if not zone_state.is_locked():
            zone_state.lock_direction(direction, source, device_id)
            self.set_device_zone_state(device_id, zone_id, zone_state)
            
            self.logger.info(f"Device {device_id}: Zone {zone_id} initial direction set to {direction} (source: {source})")
    
    def get_zone_info(self, device_id: str, zone_id: int) -> Dict:
        """Get comprehensive zone information"""
        zone_state = self.get_device_zone_state(device_id, zone_id)
        
        return {
            'zone_id': zone_id,
            'is_locked': zone_state.is_locked(),
            'active_direction': zone_state.active_direction,
            'turn_type': zone_state.turn_type,
            'locked_at': zone_state.locked_at,
            'locked_by_device': zone_state.locked_by_device,
            'locked_duration': time.time() - zone_state.locked_at if zone_state.locked_at else None,
            'last_updated': zone_state.last_updated
        }
    
    def get_all_device_zones(self, device_id: str) -> Dict[int, Dict]:
        """Get all zone states for a device"""
        if device_id not in self.device_zone_states:
            return {}
        
        return {
            zone_id: self.get_zone_info(device_id, zone_id)
            for zone_id in self.device_zone_states[device_id].keys()
        }
    
    def load_states(self):
        """Load zone states from storage"""
        try:
            if self.storage_path.exists():
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                
                # Convert loaded data back to ZoneDirectionState objects
                for device_id, zones in data.get('device_zone_states', {}).items():
                    self.device_zone_states[device_id] = {}
                    for zone_id_str, zone_data in zones.items():
                        zone_id = int(zone_id_str)
                        self.device_zone_states[device_id][zone_id] = ZoneDirectionState(**zone_data)
                
                self.logger.info(f"Loaded zone states from {self.storage_path}")
            else:
                self.logger.info("No existing zone states file found")
                
        except Exception as e:
            self.logger.error(f"Error loading zone states: {e}")
            self.device_zone_states = {}
    
    def save_states(self):
        """Save zone states to storage"""
        try:
            # Convert ZoneDirectionState objects to dictionaries
            save_data = {
                'device_zone_states': {},
                'last_saved': time.time()
            }
            
            for device_id, zones in self.device_zone_states.items():
                save_data['device_zone_states'][device_id] = {}
                for zone_id, zone_state in zones.items():
                    save_data['device_zone_states'][device_id][str(zone_id)] = asdict(zone_state)
            
            with open(self.storage_path, 'w') as f:
                json.dump(save_data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Error saving zone states: {e}")
    
    def cleanup_old_states(self, max_age_hours: int = 24):
        """Clean up old zone states that haven't been accessed recently"""
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        for device_id in list(self.device_zone_states.keys()):
            zones_to_remove = []
            
            for zone_id, zone_state in self.device_zone_states[device_id].items():
                if zone_state.last_updated and zone_state.last_updated < cutoff_time:
                    zones_to_remove.append(zone_id)
            
            for zone_id in zones_to_remove:
                del self.device_zone_states[device_id][zone_id]
                self.logger.info(f"Cleaned up old zone state: device {device_id}, zone {zone_id}")
        
        if zones_to_remove:
            self.save_states()


# Convenience functions
def get_zone_manager() -> ZoneDirectionManager:
    """Get a global zone direction manager instance"""
    if not hasattr(get_zone_manager, '_instance'):
        get_zone_manager._instance = ZoneDirectionManager()
    return get_zone_manager._instance


def process_zone_movement(device_id: str, zone_id: int, 
                         right_drive: float, left_drive: float,
                         right_motor: float, left_motor: float,
                         robot_current_direction: str = None) -> Tuple[bool, str, str]:
    """Convenience function to process movement with zone logic"""
    manager = get_zone_manager()
    return manager.detect_and_process_movement(device_id, zone_id, right_drive, left_drive, right_motor, left_motor, robot_current_direction)


def get_ui_lock_status(device_id: str, zone_id: int) -> dict:
    """Get lock status specifically formatted for UI components"""
    manager = get_zone_manager()
    zone_info = manager.get_zone_info(device_id, zone_id)
    
    return {
        'is_direction_locked': zone_info['is_locked'],
        'locked_direction': zone_info['active_direction'],
        'lock_type': zone_info['turn_type'],
        'lock_duration': zone_info['locked_duration'],
        'should_show_locked_visual': zone_info['is_locked'],
        'lock_color_hint': 'orange' if zone_info['is_locked'] else 'green',
        'lock_description': f"Direction locked to {zone_info['active_direction']} by {zone_info['turn_type']}" if zone_info['is_locked'] else "Direction not locked"
    }


def unlock_zone_for_ui(device_id: str, zone_id: int) -> bool:
    """Unlock zone direction from UI - useful for manual override"""
    try:
        manager = get_zone_manager()
        manager.clear_zone_direction(device_id, zone_id)
        return True
    except Exception as e:
        print(f"Error unlocking zone {zone_id} for device {device_id}: {e}")
        return False


if __name__ == "__main__":
    # Example usage

    
    manager = ZoneDirectionManager()
    
    # Simulate turn detection
    device_id = "robot_001"
    zone_id = 2
    

    
    # Test 1: Initial right turn (should lock zone direction)

    allowed, movement, reason = manager.detect_and_process_movement(
        device_id, zone_id, 100, -100, 45.0, 45.0
    )

    
    # Test 2: Forward movement (should continue in locked direction)

    allowed, movement, reason = manager.detect_and_process_movement(
        device_id, zone_id, 500, 500, 1000.0, 1000.0
    )

    
    # Test 3: New left turn (should change zone direction)

    allowed, movement, reason = manager.detect_and_process_movement(
        device_id, zone_id, -100, 100, 45.0, 45.0
    )

    
    # Show zone info

    zone_info = manager.get_zone_info(device_id, zone_id)
    for key, value in zone_info.items():
        print(f"   {key}: {value}")
