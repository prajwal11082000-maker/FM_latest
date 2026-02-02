#!/usr/bin/env python3
"""
Zone Navigator

Implements the core navigation algorithm that determines the robot's next zone
based on sensor values and turning rules.
"""

import time
import logging
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass

from .navigation_enums import (
    Direction, TurnAction, NavigationStatus, NavigationConstants, SensorData
)
from .robot_state import RobotState, Position


@dataclass
class NavigationDecision:
    """Represents a navigation decision made by the zone navigator"""
    action: TurnAction
    next_direction: Direction
    next_zone_position: Position
    confidence: float
    reason: str
    sensor_data: SensorData
    timestamp: float


class ZoneNavigator:
    """
    Core navigation logic that determines robot movement based on sensor inputs
    and implements the zone-based navigation rules.
    """
    
    def __init__(self, robot_state: RobotState, logger: Optional[logging.Logger] = None):
        """
        Initialize Zone Navigator
        
        Args:
            robot_state: Current robot state manager
            logger: Optional logger for debug information
        """
        self.robot_state = robot_state
        self.logger = logger or logging.getLogger(__name__)
        
        # Navigation decision history
        self.decision_history = []
        self.max_history = 50
        
        # Sensor validation settings
        self.sensor_tolerance = 5.0  # Tolerance for sensor value matching
        self.min_confidence_threshold = 0.7
        
        self.logger.info("ZoneNavigator initialized")
    
    def analyze_sensor_data(self, sensor_data: SensorData) -> NavigationDecision:
        """
        Analyze sensor data and determine the next navigation action
        
        Args:
            sensor_data: Current sensor readings
            
        Returns:
            NavigationDecision object with the recommended action
        """
        self.logger.debug(f"Analyzing sensor data: {sensor_data}")
        
        # Check for U-turn condition first (unique motor signature 180/180)
        if self._is_u_turn_condition(sensor_data):
            return self._create_u_turn_decision(sensor_data)
        
        # Check for right turn condition
        if self._is_right_turn_condition(sensor_data):
            return self._create_right_turn_decision(sensor_data)
        
        # Check for left turn condition  
        elif self._is_left_turn_condition(sensor_data):
            return self._create_left_turn_decision(sensor_data)
        
        # Default: continue straight
        else:
            return self._create_straight_decision(sensor_data)

    def _is_u_turn_condition(self, sensor_data: SensorData) -> bool:
        """
        Check if sensor data matches U-turn conditions (updated)
        
        CRITICAL U-TURN CONDITION (UPDATED):
        - right_motor: EXACTLY 45.0 (no tolerance)
        - left_motor:  EXACTLY 45.0 (no tolerance)
        - right_drive/left_drive: high-magnitude, opposite-signed ranges in either order:
            • (right_drive 1000..1200, left_drive -1200..-1000)
            • (right_drive -1200..-1000, left_drive 1000..1200)
        - current_location: matches robot's current zone (safety)
        """
        # Motors must be exactly the updated U-turn motor value
        motor_value = NavigationConstants.U_TURN_MOTOR_VALUE
        right_motor_ok = sensor_data.right_motor == motor_value
        left_motor_ok = sensor_data.left_motor == motor_value

        # Drives must match one of the allowed opposite-signed high ranges
        drive_pattern_ok = False
        for rng in NavigationConstants.U_TURN_DRIVE_RANGES:
            rd_min, rd_max = rng['right_drive']
            ld_min, ld_max = rng['left_drive']
            if rd_min <= sensor_data.right_drive <= rd_max and ld_min <= sensor_data.left_drive <= ld_max:
                drive_pattern_ok = True
                break

        # Location must match
        location_ok = sensor_data.current_location == self.robot_state.current_position.zone

        result = right_motor_ok and left_motor_ok and drive_pattern_ok and location_ok

        if result:
            self.logger.info(f"U-turn condition detected: {sensor_data}")
        else:
            if location_ok and (not right_motor_ok or not left_motor_ok):
                self.logger.debug(
                    f"U-turn not detected - motor values must be exactly {motor_value}: "
                    f"right_motor={sensor_data.right_motor}, left_motor={sensor_data.left_motor}"
                )
            elif location_ok and not drive_pattern_ok:
                self.logger.debug(
                    f"U-turn not detected - drive values must match high-magnitude opposite-signed ranges: "
                    f"right_drive={sensor_data.right_drive}, left_drive={sensor_data.left_drive}"
                )
        return result
    
    def _is_right_turn_condition(self, sensor_data: SensorData) -> bool:
        """
        Check if sensor data matches right turn conditions
        
        CRITICAL RIGHT TURN CONDITION:
        - right_drive: between 500 to 600
        - left_drive: between -600 to -500  
        - right_motor: EXACTLY 45.0 (no tolerance)
        - left_motor: EXACTLY 45.0 (no tolerance)
        - current_location: matches expected zone
        
        The robot will NOT turn unless both motor values are exactly 45.
        """
        ranges = NavigationConstants.RIGHT_TURN_RANGES
        
        # Check right_drive range
        right_drive_ok = (ranges['right_drive'][0] <= sensor_data.right_drive <= 
                         ranges['right_drive'][1])
        
        # Check left_drive range  
        left_drive_ok = (ranges['left_drive'][0] <= sensor_data.left_drive <= 
                        ranges['left_drive'][1])
        
        # Check motor values (EXACT match required - no tolerance for turns)
        right_motor_ok = sensor_data.right_motor == ranges['right_motor']
        left_motor_ok = sensor_data.left_motor == ranges['left_motor']
        
        # Check current location matches robot's zone
        location_ok = sensor_data.current_location == self.robot_state.current_position.zone
        
        result = right_drive_ok and left_drive_ok and right_motor_ok and left_motor_ok and location_ok
        
        if result:
            self.logger.info(f"Right turn condition detected: {sensor_data}")
        else:
            # Log why the turn was rejected if motor values are not exactly 45
            if right_drive_ok and left_drive_ok and location_ok and (not right_motor_ok or not left_motor_ok):
                self.logger.warning(
                    f"Right turn REJECTED - Motor values not exactly 45.0: "
                    f"right_motor={sensor_data.right_motor}, left_motor={sensor_data.left_motor} "
                    f"(required: both exactly 45.0)"
                )
        
        return result
    
    def _is_left_turn_condition(self, sensor_data: SensorData) -> bool:
        """
        Check if sensor data matches left turn conditions
        
        CRITICAL LEFT TURN CONDITION:
        - right_drive: between -600 to -500
        - left_drive: between 500 to 600
        - right_motor: EXACTLY 45.0 (no tolerance)
        - left_motor: EXACTLY 45.0 (no tolerance)
        - current_location: matches expected zone
        
        The robot will NOT turn unless both motor values are exactly 45.
        """
        ranges = NavigationConstants.LEFT_TURN_RANGES
        
        # Check right_drive range
        right_drive_ok = (ranges['right_drive'][0] <= sensor_data.right_drive <= 
                         ranges['right_drive'][1])
        
        # Check left_drive range
        left_drive_ok = (ranges['left_drive'][0] <= sensor_data.left_drive <= 
                        ranges['left_drive'][1])
        
        # Check motor values (EXACT match required - no tolerance for turns)
        right_motor_ok = sensor_data.right_motor == ranges['right_motor']
        left_motor_ok = sensor_data.left_motor == ranges['left_motor']
        
        # Check current location matches robot's zone
        location_ok = sensor_data.current_location == self.robot_state.current_position.zone
        
        result = right_drive_ok and left_drive_ok and right_motor_ok and left_motor_ok and location_ok
        
        if result:
            self.logger.info(f"Left turn condition detected: {sensor_data}")
        else:
            # Log why the turn was rejected if motor values are not exactly 45
            if right_drive_ok and left_drive_ok and location_ok and (not right_motor_ok or not left_motor_ok):
                self.logger.warning(
                    f"Left turn REJECTED - Motor values not exactly 45.0: "
                    f"right_motor={sensor_data.right_motor}, left_motor={sensor_data.left_motor} "
                    f"(required: both exactly 45.0)"
                )
        
        return result
    
    def _create_right_turn_decision(self, sensor_data: SensorData) -> NavigationDecision:
        """Create a navigation decision for right turn"""
        current_direction = self.robot_state.current_direction
        next_direction = NavigationConstants.RIGHT_TURN_MAP[current_direction]
        next_position = self.robot_state.get_next_zone_position(next_direction)
        
        decision = NavigationDecision(
            action=TurnAction.RIGHT,
            next_direction=next_direction,
            next_zone_position=next_position,
            confidence=0.9,  # High confidence for exact sensor match
            reason=f"Right turn: {current_direction} -> {next_direction}",
            sensor_data=sensor_data,
            timestamp=time.time()
        )
        
        self._add_decision_to_history(decision)
        return decision

    def _create_u_turn_decision(self, sensor_data: SensorData) -> NavigationDecision:
        """Create a navigation decision for U-turn (180° flip)"""
        current_direction = self.robot_state.current_direction
        next_direction = NavigationConstants.U_TURN_MAP[current_direction]
        next_position = self.robot_state.get_next_zone_position(next_direction)

        decision = NavigationDecision(
            action=TurnAction.UTURN,
            next_direction=next_direction,
            next_zone_position=next_position,
            confidence=0.95,  # High confidence for exact motor match
            reason=f"U-turn: {current_direction} -> {next_direction}",
            sensor_data=sensor_data,
            timestamp=time.time()
        )

        self._add_decision_to_history(decision)
        return decision
    
    def _create_left_turn_decision(self, sensor_data: SensorData) -> NavigationDecision:
        """Create a navigation decision for left turn"""
        current_direction = self.robot_state.current_direction
        next_direction = NavigationConstants.LEFT_TURN_MAP[current_direction]
        next_position = self.robot_state.get_next_zone_position(next_direction)
        
        decision = NavigationDecision(
            action=TurnAction.LEFT,
            next_direction=next_direction,
            next_zone_position=next_position,
            confidence=0.9,  # High confidence for exact sensor match
            reason=f"Left turn: {current_direction} -> {next_direction}",
            sensor_data=sensor_data,
            timestamp=time.time()
        )
        
        self._add_decision_to_history(decision)
        return decision
    
    def _create_straight_decision(self, sensor_data: SensorData) -> NavigationDecision:
        """Create a navigation decision for straight movement"""
        current_direction = self.robot_state.current_direction
        next_position = self.robot_state.get_next_zone_position(current_direction)
        
        decision = NavigationDecision(
            action=TurnAction.STRAIGHT,
            next_direction=current_direction,  # Same direction
            next_zone_position=next_position,
            confidence=0.8,  # Default confidence for straight movement
            reason=f"Continue straight in {current_direction} direction",
            sensor_data=sensor_data,
            timestamp=time.time()
        )
        
        self._add_decision_to_history(decision)
        return decision
    
    def _add_decision_to_history(self, decision: NavigationDecision):
        """Add decision to navigation history"""
        self.decision_history.append(decision)
        
        # Maintain history limit
        if len(self.decision_history) > self.max_history:
            self.decision_history.pop(0)
    
    def execute_navigation_decision(self, decision: NavigationDecision) -> bool:
        """
        Execute a navigation decision by updating robot state
        
        Args:
            decision: Navigation decision to execute
            
        Returns:
            True if execution was successful, False otherwise
        """
        try:
            self.logger.info(f"Executing navigation decision: {decision.reason}")
            
            # Update robot direction
            if decision.next_direction != self.robot_state.current_direction:
                success = self.robot_state.update_direction(
                    decision.next_direction, 
                    f"turn_{decision.action.value}"
                )
                if not success:
                    self.logger.warning("Failed to update robot direction")
                    return False
            
            # Update robot position to next zone
            success = self.robot_state.update_position(
                decision.next_zone_position.coordinates,
                f"navigate_{decision.action.value}"
            )
            
            if success:
                self.logger.info(
                    f"Navigation successful: Now at {decision.next_zone_position} "
                    f"facing {decision.next_direction}"
                )
            else:
                self.logger.warning("Failed to update robot position")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error executing navigation decision: {e}")
            return False
    
    def navigate_with_sensor_data(self, sensor_data: SensorData) -> NavigationDecision:
        """
        Complete navigation process: analyze sensor data and execute decision
        
        Args:
            sensor_data: Current sensor readings
            
        Returns:
            NavigationDecision that was made and executed
        """
        # Analyze sensor data
        decision = self.analyze_sensor_data(sensor_data)
        
        # Execute the decision if confidence is high enough
        if decision.confidence >= self.min_confidence_threshold:
            execution_success = self.execute_navigation_decision(decision)
            
            if execution_success:
                self.robot_state.set_status(NavigationStatus.NAVIGATING)
            else:
                self.robot_state.set_status(NavigationStatus.ERROR)
                decision.confidence = 0.0  # Mark as failed
        else:
            self.logger.warning(f"Navigation decision confidence too low: {decision.confidence}")
            self.robot_state.set_status(NavigationStatus.ERROR)
        
        return decision
    
    def get_navigation_summary(self) -> Dict[str, Any]:
        """
        Get a summary of recent navigation decisions and current state
        
        Returns:
            Dictionary with navigation summary information
        """
        recent_decisions = self.decision_history[-10:] if self.decision_history else []
        
        return {
            'current_state': self.robot_state.get_state_summary(),
            'total_decisions': len(self.decision_history),
            'recent_decisions': [
                {
                    'action': d.action.value,
                    'direction': d.next_direction.value,
                    'confidence': d.confidence,
                    'reason': d.reason,
                    'timestamp': d.timestamp
                }
                for d in recent_decisions
            ],
            'navigation_stats': self._get_navigation_stats()
        }
    
    def _get_navigation_stats(self) -> Dict[str, Any]:
        """Get statistics about navigation decisions"""
        if not self.decision_history:
            return {'total': 0}
        
        actions = [d.action for d in self.decision_history]
        directions = [d.next_direction for d in self.decision_history]
        
        stats = {
            'total': len(self.decision_history),
            'action_counts': {
                'left': actions.count(TurnAction.LEFT),
                'right': actions.count(TurnAction.RIGHT),
                'straight': actions.count(TurnAction.STRAIGHT),
                'u_turn': actions.count(TurnAction.UTURN)
            },
            'direction_counts': {
                'north': directions.count(Direction.NORTH),
                'south': directions.count(Direction.SOUTH),
                'east': directions.count(Direction.EAST),
                'west': directions.count(Direction.WEST)
            },
            'average_confidence': sum(d.confidence for d in self.decision_history) / len(self.decision_history),
            'last_decision_time': self.decision_history[-1].timestamp if self.decision_history else 0
        }
        
        return stats
    
    def reset_navigation_history(self):
        """Clear navigation decision history"""
        self.decision_history.clear()
        self.logger.info("Navigation history cleared")
    
    def set_sensor_tolerance(self, tolerance: float):
        """Set tolerance for sensor value matching"""
        self.sensor_tolerance = tolerance
        self.logger.info(f"Sensor tolerance set to {tolerance}")
    
    def set_confidence_threshold(self, threshold: float):
        """Set minimum confidence threshold for executing decisions"""
        self.min_confidence_threshold = threshold
        self.logger.info(f"Confidence threshold set to {threshold}")
