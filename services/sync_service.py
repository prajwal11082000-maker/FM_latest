#!/usr/bin/env python3
"""
Scheduled Device Location Sync Service

This service runs periodic synchronization between device log files and the main
devices CSV table to ensure location data stays up-to-date.
"""

import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Callable
import logging

from utils.logger import setup_logger
from sync_device_locations import DeviceLocationSyncer


class DeviceLocationSyncService:
    def __init__(self, sync_interval_minutes: int = 5, auto_start: bool = False):
        """
        Initialize the sync service.
        
        Args:
            sync_interval_minutes: How often to sync (in minutes)
            auto_start: Whether to start the service automatically
        """
        self.logger = setup_logger('sync_service')
        self.sync_interval_minutes = sync_interval_minutes
        self.sync_interval_seconds = sync_interval_minutes * 60
        
        self.syncer = DeviceLocationSyncer()
        self.is_running = False
        self.sync_thread = None
        self.stop_event = threading.Event()
        
        # Callbacks
        self.on_sync_completed = None
        self.on_sync_error = None
        
        # Statistics
        self.total_syncs = 0
        self.successful_syncs = 0
        self.failed_syncs = 0
        self.last_sync_time = None
        self.last_sync_result = None
        
        if auto_start:
            self.start()
    
    def set_sync_callback(self, on_completed: Callable = None, on_error: Callable = None):
        """
        Set callback functions for sync events.
        
        Args:
            on_completed: Called when sync completes successfully (receives result dict)
            on_error: Called when sync fails (receives error message)
        """
        self.on_sync_completed = on_completed
        self.on_sync_error = on_error
    
    def start(self) -> bool:
        """
        Start the sync service.
        
        Returns:
            True if started successfully, False if already running
        """
        if self.is_running:
            self.logger.warning("Sync service is already running")
            return False
        
        self.logger.info(f"Starting device location sync service (interval: {self.sync_interval_minutes} minutes)")
        
        self.is_running = True
        self.stop_event.clear()
        
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()
        
        return True
    
    def stop(self) -> bool:
        """
        Stop the sync service.
        
        Returns:
            True if stopped successfully, False if not running
        """
        if not self.is_running:
            self.logger.warning("Sync service is not running")
            return False
        
        self.logger.info("Stopping device location sync service")
        
        self.is_running = False
        self.stop_event.set()
        
        if self.sync_thread and self.sync_thread.is_alive():
            self.sync_thread.join(timeout=10)  # Wait up to 10 seconds
        
        return True
    
    def sync_now(self) -> dict:
        """
        Perform an immediate sync (doesn't interfere with scheduled syncs).
        
        Returns:
            Sync result dictionary
        """
        return self._perform_sync()
    
    def get_status(self) -> dict:
        """
        Get the current status of the sync service.
        
        Returns:
            Status dictionary with service and sync information
        """
        return {
            'service_running': self.is_running,
            'sync_interval_minutes': self.sync_interval_minutes,
            'total_syncs': self.total_syncs,
            'successful_syncs': self.successful_syncs,
            'failed_syncs': self.failed_syncs,
            'last_sync_time': self.last_sync_time.isoformat() if self.last_sync_time else None,
            'last_sync_result': self.last_sync_result,
            'next_sync_time': self._get_next_sync_time().isoformat() if self.is_running else None
        }
    
    def _get_next_sync_time(self) -> datetime:
        """Get the estimated next sync time."""
        if self.last_sync_time:
            return self.last_sync_time + timedelta(minutes=self.sync_interval_minutes)
        return datetime.now() + timedelta(minutes=self.sync_interval_minutes)
    
    def _sync_loop(self):
        """Main sync loop running in a separate thread."""
        self.logger.info("Device location sync loop started")
        
        while not self.stop_event.is_set():
            try:
                # Perform sync
                self._perform_sync()
                
                # Wait for the next sync or stop signal
                if self.stop_event.wait(timeout=self.sync_interval_seconds):
                    break  # Stop event was set
                    
            except Exception as e:
                self.logger.error(f"Unexpected error in sync loop: {e}")
                # Wait a bit before retrying to avoid rapid failure loops
                if self.stop_event.wait(timeout=30):
                    break
        
        self.logger.info("Device location sync loop stopped")
    
    def _perform_sync(self) -> dict:
        """
        Perform the actual synchronization.
        
        Returns:
            Sync result dictionary
        """
        self.logger.debug("Starting device location sync")
        self.total_syncs += 1
        self.last_sync_time = datetime.now()
        
        try:
            # Perform the sync
            result = self.syncer.sync_device_locations()
            
            # Check if sync was successful
            if result.get('errors'):
                self.failed_syncs += 1
                error_msg = f"Sync completed with errors: {'; '.join(result['errors'])}"
                self.logger.warning(error_msg)
                
                if self.on_sync_error:
                    self.on_sync_error(error_msg)
            else:
                self.successful_syncs += 1
                self.logger.info(f"Sync completed successfully. Updated {result.get('updated_devices', 0)} devices")
                
                if self.on_sync_completed:
                    self.on_sync_completed(result)
            
            self.last_sync_result = result
            return result
            
        except Exception as e:
            self.failed_syncs += 1
            error_msg = f"Sync failed with exception: {e}"
            self.logger.error(error_msg)
            
            result = {
                'total_devices': 0,
                'updated_devices': 0,
                'unchanged_devices': 0,
                'error_devices': 0,
                'updated_device_ids': [],
                'errors': [error_msg],
                'exception': str(e)
            }
            
            self.last_sync_result = result
            
            if self.on_sync_error:
                self.on_sync_error(error_msg)
            
            return result
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


