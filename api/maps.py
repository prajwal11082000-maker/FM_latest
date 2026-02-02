from typing import Dict, List, Optional
from .client import APIClient
from utils.logger import setup_logger


class MapsAPI:
    def __init__(self, client: APIClient):
        self.client = client
        self.logger = setup_logger('maps_api')

    def list_maps(self, params: Dict = None) -> Dict:
        """Get list of all maps"""
        return self.client.get('/maps/', params=params)

    def get_map(self, map_id: int) -> Dict:
        """Get specific map by ID"""
        return self.client.get(f'/maps/{map_id}/')

    def create_map(self, map_data: Dict) -> Dict:
        """Create new map"""
        return self.client.post('/maps/', map_data)

    def update_map(self, map_id: int, map_data: Dict) -> Dict:
        """Update existing map"""
        return self.client.put(f'/maps/{map_id}/', map_data)

    def delete_map(self, map_id: int) -> Dict:
        """Delete map"""
        return self.client.delete(f'/maps/{map_id}/')

    # Zone Connections
    def list_zone_connections(self, map_id: int) -> Dict:
        """Get zone connections for a map"""
        return self.client.get(f'/maps/{map_id}/connections/')

    def create_zone_connection(self, map_id: int, connection_data: Dict) -> Dict:
        """Create zone connection"""
        return self.client.post(f'/maps/{map_id}/connections/', connection_data)

    def update_zone_connection(self, map_id: int, connection_id: int, connection_data: Dict) -> Dict:
        """Update zone connection"""
        return self.client.put(f'/maps/{map_id}/connections/{connection_id}/', connection_data)

    def delete_zone_connection(self, map_id: int, connection_id: int) -> Dict:
        """Delete zone connection"""
        return self.client.delete(f'/maps/{map_id}/connections/{connection_id}/')

    def generate_stops(self, map_id: int, connection_id: int, stop_data: Dict) -> Dict:
        """Generate stops for a zone connection"""
        return self.client.post(f'/maps/{map_id}/connections/{connection_id}/generate_stops/', stop_data)
    
    def calculate_bin_positions(self, map_id: int, connection_id: int, bin_config: Dict) -> Dict:
        """Calculate bin positions using the custom bin calculator"""
        try:
            from bin_calculator_integration import BinCalculatorIntegration
            integration = BinCalculatorIntegration()
            return integration.calculate_bins_for_zone(bin_config)
        except ImportError:
            self.logger.error("Bin calculator integration not available")
            return {'error': 'Bin calculator not available'}
    
    def generate_stops_with_bins(self, map_id: int, connection_id: int, zone_data: Dict) -> Dict:
        """Generate stops with automatic bin positioning"""
        try:
            from bin_calculator_integration import BinCalculatorIntegration
            integration = BinCalculatorIntegration()
            
            # Add connection_id to zone_data
            zone_data['connection_id'] = connection_id
            
            # Generate stops data with bin positions
            stops_data = integration.generate_stops_data_for_api(zone_data)
            
            # Send to the API
            result = self.generate_stops(map_id, connection_id, stops_data)
            return result
            
        except ImportError:
            self.logger.error("Bin calculator integration not available")
            return {'error': 'Bin calculator not available'}
        except Exception as e:
            self.logger.error(f"Error generating stops with bins: {str(e)}")
            return {'error': f'Failed to generate stops: {str(e)}'}
    
    def generate_exact_stops(self, map_id: int, connection_id: int, zone_data: Dict) -> Dict:
        """Generate stops with EXACT bin positioning matching user requirements"""
        try:
            from exact_bin_integration import ExactBinIntegration
            integration = ExactBinIntegration()
            
            # Add connection_id to zone_data
            zone_data['connection_id'] = connection_id
            
            # Generate UI result for success dialog
            ui_result = integration.calculate_bins_for_ui(zone_data)
            
            # Generate API stops data
            api_stops = integration.generate_stops_data_for_api(zone_data)
            
            # Send to the API
            api_result = self.generate_stops(map_id, connection_id, api_stops)
            
            # Return combined result for UI
            return {
                'success': True,
                'api_result': api_result,
                'ui_data': ui_result,
                'stops_generated': len(api_stops['stops']),
                'message': ui_result['message']
            }
            
        except ImportError:
            self.logger.error("Exact bin calculator integration not available")
            return {'error': 'Exact bin calculator not available'}
        except Exception as e:
            self.logger.error(f"Error generating exact stops: {str(e)}")
            return {'error': f'Failed to generate exact stops: {str(e)}'}
    
    def calculate_exact_positions_only(self, zone_data: Dict) -> Dict:
        """Calculate exact bin positions without sending to API (for preview)"""
        try:
            from exact_bin_integration import ExactBinIntegration
            integration = ExactBinIntegration()
            
            # Generate UI result
            result = integration.calculate_bins_for_ui(zone_data)
            return result
            
        except ImportError:
            self.logger.error("Exact bin calculator integration not available")
            return {'error': 'Exact bin calculator not available'}
        except Exception as e:
            self.logger.error(f"Error calculating exact positions: {str(e)}")
            return {'error': f'Failed to calculate positions: {str(e)}'}

    # Stop Groups
    def list_stop_groups(self, map_id: int) -> Dict:
        """Get stop groups for a map"""
        return self.client.get(f'/maps/{map_id}/stop-groups/')

    def create_stop_group(self, map_id: int, group_data: Dict) -> Dict:
        """Create stop group"""
        return self.client.post(f'/maps/{map_id}/stop-groups/', group_data)

    def update_stop_group(self, map_id: int, group_id: int, group_data: Dict) -> Dict:
        """Update stop group"""
        return self.client.put(f'/maps/{map_id}/stop-groups/{group_id}/', group_data)

    def delete_stop_group(self, map_id: int, group_id: int) -> Dict:
        """Delete stop group"""
        return self.client.delete(f'/maps/{map_id}/stop-groups/{group_id}/')