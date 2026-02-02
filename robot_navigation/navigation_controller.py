#!/usr/bin/env python3
"""
Robot Navigation Controller

Main controller that coordinates robot navigation, state management, and live tracking.
This is the primary interface for controlling robot movement in the warehouse system.
"""

import time
import threading
import logging
from typing import Optional, Dict, Any, Callable, List, Tuple
from datetime import datetime

from .navigation_enums import (
    Direction, NavigationStatus, NavigationConstants, SensorData
)
from .robot_state import RobotState, Position
from .zone_navigator import ZoneNavigator, NavigationDecision


class NavigationEventHandler:
    """Handles navigation events and callbacks"""
    
    def __init__(self):
        self.callbacks = {
            'on_position_change': [],
            'on_direction_change': [],
            'on_navigation_decision': [],
            'on_error': [],
            'on_status_change': []
        }
    
    def register_callback(self, event_type: str, callback: Callable):
        """Register a callback for navigation events"""
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
    
    def trigger_event(self, event_type: str, *args, **kwargs):
        """Trigger all callbacks for an event type"""
        if event_type in self.callbacks:
            for callback in self.callbacks[event_type]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    logging.error(f"Error in navigation callback {callback}: {e}")


class RobotNavigationController:
    """
    Main navigation controller that orchestrates robot movement and zone navigation.
    
    This controller provides:
    - Sensor-based navigation decisions
    - Real-time position and direction tracking  
    - Event-driven navigation updates
    - Integration with live device tracking
    - Comprehensive logging and monitoring
    """
    
    def __init__(self, initial_position: Optional[Tuple[int, int, int, int, int]] = None,
                 initial_direction: Optional[Direction] = None,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the Navigation Controller
        
        Args:
            initial_position: Starting position (x, y, rotation_x, rotation_y, zone)
            initial_direction: Starting direction (defaults to North)
            logger: Optional logger instance
        """
        # Setup logging
        self.logger = logger or self._setup_default_logger()
        self.logger.info("Initializing RobotNavigationController")
        
        # Initialize robot state
        self.robot_state = RobotState(initial_position, initial_direction)
        
        # Initialize zone navigator
        self.zone_navigator = ZoneNavigator(self.robot_state, self.logger)
        
        # Event handling
        self.event_handler = NavigationEventHandler()
        
        # Navigation control
        self.is_active = False
        self.is_paused = False
        self.navigation_thread = None
        self.stop_event = threading.Event()
        
        # Performance tracking
        self.start_time = time.time()
        self.total_navigation_steps = 0
        self.successful_navigations = 0
        self.failed_navigations = 0
        
        # Configuration
        self.auto_navigation_enabled = False
        self.navigation_interval = 1.0  # seconds between navigation updates
        
        self.logger.info("RobotNavigationController initialized successfully")
    
    def _setup_default_logger(self) -> logging.Logger:
        """Setup default logger if none provided"""
        logger = logging.getLogger('RobotNavigation')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def start_navigation_system(self):
        """Start the navigation system"""
        if self.is_active:
            self.logger.warning("Navigation system is already active")
            return
        
        self.is_active = True
        self.is_paused = False
        self.stop_event.clear()
        self.start_time = time.time()
        
        self.robot_state.set_status(NavigationStatus.IDLE)
        self.event_handler.trigger_event('on_status_change', NavigationStatus.IDLE)
        
        self.logger.info("Navigation system started")
    
    def stop_navigation_system(self):
        """Stop the navigation system"""
        if not self.is_active:
            return
        
        self.is_active = False
        self.stop_event.set()
        
        # Wait for navigation thread to finish
        if self.navigation_thread and self.navigation_thread.is_alive():
            self.navigation_thread.join(timeout=5.0)
        
        self.robot_state.set_status(NavigationStatus.IDLE)
        self.event_handler.trigger_event('on_status_change', NavigationStatus.IDLE)
        
        self.logger.info("Navigation system stopped")
    
    def pause_navigation(self):
        """Pause navigation (can be resumed)"""
        if not self.is_active:
            self.logger.warning("Cannot pause - navigation system not active")
            return
        
        self.is_paused = True
        self.robot_state.set_status(NavigationStatus.IDLE)
        self.logger.info("Navigation paused")
    
    def resume_navigation(self):
        """Resume navigation from paused state"""
        if not self.is_active:
            self.logger.warning("Cannot resume - navigation system not active")
            return
        
        self.is_paused = False
        self.logger.info("Navigation resumed")
    
    def process_sensor_data(self, sensor_data: SensorData) -> NavigationDecision:
        """
        Process sensor data and make navigation decision
        
        Args:
            sensor_data: Current robot sensor readings
            
        Returns:
            NavigationDecision made by the system
        """
        if not self.is_active:
            raise RuntimeError("Navigation system not active")
        
        if self.is_paused:
            self.logger.debug("Navigation is paused - skipping sensor data processing")
            return None
        
        try:
            self.logger.debug(f"Processing sensor data: {sensor_data}")
            
            # Record the navigation attempt
            self.total_navigation_steps += 1
            
            # Get current state before navigation
            old_position = self.robot_state.current_position.coordinates
            old_direction = self.robot_state.current_direction
            
            # Process navigation decision
            decision = self.zone_navigator.navigate_with_sensor_data(sensor_data)
            
            # Check if navigation was successful
            if decision.confidence > 0:
                self.successful_navigations += 1
                
                # Trigger events for state changes
                new_position = self.robot_state.current_position.coordinates
                new_direction = self.robot_state.current_direction
                
                if new_position != old_position:
                    self.event_handler.trigger_event('on_position_change', old_position, new_position)
                
                if new_direction != old_direction:
                    self.event_handler.trigger_event('on_direction_change', old_direction, new_direction)
                
                # Trigger navigation decision event
                self.event_handler.trigger_event('on_navigation_decision', decision)
                
            else:
                self.failed_navigations += 1
                self.event_handler.trigger_event('on_error', f"Navigation decision failed: {decision.reason}")
            
            return decision
            
        except Exception as e:
            self.failed_navigations += 1
            error_msg = f"Error processing sensor data: {e}"
            self.logger.error(error_msg)
            self.event_handler.trigger_event('on_error', error_msg)
            self.robot_state.set_status(NavigationStatus.ERROR)
            raise
    
    def navigate_to_position(self, target_position: Tuple[int, int, int, int, int],
                           target_direction: Optional[Direction] = None) -> bool:
        """
        Navigate robot to a specific position and direction
        
        Args:
            target_position: Target position tuple (x, y, rotation_x, rotation_y, zone)
            target_direction: Optional target direction
            
        Returns:
            True if navigation target was set successfully
        """
        if not self.is_active:
            raise RuntimeError("Navigation system not active")
        
        try:
            self.robot_state.set_target(target_position, target_direction)
            self.logger.info(f"Navigation target set: {target_position}, direction: {target_direction}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting navigation target: {e}")
            return False
    
    def clear_navigation_target(self):
        """Clear current navigation target"""
        self.robot_state.clear_target()
        self.logger.info("Navigation target cleared")
    
    def get_current_state(self) -> Dict[str, Any]:
        """
        Get comprehensive current state information
        
        Returns:
            Dictionary with complete navigation state
        """
        base_state = self.robot_state.get_state_summary()
        navigation_summary = self.zone_navigator.get_navigation_summary()
        
        controller_state = {
            'system_status': {
                'is_active': self.is_active,
                'is_paused': self.is_paused,
                'uptime': time.time() - self.start_time if self.is_active else 0,
                'auto_navigation_enabled': self.auto_navigation_enabled
            },
            'performance_stats': {
                'total_navigation_steps': self.total_navigation_steps,
                'successful_navigations': self.successful_navigations,
                'failed_navigations': self.failed_navigations,
                'success_rate': (self.successful_navigations / self.total_navigation_steps 
                               if self.total_navigation_steps > 0 else 0)
            },
            'robot_state': base_state,
            'navigation_summary': navigation_summary
        }
        
        return controller_state
    
    def get_navigation_history(self, count: int = 20) -> List[Dict]:
        """
        Get recent navigation history
        
        Args:
            count: Number of recent entries to return
            
        Returns:
            List of navigation history entries
        """
        return self.robot_state.history.get_recent_entries(count)
    
    def reset_robot_state(self):
        """Reset robot to initial state"""
        if not self.is_active:
            raise RuntimeError("Navigation system not active")
        
        old_position = self.robot_state.current_position.coordinates
        old_direction = self.robot_state.current_direction
        
        self.robot_state.reset_to_initial()
        
        # Reset navigation history
        self.zone_navigator.reset_navigation_history()
        
        # Reset performance counters
        self.total_navigation_steps = 0
        self.successful_navigations = 0
        self.failed_navigations = 0
        
        # Trigger events
        new_position = self.robot_state.current_position.coordinates
        new_direction = self.robot_state.current_direction
        
        self.event_handler.trigger_event('on_position_change', old_position, new_position)
        self.event_handler.trigger_event('on_direction_change', old_direction, new_direction)
        
        self.logger.info("Robot state reset to initial configuration")
    
    def enable_auto_navigation(self, interval: float = 1.0):
        """
        Enable automatic navigation mode (requires continuous sensor data feed)
        
        Args:
            interval: Time interval between navigation updates in seconds
        """
        self.auto_navigation_enabled = True
        self.navigation_interval = interval
        self.logger.info(f"Auto navigation enabled with {interval}s interval")
    
    def disable_auto_navigation(self):
        """Disable automatic navigation mode"""
        self.auto_navigation_enabled = False
        self.logger.info("Auto navigation disabled")
    
    def register_event_callback(self, event_type: str, callback: Callable):
        """
        Register callback for navigation events
        
        Available events:
        - on_position_change: Called when robot position changes
        - on_direction_change: Called when robot direction changes  
        - on_navigation_decision: Called when navigation decision is made
        - on_error: Called when navigation error occurs
        - on_status_change: Called when navigation status changes
        
        Args:
            event_type: Type of event to register for
            callback: Callback function to register
        """
        self.event_handler.register_callback(event_type, callback)
        self.logger.debug(f"Registered callback for event: {event_type}")
    
    def set_navigation_parameters(self, **kwargs):
        """
        Update navigation parameters
        
        Available parameters:
        - sensor_tolerance: Tolerance for sensor value matching
        - confidence_threshold: Minimum confidence for executing decisions
        - navigation_interval: Time between auto navigation updates
        """
        if 'sensor_tolerance' in kwargs:
            self.zone_navigator.set_sensor_tolerance(kwargs['sensor_tolerance'])
        
        if 'confidence_threshold' in kwargs:
            self.zone_navigator.set_confidence_threshold(kwargs['confidence_threshold'])
        
        if 'navigation_interval' in kwargs:
            self.navigation_interval = kwargs['navigation_interval']
        
        self.logger.info(f"Navigation parameters updated: {kwargs}")
    
    def get_system_diagnostics(self) -> Dict[str, Any]:
        """
        Get comprehensive system diagnostics
        
        Returns:
            Dictionary with diagnostic information
        """
        current_time = time.time()
        
        diagnostics = {
            'timestamp': current_time,
            'datetime': datetime.fromtimestamp(current_time).isoformat(),
            'system_health': {
                'navigation_active': self.is_active,
                'navigation_paused': self.is_paused,
                'uptime_seconds': current_time - self.start_time if self.is_active else 0,
                'total_operations': self.total_navigation_steps,
                'success_rate': (self.successful_navigations / self.total_navigation_steps 
                               if self.total_navigation_steps > 0 else 0)
            },
            'current_state': self.get_current_state(),
            'configuration': {
                'auto_navigation_enabled': self.auto_navigation_enabled,
                'navigation_interval': self.navigation_interval,
                'sensor_tolerance': self.zone_navigator.sensor_tolerance,
                'confidence_threshold': self.zone_navigator.min_confidence_threshold
            }
        }
        
        return diagnostics
    
    def __enter__(self):
        """Context manager entry - start navigation system"""
        self.start_navigation_system()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - stop navigation system"""
        self.stop_navigation_system()
        return False
    
    def __str__(self):
        return (f"RobotNavigationController(active={self.is_active}, "
                f"position={self.robot_state.current_position}, "
                f"direction={self.robot_state.current_direction})")
    
    def __repr__(self):
        return str(self)
