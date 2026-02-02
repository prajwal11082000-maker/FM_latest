#!/usr/bin/env python3
"""
Zone Navigation Manager

This module implements the complete zone-based navigation system:
1. Turn Detection → Direction Locking → Zone Mapping → Robot Movement to Next Zone

Key Logic:
- When turn is detected and locked, robot must move to the connected zone in that direction
- Direction locking automatically maps to the linked zone (next zone in that direction)
- Robot follows only the locked direction until next turn

Movement Rules (UPDATED):
- Right Turn: right_drive(500-600), left_drive(-500 to -600), motors(45,45)
- Left Turn: right_drive(-500 to -600), left_drive(500-600), motors(45,45)
- U-Turn: motors(45,45) AND drives in either range:
    (right_drive 1000..1200, left_drive -1200..-1000) OR
    (right_drive -1200..-1000, left_drive 1000..1200)
  When detected, flip current direction 180° (east↔west, north↔south) and lock.
"""

import json
import os
import time
import logging
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class ZoneConnection:
    """Represents a connection between zones in a specific direction"""
    from_zone: str
    to_zone: str
    direction: str  # 'north', 'south', 'east', 'west'
    connection_id: int = None
    is_active: bool = True


@dataclass
class ZoneNavigationState:
    """Represents the navigation state for zone-based movement"""
    current_zone: str
    locked_direction: Optional[str] = None  # Direction robot must follow
    target_zone: Optional[str] = None  # Next zone robot must move to
    lock_timestamp: Optional[float] = None
    turn_type: Optional[str] = None  # 'left', 'right', 'u_turn'
    device_id: Optional[str] = None
    is_transitioning: bool = False  # Whether robot is moving to target zone
    # Turn de-duplication metadata
    last_turn_signature: Optional[str] = None
    last_turn_timestamp: Optional[float] = None
    last_turn_zone: Optional[str] = None


