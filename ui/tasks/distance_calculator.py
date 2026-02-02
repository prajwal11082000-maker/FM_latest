"""
Distance Calculation Module

Calculates distances for maps, zones, stops, and device-to-map routing.
"""
from typing import Dict, List, Optional, Tuple
from data_manager.csv_handler import CSVHandler
from utils.logger import setup_logger


class DistanceCalculator:
    """Handles distance calculations for warehouse navigation"""
    
    def __init__(self, csv_handler: CSVHandler):
        self.csv_handler = csv_handler
        self.logger = setup_logger('distance_calculator')
    
    def calculate_stop_distance(self, stop_id: str) -> float:
        """
        Calculate distance for a single stop including bin positions.
        
        Args:
            stop_id: Stop identifier
            
        Returns:
            Total distance in millimeters for visiting all bins at this stop
        """
        try:
            stops = self.csv_handler.read_csv('stops')
            stop = next((s for s in stops if str(s.get('stop_id', '')) == str(stop_id)), None)
            
            if not stop:
                self.logger.warning(f"Stop {stop_id} not found")
                return 0.0
            
            # Get bin configuration
            left_bins = int(stop.get('left_bins_count', 0))
            right_bins = int(stop.get('right_bins_count', 0))
            left_distance = float(stop.get('left_bins_distance', 0))
            right_distance = float(stop.get('right_bins_distance', 0))
            
            # Calculate total distance to visit all bins
            # Distance = (left bins * left distance * 2) + (right bins * right distance * 2)
            # Multiply by 2 for round trip to each bin
            left_total = left_bins * left_distance * 2 * 1000  # Convert to mm
            right_total = right_bins * right_distance * 2 * 1000  # Convert to mm
            
            total = left_total + right_total
            self.logger.debug(f"Stop {stop_id} distance: {total}mm (L:{left_total}mm, R:{right_total}mm)")
            return total
            
        except Exception as e:
            self.logger.error(f"Error calculating stop distance for {stop_id}: {e}")
            return 0.0
    
    def calculate_multiple_stops_distance(self, stop_ids: List[str]) -> float:
        """
        Calculate total distance for multiple stops.
        
        Args:
            stop_ids: List of stop identifiers
            
        Returns:
            Total distance in millimeters for all stops
        """
        total = 0.0
        for stop_id in stop_ids:
            total += self.calculate_stop_distance(stop_id)
        return total
    
    def calculate_zone_stops_distance(self, zone_id: str) -> float:
        """
        Calculate total distance for all stops in a zone connection.
        
        Args:
            zone_id: Zone connection identifier
            
        Returns:
            Total distance in millimeters for all stops in this zone
        """
        try:
            stops = self.csv_handler.read_csv('stops')
            zone_stops = [s for s in stops if str(s.get('zone_connection_id', '')) == str(zone_id)]
            
            total = 0.0
            for stop in zone_stops:
                stop_id = stop.get('stop_id', '')
                if stop_id:
                    total += self.calculate_stop_distance(stop_id)
            
            self.logger.debug(f"Zone {zone_id} stops total distance: {total}mm ({len(zone_stops)} stops)")
            return total
            
        except Exception as e:
            self.logger.error(f"Error calculating zone stops distance for {zone_id}: {e}")
            return 0.0
    
    def calculate_map_distance(self, map_id: str, include_stops: bool = True) -> float:
        """
        Calculate total distance for a map by summing all zone distances.
        
        For picking/storing: Sum all zone connection distances in the map
        For auditing: Sum all zone distances for complete map traversal
        
        Args:
            map_id: Map identifier
            include_stops: Whether to include stop distances (default: True)
            
        Returns:
            Total distance in meters (converted to mm if needed)
        """
        try:
            zones = self.csv_handler.read_csv('zones')
            total_distance = 0.0
            
            for zone in zones:
                if str(zone.get('map_id', '')) == str(map_id):
                    zone_id = zone.get('id', '')
                    
                    # Add zone connection distance
                    distance = zone.get('magnitude') or zone.get('distance', '0')
                    try:
                        distance_val = float(distance) if distance and str(distance).strip() else 0.0
                        distance_mm = distance_val * 1000  # Convert meters to mm
                        total_distance += distance_mm
                    except (ValueError, TypeError) as e:
                        self.logger.debug(f"Could not parse distance value '{distance}': {e}")
                        pass
                    
                    # Add stops distance if requested
                    if include_stops and zone_id:
                        stops_distance = self.calculate_zone_stops_distance(zone_id)
                        total_distance += stops_distance
            
            self.logger.debug(f"Calculated map distance for map_id={map_id}: {total_distance}mm (stops_included={include_stops})")
            return total_distance
            
        except Exception as e:
            self.logger.error(f"Error calculating map distance for map_id={map_id}: {e}")
            return 0.0
    
    def calculate_path_distance(self, map_id: str, from_zone: str, to_zone: str, 
                               selected_stops: Optional[List[str]] = None,
                               include_all_stops: bool = False) -> float:
        """
        Calculate distance for a specific path between zones.
        
        Uses BFS to find path and sums distances along the route.
        
        Args:
            map_id: Map identifier
            from_zone: Starting zone
            to_zone: Destination zone
            selected_stops: List of specific stop IDs to include (optional)
            include_all_stops: Include all stops in path zones (default: False)
            
        Returns:
            Total path distance in millimeters
        """
        try:
            zones = self.csv_handler.read_csv('zones')
            
            # Build graph with distances and zone IDs
            graph = {}
            zone_info = {}  # Store zone IDs for later stop calculation
            
            for zone in zones:
                if str(zone.get('map_id', '')) == str(map_id):
                    from_z = zone.get('from_zone', '')
                    to_z = zone.get('to_zone', '')
                    zone_id = zone.get('id', '')
                    
                    if from_z:
                        distance = zone.get('magnitude') or zone.get('distance', '0')
                        try:
                            distance_val = float(distance) if distance and str(distance).strip() else 0.0
                            distance_mm = distance_val * 1000  # Convert meters to mm
                        except (ValueError, TypeError):
                            distance_mm = 0.0
                        
                        if from_z not in graph:
                            graph[from_z] = {}
                        graph[from_z][to_z] = {'distance': distance_mm, 'zone_id': zone_id}
                        zone_info[f"{from_z}->{to_z}"] = zone_id
            
            # BFS to find path and sum distances
            queue = [(from_zone, 0.0, [])]  # (current_zone, total_distance, zone_ids_in_path)
            visited = {from_zone}
            
            while queue:
                current, distance, path_zones = queue.pop(0)
                
                if current == to_zone:
                    # Calculate stop distances
                    stops_distance = 0.0
                    
                    if selected_stops:
                        # Use only selected stops
                        stops_distance = self.calculate_multiple_stops_distance(selected_stops)
                        self.logger.debug(f"Selected stops distance: {stops_distance}mm ({len(selected_stops)} stops)")
                    elif include_all_stops:
                        # Include all stops in path zones
                        for zone_id in path_zones:
                            stops_distance += self.calculate_zone_stops_distance(zone_id)
                        self.logger.debug(f"All stops in path distance: {stops_distance}mm")
                    
                    total = distance + stops_distance
                    self.logger.info(f"Path distance from {from_zone} to {to_zone}: {total}mm (zone:{distance}mm + stops:{stops_distance}mm)")
                    return total
                
                if current in graph:
                    for next_zone, edge_info in graph[current].items():
                        if next_zone not in visited:
                            visited.add(next_zone)
                            new_distance = distance + edge_info['distance']
                            new_path = path_zones + [edge_info['zone_id']]
                            queue.append((next_zone, new_distance, new_path))
            
            # No path found
            self.logger.warning(f"No path found from {from_zone} to {to_zone} in map {map_id}")
            return 0.0
            
        except Exception as e:
            self.logger.error(f"Error calculating path distance: {e}")
            return 0.0
    
    def calculate_device_to_map_distance(self, device_location: str, map_id: str) -> float:
        """
        Calculate distance from device's current location to map starting point.
        
        Args:
            device_location: Device's current location (zone ID or zone name)
            map_id: Target map identifier
            
        Returns:
            Distance in millimeters from device to map entry point
        """
        try:
            zones = self.csv_handler.read_csv('zones')
            map_zones = [z for z in zones if str(z.get('map_id', '')) == str(map_id)]
            
            if not map_zones:
                self.logger.warning(f"No zones found for map_id={map_id}")
                return 0.0
            
            # Find starting zone (zone with minimum from_zone or first zone)
            starting_zones = {}
            for zone in map_zones:
                from_z = zone.get('from_zone', '')
                if from_z:
                    # Get minimum zone as starting point (heuristic)
                    try:
                        zone_num = int(from_z)
                        if zone_num not in starting_zones:
                            starting_zones[zone_num] = from_z
                    except (ValueError, TypeError):
                        if from_z not in starting_zones.values():
                            starting_zones[0] = from_z
            
            if not starting_zones:
                return 0.0
            
            # Get first/starting zone
            start_zone = starting_zones.get(min(starting_zones.keys())) if starting_zones else map_zones[0].get('from_zone', '')
            
            if not start_zone:
                return 0.0
            
            # If device is already in the map, return 0
            if str(device_location).strip() == str(start_zone).strip():
                return 0.0
            
            # Try to find path from device location to start zone
            device_zone_matches = [z for z in zones 
                                 if (str(z.get('from_zone', '')).strip() == str(device_location).strip() or
                                     str(z.get('to_zone', '')).strip() == str(device_location).strip())]
            
            if device_zone_matches:
                device_map_id = device_zone_matches[0].get('map_id', '')
                if str(device_map_id) == str(map_id):
                    # Same map - use path finding (without stops for device travel)
                    return self.calculate_path_distance(map_id, str(device_location), str(start_zone), 
                                                       include_all_stops=False)
                else:
                    # Different map - would need cross-map routing (return 0 for now)
                    return 0.0
            
            # Device location not found in zones - return 0
            return 0.0
            
        except Exception as e:
            self.logger.error(f"Error calculating device to map distance: {e}")
            return 0.0
    
    def get_required_distance_for_task(self, task_type: str, map_id: str, 
                                      from_zone: Optional[str] = None, 
                                      to_zone: Optional[str] = None,
                                      selected_stops: Optional[List[str]] = None) -> float:
        """
        Calculate required distance based on task type.
        
        Args:
            task_type: 'picking', 'storing', or 'auditing'
            map_id: Map identifier
            from_zone: Starting zone (for picking/storing)
            to_zone: Destination zone (for picking/storing)
            selected_stops: List of selected stop IDs (for picking/storing)
            
        Returns:
            Required distance in millimeters
        """
        if task_type == 'auditing':
            # Auditing: complete map traversal with all stops
            return self.calculate_map_distance(map_id, include_stops=True)
        elif task_type in ['picking', 'storing']:
            # Picking/Storing: specific path distance
            if from_zone and to_zone:
                # Include selected stops or all stops if none selected
                include_all = (selected_stops is None or len(selected_stops) == 0)
                return self.calculate_path_distance(map_id, from_zone, to_zone, 
                                                   selected_stops=selected_stops,
                                                   include_all_stops=include_all)
            else:
                # Fallback to map distance if zones not specified
                return self.calculate_map_distance(map_id, include_stops=True)
        else:
            return 0.0