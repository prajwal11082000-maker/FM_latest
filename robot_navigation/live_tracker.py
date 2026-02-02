#!/usr/bin/env python3
"""
Live Device Tracker

Provides real-time tracking and monitoring of robot devices with continuous
sensor data processing and live navigation updates.
"""

import time
import threading
import queue
import logging
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from .navigation_enums import SensorData, NavigationStatus
from .navigation_controller import RobotNavigationController


@dataclass
class TrackingEvent:
    """Represents a tracking event with timestamp and data"""
    timestamp: float
    event_type: str
    data: Dict[str, Any]
    robot_id: Optional[str] = None
    
    @property
    def datetime(self) -> datetime:
        """Get event timestamp as datetime object"""
        return datetime.fromtimestamp(self.timestamp)


class DeviceDataBuffer:
    """Circular buffer for storing device sensor data"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.data = []
        self.lock = threading.Lock()
    
    def add(self, sensor_data: SensorData):
        """Add sensor data to buffer"""
        with self.lock:
            self.data.append({
                'timestamp': time.time(),
                'sensor_data': sensor_data
            })
            
            # Maintain buffer size
            if len(self.data) > self.max_size:
                self.data.pop(0)
    
    def get_latest(self, count: int = 1) -> List[Dict]:
        """Get latest sensor data entries"""
        with self.lock:
            if count >= len(self.data):
                return self.data.copy()
            return self.data[-count:].copy()
    
    def get_in_range(self, start_time: float, end_time: float) -> List[Dict]:
        """Get sensor data within time range"""
        with self.lock:
            return [
                entry for entry in self.data 
                if start_time <= entry['timestamp'] <= end_time
            ]
    
    def clear(self):
        """Clear buffer"""
        with self.lock:
            self.data.clear()


class LiveDeviceTracker:
    """
    Live tracking system that continuously monitors robot devices and 
    processes sensor data for real-time navigation.
    """
    
    def __init__(self, robot_controller: RobotNavigationController,
                 robot_id: str = "robot_001",
                 tracking_interval: float = 0.5,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize Live Device Tracker
        
        Args:
            robot_controller: Robot navigation controller instance
            robot_id: Unique identifier for the robot
            tracking_interval: Time interval between tracking updates (seconds)
            logger: Optional logger instance
        """
        self.robot_controller = robot_controller
        self.robot_id = robot_id
        self.tracking_interval = tracking_interval
        self.logger = logger or self._setup_default_logger()
        
        # Tracking state
        self.is_tracking = False
        self.tracking_thread = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        
        # Data management
        self.sensor_data_queue = queue.Queue(maxsize=100)
        self.data_buffer = DeviceDataBuffer(max_size=2000)
        self.tracking_events = []
        self.max_events = 500
        
        # Statistics
        self.start_time = 0
        self.total_sensor_readings = 0
        self.total_navigation_updates = 0
        self.last_sensor_data = None
        self.last_update_time = 0
        
        # Callbacks for tracking events
        self.event_callbacks = {
            'on_sensor_data': [],
            'on_navigation_update': [],
            'on_tracking_error': [],
            'on_device_status_change': []
        }
        
        # Device status
        self.device_status = {
            'connection_status': 'disconnected',
            'sensor_health': 'unknown',
            'navigation_health': 'unknown',
            'last_heartbeat': 0
        }
        
        # Alert thresholds
        self.alert_thresholds = {
            'sensor_timeout': 5.0,  # seconds
            'navigation_failure_rate': 0.1,  # 10%
            'device_response_time': 2.0  # seconds
        }
        
        self.logger.info(f"LiveDeviceTracker initialized for robot {robot_id}")
    
    def _setup_default_logger(self) -> logging.Logger:
        """Setup default logger if none provided"""
        logger = logging.getLogger(f'LiveTracker-{self.robot_id}')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def start_tracking(self):
        """Start live tracking system"""
        if self.is_tracking:
            self.logger.warning("Tracking is already active")
            return
        
        # Start robot navigation system if not active
        if not self.robot_controller.is_active:
            self.robot_controller.start_navigation_system()
        
        self.is_tracking = True
        self.stop_event.clear()
        self.pause_event.clear()
        self.start_time = time.time()
        
        # Start tracking thread
        self.tracking_thread = threading.Thread(
            target=self._tracking_loop,
            name=f"LiveTracker-{self.robot_id}"
        )
        self.tracking_thread.daemon = True
        self.tracking_thread.start()
        
        # Update device status
        self.device_status['connection_status'] = 'connected'
        self.device_status['last_heartbeat'] = time.time()
        
        self._add_tracking_event('tracking_started', {
            'robot_id': self.robot_id,
            'tracking_interval': self.tracking_interval
        })
        
        self.logger.info(f"Live tracking started for robot {self.robot_id}")
    
    def stop_tracking(self):
        """Stop live tracking system"""
        if not self.is_tracking:
            return
        
        self.is_tracking = False
        self.stop_event.set()
        
        # Wait for tracking thread to finish
        if self.tracking_thread and self.tracking_thread.is_alive():
            self.tracking_thread.join(timeout=5.0)
        
        # Update device status
        self.device_status['connection_status'] = 'disconnected'
        
        self._add_tracking_event('tracking_stopped', {
            'robot_id': self.robot_id,
            'total_runtime': time.time() - self.start_time
        })
        
        self.logger.info(f"Live tracking stopped for robot {self.robot_id}")
    
    def pause_tracking(self):
        """Pause tracking (can be resumed)"""
        if not self.is_tracking:
            self.logger.warning("Cannot pause - tracking not active")
            return
        
        self.pause_event.set()
        self._add_tracking_event('tracking_paused', {'robot_id': self.robot_id})
        self.logger.info("Live tracking paused")
    
    def resume_tracking(self):
        """Resume tracking from paused state"""
        if not self.is_tracking:
            self.logger.warning("Cannot resume - tracking not active") 
            return
        
        self.pause_event.clear()
        self._add_tracking_event('tracking_resumed', {'robot_id': self.robot_id})
        self.logger.info("Live tracking resumed")
    
    def submit_sensor_data(self, sensor_data: SensorData) -> bool:
        """
        Submit new sensor data for processing
        
        Args:
            sensor_data: Current robot sensor readings
            
        Returns:
            True if data was accepted, False otherwise
        """
        if not self.is_tracking:
            self.logger.debug("Sensor data submitted but tracking not active")
            return False
        
        try:
            # Add to queue for processing
            self.sensor_data_queue.put(sensor_data, block=False)
            
            # Update device status
            self.device_status['last_heartbeat'] = time.time()
            self.device_status['sensor_health'] = 'healthy'
            
            return True
            
        except queue.Full:
            self.logger.warning("Sensor data queue is full - dropping data")
            self._trigger_event_callbacks('on_tracking_error', 
                                         "Sensor data queue overflow")
            return False
    
    def _tracking_loop(self):
        """Main tracking loop - runs in separate thread"""
        self.logger.info("Starting tracking loop")
        
        while not self.stop_event.is_set():
            try:
                # Wait if paused
                if self.pause_event.is_set():
                    time.sleep(0.1)
                    continue
                
                # Process any pending sensor data
                self._process_sensor_data_queue()
                
                # Check for sensor data timeout
                self._check_sensor_timeout()
                
                # Update device health status
                self._update_device_health()
                
                # Sleep for tracking interval
                time.sleep(self.tracking_interval)
                
            except Exception as e:
                self.logger.error(f"Error in tracking loop: {e}")
                self._trigger_event_callbacks('on_tracking_error', str(e))
                time.sleep(1.0)  # Brief pause on error
        
        self.logger.info("Tracking loop ended")
    
    def _process_sensor_data_queue(self):
        """Process all pending sensor data in the queue"""
        while not self.sensor_data_queue.empty():
            try:
                sensor_data = self.sensor_data_queue.get_nowait()
                self._process_sensor_data(sensor_data)
                
            except queue.Empty:
                break
            except Exception as e:
                self.logger.error(f"Error processing sensor data: {e}")
    
    def _process_sensor_data(self, sensor_data: SensorData):
        """Process individual sensor data entry"""
        try:
            # Record sensor reading
            self.total_sensor_readings += 1
            self.last_sensor_data = sensor_data
            self.last_update_time = time.time()
            
            # Add to data buffer
            self.data_buffer.add(sensor_data)
            
            # Trigger sensor data callbacks
            self._trigger_event_callbacks('on_sensor_data', sensor_data)
            
            # Process navigation decision
            decision = self.robot_controller.process_sensor_data(sensor_data)
            
            if decision:
                self.total_navigation_updates += 1
                
                # Add tracking event
                self._add_tracking_event('navigation_update', {
                    'robot_id': self.robot_id,
                    'action': decision.action.value,
                    'direction': decision.next_direction.value,
                    'confidence': decision.confidence,
                    'sensor_data': sensor_data.to_dict()
                })
                
                # Trigger navigation update callbacks
                self._trigger_event_callbacks('on_navigation_update', decision)
                
                self.logger.debug(f"Navigation decision: {decision.reason}")
            
        except Exception as e:
            self.logger.error(f"Error processing sensor data: {e}")
            self._trigger_event_callbacks('on_tracking_error', str(e))
    
    def _check_sensor_timeout(self):
        """Check for sensor data timeout"""
        if self.last_update_time == 0:
            return
        
        time_since_update = time.time() - self.last_update_time
        
        if time_since_update > self.alert_thresholds['sensor_timeout']:
            self.device_status['sensor_health'] = 'timeout'
            self._trigger_event_callbacks('on_tracking_error', 
                                         f"Sensor timeout: {time_since_update:.1f}s")
    
    def _update_device_health(self):
        """Update overall device health status"""
        current_time = time.time()
        
        # Check navigation health
        if self.robot_controller.is_active:
            nav_stats = self.robot_controller.get_current_state()['performance_stats']
            failure_rate = (nav_stats['failed_navigations'] / 
                          max(nav_stats['total_navigation_steps'], 1))
            
            if failure_rate > self.alert_thresholds['navigation_failure_rate']:
                self.device_status['navigation_health'] = 'degraded'
            else:
                self.device_status['navigation_health'] = 'healthy'
        else:
            self.device_status['navigation_health'] = 'inactive'
        
        # Update heartbeat
        if current_time - self.device_status['last_heartbeat'] < 2.0:
            self.device_status['connection_status'] = 'connected'
        else:
            self.device_status['connection_status'] = 'disconnected'
    
    def _add_tracking_event(self, event_type: str, data: Dict[str, Any]):
        """Add event to tracking history"""
        event = TrackingEvent(
            timestamp=time.time(),
            event_type=event_type,
            data=data,
            robot_id=self.robot_id
        )
        
        self.tracking_events.append(event)
        
        # Maintain event history limit
        if len(self.tracking_events) > self.max_events:
            self.tracking_events.pop(0)
    
    def register_event_callback(self, event_type: str, callback: Callable):
        """
        Register callback for tracking events
        
        Available events:
        - on_sensor_data: Called when new sensor data is processed
        - on_navigation_update: Called when navigation decision is made
        - on_tracking_error: Called when tracking error occurs
        - on_device_status_change: Called when device status changes
        """
        if event_type in self.event_callbacks:
            self.event_callbacks[event_type].append(callback)
            self.logger.debug(f"Registered callback for event: {event_type}")
        else:
            self.logger.warning(f"Unknown event type: {event_type}")
    
    def _trigger_event_callbacks(self, event_type: str, *args, **kwargs):
        """Trigger all callbacks for an event type"""
        if event_type in self.event_callbacks:
            for callback in self.event_callbacks[event_type]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    self.logger.error(f"Error in tracking callback {callback}: {e}")
    
    def get_tracking_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive tracking summary
        
        Returns:
            Dictionary with tracking status and statistics
        """
        current_time = time.time()
        uptime = current_time - self.start_time if self.is_tracking else 0
        
        return {
            'robot_id': self.robot_id,
            'tracking_status': {
                'is_tracking': self.is_tracking,
                'is_paused': self.pause_event.is_set(),
                'uptime_seconds': uptime,
                'tracking_interval': self.tracking_interval
            },
            'device_status': self.device_status.copy(),
            'statistics': {
                'total_sensor_readings': self.total_sensor_readings,
                'total_navigation_updates': self.total_navigation_updates,
                'readings_per_minute': (self.total_sensor_readings / (uptime / 60) 
                                      if uptime > 0 else 0),
                'last_update_time': self.last_update_time,
                'queue_size': self.sensor_data_queue.qsize(),
                'buffer_size': len(self.data_buffer.data)
            },
            'robot_state': self.robot_controller.get_current_state(),
            'recent_events': [
                {
                    'timestamp': event.timestamp,
                    'datetime': event.datetime.isoformat(),
                    'event_type': event.event_type,
                    'data': event.data
                }
                for event in self.tracking_events[-10:]
            ]
        }
    
    def get_sensor_data_history(self, minutes: int = 5) -> List[Dict]:
        """
        Get recent sensor data history
        
        Args:
            minutes: Number of minutes of history to retrieve
            
        Returns:
            List of sensor data entries with timestamps
        """
        end_time = time.time()
        start_time = end_time - (minutes * 60)
        
        return self.data_buffer.get_in_range(start_time, end_time)
    
    def set_alert_thresholds(self, **thresholds):
        """
        Update alert thresholds
        
        Available thresholds:
        - sensor_timeout: Seconds before sensor timeout alert
        - navigation_failure_rate: Navigation failure rate threshold
        - device_response_time: Device response time threshold
        """
        for key, value in thresholds.items():
            if key in self.alert_thresholds:
                self.alert_thresholds[key] = value
                self.logger.info(f"Alert threshold updated: {key} = {value}")
            else:
                self.logger.warning(f"Unknown alert threshold: {key}")
    
    def force_navigation_reset(self):
        """Force reset of robot navigation state"""
        try:
            self.robot_controller.reset_robot_state()
            self._add_tracking_event('navigation_reset', {'robot_id': self.robot_id})
            self.logger.info("Navigation state forcibly reset")
            return True
            
        except Exception as e:
            self.logger.error(f"Error resetting navigation state: {e}")
            return False
    
    def __enter__(self):
        """Context manager entry - start tracking"""
        self.start_tracking()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - stop tracking"""
        self.stop_tracking()
        return False
    
    def __str__(self):
        return (f"LiveDeviceTracker(robot_id={self.robot_id}, "
                f"tracking={self.is_tracking}, readings={self.total_sensor_readings})")
    
    def __repr__(self):
        return str(self)