class ZoneNavigationManager:
    """
    Manages zone-based navigation with turn detection and automatic zone transitions.
    
    Core Logic:
    1. Detect valid turns (motor values = 45.0, 45.0)
    2. Calculate turn direction from current zone direction
    3. Lock direction and find connected zone in that direction
    4. Move robot to the target zone
    5. Maintain direction lock until next valid turn
    """
    
    def __init__(self, storage_path: str = 'data/zone_navigation.json', 
                 logger: Optional[logging.Logger] = None):
        """
        Initialize Zone Navigation Manager
        
        Args:
            storage_path: Path to store zone navigation states
            logger: Optional logger instance
        """
        self.storage_path = Path(storage_path)
        self.logger = logger or logging.getLogger(__name__)
        
        # Zone connections: {zone_name: [ZoneConnection, ...]}
        self.zone_connections: Dict[str, List[ZoneConnection]] = {}
        
        # Device navigation states: {device_id: ZoneNavigationState}
        self.device_states: Dict[str, ZoneNavigationState] = {}
        
        # Direction mappings for turns (CRITICAL: north + right = east)
        self.direction_mappings = {
            'north': {'left': 'west', 'right': 'east'},    # north + right = east (YOUR CASE)
            'south': {'left': 'east', 'right': 'west'},
            'east': {'left': 'north', 'right': 'south'},
            'west': {'left': 'south', 'right': 'north'}
        }

        # U-turn mapping (flip 180°)
        self.u_turn_map = {
            'north': 'south',
            'south': 'north',
            'east': 'west',
            'west': 'east'
        }
        # Duplicate detection window (seconds). Prevents repeated flip-flop on the same row.
        self.u_turn_duplicate_window = 2.0
        self.turn_duplicate_window = 2.0
        
        # Ensure storage directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing states and connections
        self.load_navigation_data()
        
        self.logger.info("ZoneNavigationManager initialized")
    
    def process_movement_and_navigate(self, device_id: str, current_zone: str,
                                    right_drive: float, left_drive: float,
                                    right_motor: float, left_motor: float,
                                    current_direction: str = None) -> Tuple[bool, str, str, Optional[str]]:
        """
        Process movement input and handle zone navigation.
        
        Movement Rules:
        - Right Turn: right_drive(500-600), left_drive(-500 to -600), motors(45,45)
        - Left Turn: right_drive(-500 to -600), left_drive(500-600), motors(45,45)
        
        Args:
            device_id: Device identifier
            current_zone: Current zone name
            right_drive: Right drive value
            left_drive: Left drive value  
            right_motor: Right motor value
            left_motor: Left motor value
            current_direction: Current robot direction (optional)
            
        Returns:
            Tuple of (movement_allowed, movement_type, reason, target_zone)
        """
        from .turn_validator import TurnValidator
        
        # Get or create device state
        device_state = self.get_device_state(device_id, current_zone, current_direction)
        
        # Validate movement using turn validator
        validator = TurnValidator()
        is_valid, movement_type, validation_reason = validator.validate_movement_condition(
            right_drive, left_drive, right_motor, left_motor
        )
        
        # Process based on movement type
        if not is_valid:
            self.logger.warning(f"Device {device_id}: {validation_reason}")
            return False, "Stationary", validation_reason, None
        
        # Prepare a signature for de-duplication of turn events
        turn_signature = None
        if movement_type in ["Turning Right", "Turning Left", "U-Turn"]:
            turn_signature = (
                f"T:{movement_type}|Z:{current_zone}|RD:{right_drive}|LD:{left_drive}|RM:{right_motor}|LM:{left_motor}"
            )

        # Handle turn movements
        if movement_type in ["Turning Right", "Turning Left"]:
            return self._handle_turn_movement(
                device_id, device_state, movement_type, current_direction, turn_signature
            )
        elif movement_type == "U-Turn":
            return self._handle_u_turn_movement(
                device_id, device_state, current_direction, turn_signature
            )
        
        # Handle straight movements (when direction is locked)
        elif movement_type in ["Forward", "Backward"]:
            return self._handle_straight_movement(
                device_id, device_state, movement_type
            )
        
        # Handle stationary
        else:
            return True, movement_type, "Robot is stationary", device_state.current_zone
    
    def _handle_turn_movement(self, device_id: str, device_state: ZoneNavigationState,
                             movement_type: str, current_direction: str,
                             turn_signature: Optional[str] = None) -> Tuple[bool, str, str, Optional[str]]:
        """Handle turn movement and zone navigation logic"""
        
        turn_direction = "left" if movement_type == "Turning Left" else "right"

        # Signature-based duplicate guard (strong): prevent re-processing exact same turn row
        if turn_signature and device_state.last_turn_signature == turn_signature:
            # Ensure target zone and transition state are intact
            if not device_state.target_zone and device_state.locked_direction:
                device_state.target_zone = self._find_connected_zone(
                    device_state.current_zone, device_state.locked_direction
                )
            device_state.is_transitioning = bool(device_state.target_zone)
            self.device_states[device_id] = device_state
            self.save_navigation_data()
            reason = (
                f"Duplicate {movement_type} signature; preserving locked direction {device_state.locked_direction}."
            )
            self.logger.info(f"Device {device_id}: {reason}")
            movement_desc = (
                f"Moving {device_state.locked_direction.title()}" if device_state.target_zone else "Stationary"
            )
            return True, movement_desc, reason, device_state.target_zone
        
        # Duplicate left/right turn guard (time-window): only block if the same turn type
        # occurs in the SAME zone within a short window (likely the same CSV row reprocessed)
        if (device_state.turn_type == turn_direction and
            device_state.lock_timestamp and
            device_state.last_turn_zone == device_state.current_zone):
            if (time.time() - device_state.lock_timestamp) < self.turn_duplicate_window:
                # Ensure target_zone exists if missing
                if not device_state.target_zone and device_state.locked_direction:
                    device_state.target_zone = self._find_connected_zone(
                        device_state.current_zone, device_state.locked_direction
                    )
                device_state.is_transitioning = bool(device_state.target_zone)
                self.device_states[device_id] = device_state
                self.save_navigation_data()
                reason = (
                    f"Duplicate {movement_type} within {self.turn_duplicate_window:.1f}s; "
                    f"preserving locked direction {device_state.locked_direction}."
                )
                self.logger.info(f"Device {device_id}: {reason}")
                movement_desc = (
                    f"Moving {device_state.locked_direction.title()}" if device_state.target_zone else "Stationary"
                )
                return True, movement_desc, reason, device_state.target_zone
        
        # Calculate new direction after turn - PRIORITY: Use locked direction first (robust post U-turn), then current_direction
        base_used = None
        if device_state.locked_direction:
            base_used = device_state.locked_direction
            new_direction = self.direction_mappings.get(base_used, {}).get(turn_direction)

        elif current_direction:
            base_used = current_direction.lower()
            # Use current robot direction for calculation
            new_direction = self.direction_mappings.get(base_used, {}).get(turn_direction)

        else:
            # Default directions for first turn
            new_direction = 'west' if turn_direction == 'left' else 'east'
        
        if not new_direction:
            # Fallback calculation if mapping failed
            new_direction = 'east' if turn_direction == 'right' else 'west'
        
        # Find target zone in the new direction
        target_zone = self._find_connected_zone(device_state.current_zone, new_direction)

        # Fallback: if no target via locked-direction base, try using provided current_direction baseline
        if not target_zone and current_direction and (base_used != current_direction.lower()):
            alt_base = current_direction.lower()
            alt_dir = self.direction_mappings.get(alt_base, {}).get(turn_direction)
            if alt_dir:
                alt_target = self._find_connected_zone(device_state.current_zone, alt_dir)
                if alt_target:
                    new_direction = alt_dir
                    target_zone = alt_target
                    base_used = alt_base

        if not target_zone:
            # Final fallback: enumerate all possible results for this turn and pick a valid connection
            # Build ordered candidate directions: [current mapping, alt mapping, other possibilities]
            candidate_dirs = []
            seen = set()
            def _push(d):
                if d and d not in seen:
                    candidate_dirs.append(d)
                    seen.add(d)

            _push(new_direction)
            # Include alt_dir if computed above
            try:
                alt_dir  # type: ignore
            except NameError:
                alt_dir = None
            _push(alt_dir)
            # Add remaining possible results for given turn from all bases
            for base in ['north','south','east','west']:
                poss = self.direction_mappings.get(base, {}).get(turn_direction)
                _push(poss)

            preferred_choice = None
            fallback_choice = None
            for cand in candidate_dirs:
                tz = self._find_connected_zone(device_state.current_zone, cand)
                if tz:
                    # Prefer not to go back to last_turn_zone immediately
                    if device_state.last_turn_zone and tz == device_state.last_turn_zone:
                        if not fallback_choice:
                            fallback_choice = (cand, tz)
                    else:
                        preferred_choice = (cand, tz)
                        break
            if preferred_choice:
                new_direction, target_zone = preferred_choice
            elif fallback_choice:
                new_direction, target_zone = fallback_choice

        if not target_zone:
            return False, movement_type, f"No zone connected in direction {new_direction} from {device_state.current_zone}", None
        
        # Lock direction and set target zone
        device_state.locked_direction = new_direction
        device_state.target_zone = target_zone
        device_state.turn_type = turn_direction
        device_state.lock_timestamp = time.time()
        device_state.is_transitioning = True
        device_state.last_turn_signature = turn_signature
        device_state.last_turn_timestamp = time.time()
        device_state.last_turn_zone = device_state.current_zone
        
        # Update device state
        self.device_states[device_id] = device_state
        self.save_navigation_data()
        
        reason = f"Turn detected: {movement_type} from {base_used or current_direction or device_state.locked_direction or 'unknown'}. Direction locked to {new_direction}. Moving to zone {target_zone}."
        self.logger.info(f"Device {device_id}: {reason}")
        
        return True, movement_type, reason, target_zone

    def _handle_u_turn_movement(self, device_id: str, device_state: ZoneNavigationState,
                                current_direction: Optional[str],
                                turn_signature: Optional[str] = None) -> Tuple[bool, str, str, Optional[str]]:
        """Handle U-turn movement: flip facing direction 180° and lock it.

        Priorities for determining base direction to flip:
        1. Use device_state.locked_direction if present (most reliable after prior turns)
        2. Else use robot's current_direction if provided
        3. Else default to 'north' and flip to 'south'
        """
        # Signature-based duplicate guard (strong) for U-Turn
        if turn_signature and device_state.last_turn_signature == turn_signature:
            if not device_state.target_zone and device_state.locked_direction:
                device_state.target_zone = self._find_connected_zone(device_state.current_zone, device_state.locked_direction)
            device_state.is_transitioning = bool(device_state.target_zone)
            self.device_states[device_id] = device_state
            self.save_navigation_data()
            reason = (f"Duplicate U-Turn signature; preserving locked direction {device_state.locked_direction}.")
            self.logger.info(f"Device {device_id}: {reason}")
            movement_desc = (
                f"Moving {device_state.locked_direction.title()}" if device_state.target_zone else "Stationary"
            )
            return True, movement_desc, reason, device_state.target_zone

        # Duplicate U-turn guard (time-window): only block if SAME zone within window
        if (device_state.turn_type == 'u_turn' and device_state.lock_timestamp and
            device_state.last_turn_zone == device_state.current_zone):
            if (time.time() - device_state.lock_timestamp) < self.u_turn_duplicate_window:
                # Ensure target_zone exists (may have been missing previously)
                if not device_state.target_zone and device_state.locked_direction:
                    device_state.target_zone = self._find_connected_zone(device_state.current_zone, device_state.locked_direction)
                device_state.is_transitioning = bool(device_state.target_zone)
                self.device_states[device_id] = device_state
                self.save_navigation_data()
                reason = (f"Duplicate U-Turn within {self.u_turn_duplicate_window:.1f}s; "
                          f"preserving locked direction {device_state.locked_direction}.")
                self.logger.info(f"Device {device_id}: {reason}")
                movement_desc = (
                    f"Moving {device_state.locked_direction.title()}" if device_state.target_zone else "Stationary"
                )
                return True, movement_desc, reason, device_state.target_zone

        # Determine base direction to flip (prefer last locked direction for robustness)
        base_dir = (device_state.locked_direction or None)
        if not base_dir:
            base_dir = (current_direction.lower() if current_direction else None)
        if not base_dir:
            base_dir = 'north'
        prev_dir = base_dir
        new_direction = self.u_turn_map.get(base_dir, 'south')

        # Find target zone in the new (flipped) direction if available
        target_zone = self._find_connected_zone(device_state.current_zone, new_direction)

        # Lock new direction and set target
        device_state.locked_direction = new_direction
        device_state.target_zone = target_zone
        device_state.turn_type = 'u_turn'
        device_state.lock_timestamp = time.time()
        device_state.is_transitioning = bool(target_zone)
        device_state.last_turn_signature = turn_signature
        device_state.last_turn_timestamp = time.time()
        device_state.last_turn_zone = device_state.current_zone

        # Persist
        self.device_states[device_id] = device_state
        self.save_navigation_data()

        if target_zone:
            reason = (f"Turn detected: U-Turn {prev_dir} -> {new_direction}. "
                      f"Direction locked to {new_direction}. Moving to zone {target_zone}.")
        else:
            reason = (f"Turn detected: U-Turn {prev_dir} -> {new_direction}. "
                      f"Direction locked to {new_direction}. No connected zone in that direction from {device_state.current_zone}.")

        self.logger.info(f"Device {device_id}: {reason}")
        return True, "U-Turn", reason, target_zone
    
    def _handle_straight_movement(self, device_id: str, device_state: ZoneNavigationState,
                                 movement_type: str) -> Tuple[bool, str, str, Optional[str]]:
        """Handle straight movement in locked direction"""
        
        if not device_state.locked_direction:
            # No locked direction - allow normal movement
            return True, movement_type, f"{movement_type} movement allowed (no direction lock)", device_state.current_zone
        
        if not device_state.target_zone:
            # Direction locked but no target zone - find it
            target_zone = self._find_connected_zone(device_state.current_zone, device_state.locked_direction)
            if target_zone:
                device_state.target_zone = target_zone
                device_state.is_transitioning = True
                self.device_states[device_id] = device_state
        
        # Move towards target zone in locked direction
        movement_description = f"Moving {device_state.locked_direction.title()}"
        reason = f"{movement_description} towards zone {device_state.target_zone} (direction locked by {device_state.turn_type} turn)"
        
        self.logger.info(f"Device {device_id}: {reason}")
        
        return True, movement_description, reason, device_state.target_zone
    
    def _find_connected_zone(self, from_zone: str, direction: str) -> Optional[str]:
        """Find the zone connected in the specified direction"""
        
        if from_zone not in self.zone_connections:
            self.logger.warning(f"No connections found for zone {from_zone}")
            return None
        
        # Look for connection in the specified direction
        for connection in self.zone_connections[from_zone]:
            if connection.direction.lower() == direction.lower() and connection.is_active:
                self.logger.info(f"Found connection: {from_zone} -> {connection.to_zone} (direction: {direction})")
                return connection.to_zone
        
        self.logger.warning(f"No connection found from {from_zone} in direction {direction}")
        return None
    
    def get_device_state(self, device_id: str, current_zone: str, current_direction: str = None) -> ZoneNavigationState:
        """Get or create device navigation state"""
        
        if device_id not in self.device_states:
            # Create new state - start with NO locked direction to allow proper initialization
            self.device_states[device_id] = ZoneNavigationState(
                current_zone=current_zone,
                device_id=device_id
            )
           
        else:
            # Update current zone if changed
            state = self.device_states[device_id]
            if state.current_zone != current_zone:
                self.logger.info(f"Device {device_id} moved from zone {state.current_zone} to {current_zone}")
                state.current_zone = current_zone
                # Clear transition state when zone changes
                if state.target_zone == current_zone:
                    state.is_transitioning = False

        
        return self.device_states[device_id]
    
    def set_initial_direction(self, device_id: str, current_zone: str, direction: str) -> None:
        state = self.get_device_state(device_id, current_zone, None)
        dir_lower = (direction or '').lower()
        if dir_lower not in ['north', 'south', 'east', 'west']:
            dir_lower = 'north'
        state.locked_direction = dir_lower
        state.lock_timestamp = time.time()
        state.is_transitioning = False
        self.device_states[device_id] = state
        self.save_navigation_data()

    def add_zone_connection(self, from_zone: str, to_zone: str, direction: str, connection_id: int = None):
        """Add a connection between zones"""
        
        if from_zone not in self.zone_connections:
            self.zone_connections[from_zone] = []
        
        connection = ZoneConnection(
            from_zone=from_zone,
            to_zone=to_zone,
            direction=direction.lower(),
            connection_id=connection_id
        )
        
        self.zone_connections[from_zone].append(connection)
        self.logger.info(f"Added zone connection: {from_zone} -> {to_zone} (direction: {direction})")
        
        self.save_navigation_data()
    
    def load_zone_connections_from_csv_data(self, zones_data: List[Dict]):
        """Load zone connections from CSV zone data"""
        
        self.zone_connections.clear()
        
        for zone in zones_data:
            from_zone = zone.get('from_zone')
            to_zone = zone.get('to_zone')
            direction = zone.get('direction')
            connection_id = zone.get('id')
            
            if from_zone and to_zone and direction:
                self.add_zone_connection(from_zone, to_zone, direction, connection_id)
        
        self.logger.info(f"Loaded {len(self.zone_connections)} zone connections from CSV data")
    
    def clear_device_direction_lock(self, device_id: str):
        """Clear direction lock for a device"""
        
        if device_id in self.device_states:
            state = self.device_states[device_id]
            state.locked_direction = None
            state.target_zone = None
            state.turn_type = None
            state.lock_timestamp = None
            state.is_transitioning = False
            
            self.save_navigation_data()
            self.logger.info(f"Cleared direction lock for device {device_id}")

    
    def reset_device_state(self, device_id: str):
        """Completely reset device state - useful for testing"""
        if device_id in self.device_states:
            del self.device_states[device_id]
            self.save_navigation_data()

    
    def get_navigation_info(self, device_id: str) -> Dict:
        """Get comprehensive navigation information for a device"""
        
        if device_id not in self.device_states:
            return {
                'device_id': device_id,
                'current_zone': None,
                'is_locked': False,
                'locked_direction': None,
                'target_zone': None,
                'is_transitioning': False
            }
        
        state = self.device_states[device_id]
        
        return {
            'device_id': device_id,
            'current_zone': state.current_zone,
            'is_locked': bool(state.locked_direction),
            'locked_direction': state.locked_direction,
            'target_zone': state.target_zone,
            'turn_type': state.turn_type,
            'is_transitioning': state.is_transitioning,
            'lock_timestamp': state.lock_timestamp,
            'lock_duration': time.time() - state.lock_timestamp if state.lock_timestamp else None
        }
    
    def get_available_directions(self, zone: str) -> List[str]:
        """Get all available directions from a zone"""
        
        if zone not in self.zone_connections:
            return []
        
        return [conn.direction for conn in self.zone_connections[zone] if conn.is_active]
    
    def get_zone_map(self) -> Dict[str, List[Dict]]:
        """Get the complete zone connection map"""
        
        zone_map = {}
        for from_zone, connections in self.zone_connections.items():
            zone_map[from_zone] = [
                {
                    'to_zone': conn.to_zone,
                    'direction': conn.direction,
                    'connection_id': conn.connection_id,
                    'is_active': conn.is_active
                }
                for conn in connections
            ]
        
        return zone_map
    
    def save_navigation_data(self):
        """Save navigation data to storage"""
        
        try:
            save_data = {
                'zone_connections': {},
                'device_states': {},
                'last_saved': time.time()
            }
            
            # Save zone connections
            for from_zone, connections in self.zone_connections.items():
                save_data['zone_connections'][from_zone] = [
                    asdict(conn) for conn in connections
                ]
            
            # Save device states
            for device_id, state in self.device_states.items():
                save_data['device_states'][device_id] = asdict(state)
            
            with open(self.storage_path, 'w') as f:
                json.dump(save_data, f, indent=2)
                
            self.logger.info(f"Saved navigation data to {self.storage_path}")
                
        except Exception as e:
            self.logger.error(f"Error saving navigation data: {e}")
    
    def load_navigation_data(self):
        """Load navigation data from storage"""
        
        try:
            if self.storage_path.exists():
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                
                # Load zone connections
                self.zone_connections.clear()
                for from_zone, connections in data.get('zone_connections', {}).items():
                    self.zone_connections[from_zone] = [
                        ZoneConnection(**conn_data) for conn_data in connections
                    ]
                
                # Load device states
                self.device_states.clear()
                for device_id, state_data in data.get('device_states', {}).items():
                    self.device_states[device_id] = ZoneNavigationState(**state_data)
                
                self.logger.info(f"Loaded navigation data from {self.storage_path}")
            else:
                self.logger.info("No existing navigation data file found")
                
        except Exception as e:
            self.logger.error(f"Error loading navigation data: {e}")
            self.zone_connections = {}
            self.device_states = {}


