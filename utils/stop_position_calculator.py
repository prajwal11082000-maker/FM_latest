"""
Stop Position Calculator

Automatically calculates stop positions and bin coordinates along zone routes.
Takes zone length, bin counts, and generates precise (x, y) coordinates for
stop placement with proper left/right bin offsetting.
"""

import math
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class BinPosition:
    """Represents a single bin position"""
    x: float
    y: float
    side: str  # 'left' or 'right'
    bin_number: int
    stop_id: str


@dataclass
class StopPosition:
    """Represents a stop with its main position and associated bins"""
    stop_id: str
    name: str
    main_x: float
    main_y: float
    bins: List[BinPosition]
    distance_from_start: float


class StopPositionCalculator:
    """
    Calculates precise stop positions and bin coordinates along zone routes.
    
    Features:
    - Automatic stop spacing calculation based on zone length
    - Left and right bin positioning with proper offsets
    - Support for different zone orientations (north, south, east, west, etc.)
    - Collision detection and overlap prevention
    """
    
    def __init__(self):
        self.direction_vectors = {
            'north': (0, -1),
            'south': (0, 1), 
            'east': (1, 0),
            'west': (-1, 0),
            'northeast': (0.707, -0.707),
            'northwest': (-0.707, -0.707),
            'southeast': (0.707, 0.707),
            'southwest': (-0.707, 0.707)
        }
    
    def calculate_stop_positions(
        self,
        zone_data: Dict,
        left_bins_count: int,
        right_bins_count: int,
        bin_offset_distance: float = 2.0,
        bin_spacing: float = 0.5
    ) -> List[StopPosition]:
        """
        Calculate stop positions along a zone route with automatic bin placement.
        
        Args:
            zone_data: Zone connection data with from/to coordinates and distance
            left_bins_count: Number of bins on the left side of each stop
            right_bins_count: Number of bins on the right side of each stop
            bin_offset_distance: Distance (meters) to offset bins from main path
            bin_spacing: Spacing between bins on the same side (meters)
            
        Returns:
            List of StopPosition objects with coordinates
        """
        # Extract zone parameters
        from_x = zone_data.get('from_x', 0)
        from_y = zone_data.get('from_y', 0)
        to_x = zone_data.get('to_x', 0)
        to_y = zone_data.get('to_y', 0)
        total_distance = float(zone_data.get('magnitude', 50))
        direction = zone_data.get('direction', 'north').lower()
        
        # Calculate total bins per stop
        total_bins = left_bins_count + right_bins_count
        
        # Calculate number of stops based on zone length and bins
        # Rule: divide path into equal segments based on bin requirements
        if total_bins > 0:
            # Each stop needs space for bins, so calculate based on bin requirements
            min_stop_spacing = max(3.0, total_bins * bin_spacing + 2.0)  # Minimum 3m between stops
            max_stops = max(1, int(total_distance / min_stop_spacing))
            num_stops = min(max_stops, total_bins)  # Don't exceed total bins
        else:
            # No bins, use standard spacing
            num_stops = max(1, int(total_distance / 5.0))  # 5m default spacing
        
        # Calculate actual stop spacing
        if num_stops > 1:
            stop_spacing = total_distance / (num_stops - 1)
        else:
            stop_spacing = 0
            
        # Calculate path direction vector
        path_dx = to_x - from_x
        path_dy = to_y - from_y
        path_length = math.sqrt(path_dx * path_dx + path_dy * path_dy)
        
        if path_length > 0:
            # Normalize path direction
            path_dx /= path_length
            path_dy /= path_length
        else:
            # Fallback to direction vector
            path_dx, path_dy = self.direction_vectors.get(direction, (1, 0))
        
        # Calculate perpendicular vector for bin offsets
        perp_dx = -path_dy  # Rotate 90 degrees for perpendicular
        perp_dy = path_dx
        
        stops = []
        
        for i in range(num_stops):
            # Calculate stop position along main path
            if num_stops > 1:
                progress = i / (num_stops - 1)
            else:
                progress = 0.5  # Single stop at center
                
            stop_x = from_x + path_dx * total_distance * progress
            stop_y = from_y + path_dy * total_distance * progress
            distance_from_start = total_distance * progress
            
            # Generate stop ID and name
            stop_id = f"STOP_{zone_data.get('from_zone', 'A')}_{zone_data.get('to_zone', 'B')}_{i+1:03d}"
            stop_name = f"Stop {i+1}"
            
            # Calculate bin positions
            bins = []
            
            # Left bins
            for bin_num in range(left_bins_count):
                bin_x = stop_x + perp_dx * bin_offset_distance
                bin_y = stop_y + perp_dy * bin_offset_distance
                
                # Space bins along the perpendicular direction
                if left_bins_count > 1:
                    bin_offset = (bin_num - (left_bins_count - 1) / 2) * bin_spacing
                    bin_x += path_dx * bin_offset
                    bin_y += path_dy * bin_offset
                
                bins.append(BinPosition(
                    x=bin_x,
                    y=bin_y,
                    side='left',
                    bin_number=bin_num + 1,
                    stop_id=stop_id
                ))
            
            # Right bins
            for bin_num in range(right_bins_count):
                bin_x = stop_x - perp_dx * bin_offset_distance
                bin_y = stop_y - perp_dy * bin_offset_distance
                
                # Space bins along the perpendicular direction
                if right_bins_count > 1:
                    bin_offset = (bin_num - (right_bins_count - 1) / 2) * bin_spacing
                    bin_x += path_dx * bin_offset
                    bin_y += path_dy * bin_offset
                
                bins.append(BinPosition(
                    x=bin_x,
                    y=bin_y,
                    side='right',
                    bin_number=bin_num + 1,
                    stop_id=stop_id
                ))
            
            stops.append(StopPosition(
                stop_id=stop_id,
                name=stop_name,
                main_x=stop_x,
                main_y=stop_y,
                bins=bins,
                distance_from_start=distance_from_start
            ))
        
        return stops
    
    def calculate_equal_interval_stops(
        self,
        from_point: Tuple[float, float],
        to_point: Tuple[float, float],
        total_distance: float,
        left_bins_count: int,
        right_bins_count: int,
        bin_offset_distance: float = 2.0,
        zone_name: str = "A_to_B"
    ) -> List[StopPosition]:
        """
        Calculate stops at equal intervals based on the maximum number of bins.
        Creates stops with both left and right bins at each position.
        
        Example: Distance 50m, Left bins = 2, Right bins = 2
        - Total stops needed: max(2, 2) = 2 stops
        - Stop positions: 16.67m (50/3*1) and 33.33m (50/3*2) from start
        - Each stop will have 1 left bin and 1 right bin
        
        Args:
            from_point: (x, y) coordinates of start point
            to_point: (x, y) coordinates of end point
            total_distance: Total distance from A to B in meters
            left_bins_count: Total number of left side bins needed
            right_bins_count: Total number of right side bins needed
            bin_offset_distance: Offset distance for bins from main path
            zone_name: Name identifier for the zone
            
        Returns:
            List of StopPosition objects with precise coordinates
        """
        from_x, from_y = from_point
        to_x, to_y = to_point
        
        # Calculate path direction vector
        path_dx = to_x - from_x
        path_dy = to_y - from_y
        path_length = math.sqrt(path_dx * path_dx + path_dy * path_dy)
        
        if path_length > 0:
            path_dx /= path_length
            path_dy /= path_length
        else:
            path_dx, path_dy = 1, 0
        
        # Calculate perpendicular vector for bin placement
        perp_dx = -path_dy
        perp_dy = path_dx
        
        # Determine number of stops needed (based on the maximum of left or right bins)
        max_bins = max(left_bins_count, right_bins_count)
        
        if max_bins == 0:
            return []  # No stops needed if no bins
        
        # Calculate stop positions using improved equal interval logic with minimum spacing
        # Ensure stops are well spaced to prevent visual overlap
        min_stop_spacing = 3.0  # Minimum 3 meters between stops for visibility
        
        # Calculate optimal spacing based on distance and bin requirements
        if total_distance / max_bins < min_stop_spacing:
            # If distance is too short for ideal spacing, reduce number of stops
            adjusted_stops = max(1, int(total_distance / min_stop_spacing))
            segments = adjusted_stops + 1
        else:
            segments = max_bins + 1
        
        segment_length = total_distance / segments
        
        stops = []
        
        for i in range(1, segments):  # Skip first (0) and last (segments) positions
            distance_from_start = i * segment_length
            
            # Calculate main position along the path
            main_x = from_x + path_dx * distance_from_start
            main_y = from_y + path_dy * distance_from_start
            
            # Generate stop ID and name
            stop_id = f"STOP_{zone_name}_{i:03d}"
            stop_name = f"Stop {i}"
            
            # Create bins for this stop
            bins = []
            
            # Add left bin if we still have left bins to allocate
            if i <= left_bins_count:
                # Calculate left side position
                bin_x = main_x + perp_dx * bin_offset_distance
                bin_y = main_y + perp_dy * bin_offset_distance
                
                bins.append(BinPosition(
                    x=bin_x,
                    y=bin_y,
                    side='left',
                    bin_number=i,  # Use i as bin number to match stop sequence
                    stop_id=stop_id
                ))
            
            # Add right bin if we still have right bins to allocate
            if i <= right_bins_count:
                # Calculate right side position
                bin_x = main_x - perp_dx * bin_offset_distance
                bin_y = main_y - perp_dy * bin_offset_distance
                
                bins.append(BinPosition(
                    x=bin_x,
                    y=bin_y,
                    side='right',
                    bin_number=i,  # Use i as bin number to match stop sequence
                    stop_id=stop_id
                ))
            
            # Only create a stop if it has bins
            if bins:
                stops.append(StopPosition(
                    stop_id=stop_id,
                    name=stop_name,
                    main_x=main_x,
                    main_y=main_y,
                    bins=bins,
                    distance_from_start=distance_from_start
                ))
        
        return stops
    
    def export_coordinates_for_map(self, stops: List[StopPosition]) -> List[Dict]:
        """
        Export stop and bin coordinates in format suitable for map display.
        
        Args:
            stops: List of calculated stop positions
            
        Returns:
            List of dictionaries with stop and bin coordinate data
        """
        export_data = []
        
        for stop in stops:
            # Main stop entry
            stop_data = {
                'stop_id': stop.stop_id,
                'name': stop.name,
                'type': 'stop',
                'x': stop.main_x,
                'y': stop.main_y,
                'distance_from_start': stop.distance_from_start,
                'total_bins': len(stop.bins),
                'left_bins_count': len([b for b in stop.bins if b.side == 'left']),
                'right_bins_count': len([b for b in stop.bins if b.side == 'right'])
            }
            export_data.append(stop_data)
            
            # Individual bin entries
            for bin_pos in stop.bins:
                bin_data = {
                    'stop_id': stop.stop_id,
                    'name': f"{stop.name} - {bin_pos.side.title()} Bin {bin_pos.bin_number}",
                    'type': 'bin',
                    'side': bin_pos.side,
                    'bin_number': bin_pos.bin_number,
                    'x': bin_pos.x,
                    'y': bin_pos.y,
                    'parent_stop_x': stop.main_x,
                    'parent_stop_y': stop.main_y
                }
                export_data.append(bin_data)
        
        return export_data
    
    def calculate_path_orientation(self, from_x: float, from_y: float, 
                                 to_x: float, to_y: float) -> str:
        """
        Calculate the primary orientation of a path between two points.
        
        Returns:
            String direction: 'north', 'south', 'east', 'west', etc.
        """
        dx = to_x - from_x
        dy = to_y - from_y
        
        if dx == 0 and dy == 0:
            return 'north'  # Default
        
        # Calculate angle in radians
        angle = math.atan2(dy, dx)
        
        # Convert to degrees
        degrees = math.degrees(angle)
        
        # Normalize to 0-360
        if degrees < 0:
            degrees += 360
        
        # Map to cardinal and intercardinal directions
        if 337.5 <= degrees or degrees < 22.5:
            return 'east'
        elif 22.5 <= degrees < 67.5:
            return 'southeast'
        elif 67.5 <= degrees < 112.5:
            return 'south'
        elif 112.5 <= degrees < 157.5:
            return 'southwest'
        elif 157.5 <= degrees < 202.5:
            return 'west'
        elif 202.5 <= degrees < 247.5:
            return 'northwest'
        elif 247.5 <= degrees < 292.5:
            return 'north'
        elif 292.5 <= degrees < 337.5:
            return 'northeast'
        else:
            return 'north'
    
    def validate_positions(self, stops: List[StopPosition], 
                          min_spacing: float = 1.0) -> List[str]:
        """
        Validate calculated positions for overlaps and issues.
        
        Returns:
            List of warning messages
        """
        warnings = []
        
        # Check for stop overlaps
        for i, stop1 in enumerate(stops):
            for j, stop2 in enumerate(stops[i+1:], i+1):
                distance = math.sqrt(
                    (stop1.main_x - stop2.main_x)**2 + 
                    (stop1.main_y - stop2.main_y)**2
                )
                if distance < min_spacing:
                    warnings.append(
                        f"Stops {stop1.stop_id} and {stop2.stop_id} are too close: {distance:.2f}m"
                    )
        
        # Check for bin overlaps within each stop
        for stop in stops:
            for i, bin1 in enumerate(stop.bins):
                for bin2 in stop.bins[i+1:]:
                    distance = math.sqrt(
                        (bin1.x - bin2.x)**2 + (bin1.y - bin2.y)**2
                    )
                    if distance < 0.5:  # Bins should be at least 0.5m apart
                        warnings.append(
                            f"Bins in {stop.stop_id} overlap: {distance:.2f}m apart"
                        )
        
        return warnings


def example_usage():
    """Example of how to use the StopPositionCalculator"""
    calculator = StopPositionCalculator()
    
    # Example zone data
    zone_data = {
        'from_zone': 'A',
        'to_zone': 'B', 
        'from_x': 100,
        'from_y': 100,
        'to_x': 150,
        'to_y': 100,
        'magnitude': 50,  # 50 meters
        'direction': 'east'
    }
    
    # Calculate stops with 2 left bins and 2 right bins
    stops = calculator.calculate_equal_interval_stops(
        from_point=(100, 100),
        to_point=(150, 100),
        total_distance=50,
        left_bins_count=2,
        right_bins_count=2,
        bin_offset_distance=2.0,
        zone_name="A_to_B"
    )
    
    # Export for map display
    map_data = calculator.export_coordinates_for_map(stops)
    
    
    for stop in stops:

        for bin_pos in stop.bins:
            print(f"    {bin_pos.side.title()} Bin {bin_pos.bin_number}: ({bin_pos.x:.2f}, {bin_pos.y:.2f})")
        print()


if __name__ == "__main__":
    example_usage()