class SyncServiceManager:
    """
    Manager for controlling the sync service globally.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.logger = setup_logger('sync_service_manager')
            self.service = None
            self.initialized = True
    
    def start_service(self, sync_interval_minutes: int = 5) -> bool:
        """
        Start the global sync service.
        
        Args:
            sync_interval_minutes: Sync interval in minutes
            
        Returns:
            True if started, False if already running
        """
        if self.service and self.service.is_running:
            self.logger.warning("Sync service is already running")
            return False
        
        try:
            self.service = DeviceLocationSyncService(
                sync_interval_minutes=sync_interval_minutes,
                auto_start=True
            )
            self.logger.info("Global sync service started")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start sync service: {e}")
            return False
    
    def stop_service(self) -> bool:
        """
        Stop the global sync service.
        
        Returns:
            True if stopped, False if not running
        """
        if not self.service or not self.service.is_running:
            self.logger.warning("Sync service is not running")
            return False
        
        try:
            result = self.service.stop()
            self.logger.info("Global sync service stopped")
            return result
        except Exception as e:
            self.logger.error(f"Failed to stop sync service: {e}")
            return False
    
    def get_service_status(self) -> dict:
        """Get the status of the sync service."""
        if not self.service:
            return {
                'service_running': False,
                'message': 'Service not initialized'
            }
        
        return self.service.get_status()
    
    def sync_now(self) -> dict:
        """Perform an immediate sync."""
        if not self.service:
            return {
                'error': 'Service not initialized',
                'total_devices': 0,
                'updated_devices': 0,
                'unchanged_devices': 0,
                'error_devices': 0,
                'updated_device_ids': [],
                'errors': ['Service not initialized']
            }
        
        return self.service.sync_now()


def main():
    """CLI interface for the sync service."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Device Location Sync Service')
    parser.add_argument('--interval', type=int, default=5,
                       help='Sync interval in minutes (default: 5)')
    parser.add_argument('--once', action='store_true',
                       help='Run sync once and exit')
    parser.add_argument('--status', action='store_true',
                       help='Check service status')
    
    args = parser.parse_args()
    
    if args.status:
        manager = SyncServiceManager()
        status = manager.get_service_status()

        for key, value in status.items():
            print(f"  {key}: {value}")
        return
    
    if args.once:

        syncer = DeviceLocationSyncer()
        result = syncer.sync_device_locations()
        

        
        if result['updated_device_ids']:
            print(f"  Updated device IDs: {', '.join(result['updated_device_ids'])}")
        
        if result['errors']:
            print(f"  Errors:")
            for error in result['errors']:
                print(f"    - {error}")
        
        return
    
    # Run continuous sync service

    try:
        with DeviceLocationSyncService(sync_interval_minutes=args.interval, auto_start=True) as service:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\nSync service stopped by user")


if __name__ == "__main__":
    main()