# Convenience functions
_zone_nav_manager = None

def get_zone_navigation_manager(reset_for_testing: bool = False) -> ZoneNavigationManager:
    """Get a global zone navigation manager instance"""
    global _zone_nav_manager
    if _zone_nav_manager is None or reset_for_testing:
        _zone_nav_manager = ZoneNavigationManager()
        if reset_for_testing:
            print(f"DEBUG - 🔄 RESET zone navigation manager for testing")
    return _zone_nav_manager


def process_movement_with_zone_navigation(device_id: str, current_zone: str,
                                        right_drive: float, left_drive: float,
                                        right_motor: float, left_motor: float,
                                        current_direction: str = None) -> Tuple[bool, str, str, Optional[str]]:
    """Convenience function to process movement with zone navigation logic"""
    manager = get_zone_navigation_manager()
    return manager.process_movement_and_navigate(
        device_id, current_zone, right_drive, left_drive, right_motor, left_motor, current_direction
    )


if __name__ == "__main__":
    # Example usage

    manager = ZoneNavigationManager()
    
    # Add some example zone connections
    manager.add_zone_connection('A', 'B', 'north')
    manager.add_zone_connection('A', 'C', 'east')
    manager.add_zone_connection('A', 'D', 'south')
    manager.add_zone_connection('A', 'E', 'west')
    
    device_id = "robot_001"
    current_zone = "A"
    

    
    # Test right turn (should move east to zone C)

    allowed, movement, reason, target = manager.process_movement_and_navigate(
        device_id, current_zone, 550.0, -550.0, 45.0, 45.0, 'north'
    )

    
    # Get navigation info
    nav_info = manager.get_navigation_info(device_id)

