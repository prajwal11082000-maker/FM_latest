"""
Task Type Handlers Module

Handles task-type-specific logic for picking, storing, and auditing tasks.
Includes stop distance calculations.
"""
from typing import Dict, Optional, Tuple, List
from data_manager.csv_handler import CSVHandler
from utils.logger import setup_logger
from .distance_calculator import DistanceCalculator


class TaskTypeHandler:
    """Base class for task type handlers"""
    
    def __init__(self, csv_handler: CSVHandler, distance_calculator: DistanceCalculator):
        self.csv_handler = csv_handler
        self.distance_calculator = distance_calculator
        self.logger = setup_logger('task_type_handler')
    
    def calculate_required_distance(self, map_id: str, **kwargs) -> float:
        """Calculate required distance for this task type"""
        raise NotImplementedError
    
    def validate_task_details(self, **kwargs) -> Tuple[bool, Optional[str]]:
        """Validate task-specific details"""
        raise NotImplementedError


class PickingTaskHandler(TaskTypeHandler):
    """Handler for picking tasks"""
    
    def calculate_required_distance(self, map_id: str, from_zone: str, to_zone: str, 
                                   selected_stops: Optional[List[str]] = None, **kwargs) -> float:
        """
        Calculate required distance for picking task.
        
        Includes:
        - Zone connection distances
        - Selected stop distances (bin visits)
        - If no stops selected, includes all stops in the path
        
        Args:
            map_id: Map identifier
            from_zone: Starting zone
            to_zone: Destination zone
            selected_stops: List of selected stop IDs (optional)
            
        Returns:
            Required distance in millimeters
        """
        if not from_zone or not to_zone:
            return 0.0
        
        # Calculate path distance with stops
        include_all_stops = (selected_stops is None or len(selected_stops) == 0)
        total_distance = self.distance_calculator.calculate_path_distance(
            map_id, from_zone, to_zone,
            selected_stops=selected_stops,
            include_all_stops=include_all_stops
        )
        
        self.logger.info(f"Picking task distance: {total_distance}mm (stops: {len(selected_stops) if selected_stops else 'all'})")
        return total_distance
    
    def validate_task_details(self, map_id: Optional[str] = None, 
                             from_zone: Optional[str] = None,
                             to_zone: Optional[str] = None, **kwargs) -> Tuple[bool, Optional[str]]:
        """Validate picking task details"""
        if not map_id:
            return False, "Pickup map is required"
        if not from_zone:
            return False, "From zone is required"
        if not to_zone:
            return False, "To zone is required"
        return True, None


class StoringTaskHandler(TaskTypeHandler):
    """Handler for storing tasks"""
    
    def calculate_required_distance(self, map_id: str, from_zone: str, to_zone: str,
                                   selected_stops: Optional[List[str]] = None, **kwargs) -> float:
        """
        Calculate required distance for storing task.
        
        Includes:
        - Zone connection distances
        - Selected stop distances (bin visits)
        - If no stops selected, includes all stops in the path
        
        Args:
            map_id: Map identifier
            from_zone: Starting zone
            to_zone: Destination zone
            selected_stops: List of selected stop IDs (optional)
            
        Returns:
            Required distance in millimeters
        """
        if not from_zone or not to_zone:
            return 0.0
        
        # Calculate path distance with stops
        include_all_stops = (selected_stops is None or len(selected_stops) == 0)
        total_distance = self.distance_calculator.calculate_path_distance(
            map_id, from_zone, to_zone,
            selected_stops=selected_stops,
            include_all_stops=include_all_stops
        )
        
        self.logger.info(f"Storing task distance: {total_distance}mm (stops: {len(selected_stops) if selected_stops else 'all'})")
        return total_distance
    
    def validate_task_details(self, map_id: Optional[str] = None,
                             from_zone: Optional[str] = None,
                             to_zone: Optional[str] = None, **kwargs) -> Tuple[bool, Optional[str]]:
        """Validate storing task details"""
        if not map_id:
            return False, "Storing map is required"
        if not from_zone:
            return False, "From zone is required"
        if not to_zone:
            return False, "To zone is required"
        return True, None


class AuditingTaskHandler(TaskTypeHandler):
    """Handler for auditing tasks"""
    
    def calculate_required_distance(self, map_id: str, **kwargs) -> float:
        """
        Calculate required distance for auditing task.
        
        Auditing requires complete map traversal including:
        - All zone connections
        - All stops in the map (bin visits)
        
        Args:
            map_id: Map identifier
            
        Returns:
            Required distance in millimeters (complete map distance with stops)
        """
        total_distance = self.distance_calculator.calculate_map_distance(
            map_id, 
            include_stops=True
        )
        
        self.logger.info(f"Auditing task distance: {total_distance}mm (full map with all stops)")
        return total_distance
    
    def validate_task_details(self, map_id: Optional[str] = None, **kwargs) -> Tuple[bool, Optional[str]]:
        """Validate auditing task details"""
        if not map_id:
            return False, "Auditing map is required"
        return True, None


class ChargingTaskHandler(TaskTypeHandler):
    """Handler for charging tasks"""
    
    def calculate_required_distance(self, map_id: str, **kwargs) -> float:
        """
        Charging tasks don't have a specific traversal distance.
        The device just goes to a fixed charging station.
        """
        return 0.0
    
    def validate_task_details(self, map_id: Optional[str] = None, 
                              station_id: Optional[str] = None,
                              **kwargs) -> Tuple[bool, Optional[str]]:
        """Validate charging task details"""
        if not map_id:
            return False, "Charging map is required"
        if not station_id:
            return False, "Charging station is required"
        return True, None


class TaskTypeHandlerFactory:
    """Factory for creating task type handlers"""
    
    @staticmethod
    def create_handler(task_type: str, csv_handler: CSVHandler, 
                      distance_calculator: DistanceCalculator) -> TaskTypeHandler:
        """
        Create appropriate handler for task type.
        
        Args:
            task_type: 'picking', 'storing', or 'auditing'
            csv_handler: CSV handler instance
            distance_calculator: Distance calculator instance
            
        Returns:
            Appropriate task type handler
        """
        if task_type == 'picking':
            return PickingTaskHandler(csv_handler, distance_calculator)
        elif task_type == 'storing':
            return StoringTaskHandler(csv_handler, distance_calculator)
        elif task_type == 'auditing':
            return AuditingTaskHandler(csv_handler, distance_calculator)
        else:
            raise ValueError(f"Unknown task type: {task_type}")