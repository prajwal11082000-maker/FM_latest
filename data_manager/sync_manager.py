from typing import Dict, List, Any, Optional
from datetime import datetime
import json

from api.client import APIClient
from .csv_handler import CSVHandler
from utils.logger import setup_logger


class SyncManager:
    def __init__(self, api_client: APIClient, csv_handler: CSVHandler):
        self.api_client = api_client
        self.csv_handler = csv_handler
        self.logger = setup_logger('sync_manager')

        # Sync mapping: CSV type -> API endpoint
        self.sync_mapping = {
            'devices': '/devices/',
            'tasks': '/tasks/',
            'users': '/user-management/',
            'maps': '/maps/',
        }

    def sync_all_data(self) -> bool:
        """Sync all data types from API to CSV"""
        if not self.api_client.is_authenticated():
            self.logger.warning("Cannot sync: not authenticated")
            return False

        success_count = 0
        total_count = len(self.sync_mapping)

        for data_type in self.sync_mapping:
            if self.sync_data_type(data_type):
                success_count += 1
            else:
                self.logger.error(f"Failed to sync {data_type}")

        # Also sync zones and stops for each map
        if self.sync_zones_and_stops():
            success_count += 1
            total_count += 1

        self.logger.info(f"Sync completed: {success_count}/{total_count} successful")
        return success_count == total_count

    def sync_data_type(self, data_type: str) -> bool:
        """Sync specific data type from API to CSV"""
        endpoint = self.sync_mapping.get(data_type)
        if not endpoint:
            return False

        try:
            response = self.api_client.get(endpoint)

            if 'error' in response:
                self.logger.error(f"API error syncing {data_type}: {response['error']}")
                return False

            # Handle different response formats
            if 'results' in response:
                data = response['results']
            elif isinstance(response, list):
                data = response
            else:
                data = [response] if response else []

            # Convert API data to CSV format
            csv_data = self.convert_api_to_csv(data_type, data)

            # Write to CSV
            success = self.csv_handler.write_csv(data_type, csv_data)

            if success:
                self.logger.info(f"Synced {len(csv_data)} {data_type} records")

            return success

        except Exception as e:
            self.logger.error(f"Error syncing {data_type}: {e}")
            return False

    def sync_zones_and_stops(self) -> bool:
        """Sync zones and stops for all maps"""
        try:
            # Get all maps first
            maps_data = self.csv_handler.read_csv('maps')
            all_zones = []
            all_stops = []
            all_stop_groups = []

            for map_data in maps_data:
                map_id = map_data.get('id')
                if not map_id:
                    continue

                # Get zone connections for this map
                zones_response = self.api_client.get(f'/maps/{map_id}/connections/')
                if 'error' not in zones_response:
                    zones = zones_response if isinstance(zones_response, list) else zones_response.get('results', [])
                    for zone in zones:
                        zone['map_id'] = map_id
                        all_zones.append(zone)

                        # Get stops for this zone connection
                        zone_id = zone.get('id')
                        if zone_id:
                            stops_response = self.api_client.get(f'/maps/{map_id}/connections/{zone_id}/stops/')
                            if 'error' not in stops_response:
                                stops = stops_response if isinstance(stops_response, list) else stops_response.get(
                                    'results', [])
                                for stop in stops:
                                    stop['zone_connection_id'] = zone_id
                                    stop['map_id'] = map_id
                                    all_stops.append(stop)

                # Get stop groups for this map
                groups_response = self.api_client.get(f'/maps/{map_id}/stop-groups/')
                if 'error' not in groups_response:
                    groups = groups_response if isinstance(groups_response, list) else groups_response.get('results',
                                                                                                           [])
                    for group in groups:
                        group['map_id'] = map_id
                        # Convert stops list to comma-separated string
                        if 'stops' in group and isinstance(group['stops'], list):
                            group['stop_ids'] = ','.join(str(s.get('id', '')) for s in group['stops'])
                        all_stop_groups.append(group)

            # Write all zones, stops, and stop groups
            zones_success = self.csv_handler.write_csv('zones', all_zones)
            stops_success = self.csv_handler.write_csv('stops', all_stops)
            groups_success = self.csv_handler.write_csv('stop_groups', all_stop_groups)

            self.logger.info(
                f"Synced {len(all_zones)} zones, {len(all_stops)} stops, {len(all_stop_groups)} stop groups")

            return zones_success and stops_success and groups_success

        except Exception as e:
            self.logger.error(f"Error syncing zones and stops: {e}")
            return False

    def convert_api_to_csv(self, data_type: str, api_data: List[Dict]) -> List[Dict]:
        """Convert API data format to CSV format"""
        csv_data = []

        for item in api_data:
            csv_item = {}

            if data_type == 'devices':
                csv_item = {
                    'id': item.get('id'),
                    'device_id': item.get('device_id'),
                    'device_name': item.get('device_name'),
                    'device_type': item.get('device_type'),
                    'status': item.get('status'),
                    'battery_level': item.get('battery_level', 100),
                    'location': item.get('location', ''),
                    'created_at': item.get('created_at'),
                    'updated_at': item.get('updated_at')
                }

            elif data_type == 'tasks':
                csv_item = {
                    'id': item.get('id'),
                    'task_id': item.get('task_id'),
                    'task_name': item.get('task_name'),
                    'task_type': item.get('task_type'),
                    'status': item.get('status'),
                    'priority': item.get('priority'),
                    # Backward compatible single assignment
                    'assigned_device_id': item.get('assigned_device', {}).get('id') if item.get('assigned_device') else '',
                    # Multi-assignment support: accept either 'assigned_devices' (list of objects) or 'assigned_device_ids' (list)
                    'assigned_device_ids': ','.join([
                        str(d.get('id')) if isinstance(d, dict) else str(d)
                    for d in (item.get('assigned_devices') or item.get('assigned_device_ids') or [])]) if (
                        isinstance(item.get('assigned_devices') or item.get('assigned_device_ids'), (list, tuple))
                    ) else '',
                    'assigned_user_id': item.get('assigned_user', {}).get('id') if item.get('assigned_user') else '',
                    'description': item.get('description', ''),
                    'from_location': item.get('from_location', ''),
                    'to_location': item.get('to_location', ''),
                    'estimated_duration': item.get('estimated_duration'),
                    'actual_duration': item.get('actual_duration'),
                    'created_at': item.get('created_at'),
                    'started_at': item.get('started_at'),
                    'completed_at': item.get('completed_at')
                }

            elif data_type == 'users':
                csv_item = {
                    'id': item.get('id'),
                    'username': item.get('username'),
                    'email': item.get('email'),
                    'employee_id': item.get('profile', {}).get('employee_id') if item.get('profile') else '',
                    'is_active': item.get('is_active'),
                    'created_at': item.get('date_joined')
                }

            elif data_type == 'maps':
                csv_item = {
                    'id': item.get('id'),
                    'name': item.get('name'),
                    'description': item.get('description', ''),
                    'width': item.get('width', 1000),
                    'height': item.get('height', 800),
                    'created_at': item.get('created_at')
                }

            if csv_item:
                csv_data.append(csv_item)

        return csv_data

    def push_to_api(self, data_type: str, data: Dict) -> Optional[Dict]:
        """Push local data to API"""
        endpoint = self.sync_mapping.get(data_type)
        if not endpoint:
            return None

        try:
            # Convert CSV format to API format
            api_data = self.convert_csv_to_api(data_type, data)

            if 'id' in data and data['id']:
                # Update existing record
                response = self.api_client.put(f"{endpoint}{data['id']}/", api_data)
            else:
                # Create new record
                response = self.api_client.post(endpoint, api_data)

            if 'error' not in response:
                self.logger.info(f"Successfully pushed {data_type} to API")
                return response
            else:
                self.logger.error(f"Error pushing {data_type} to API: {response['error']}")
                return None

        except Exception as e:
            self.logger.error(f"Error pushing {data_type} to API: {e}")
            return None

    def convert_csv_to_api(self, data_type: str, csv_data: Dict) -> Dict:
        """Convert CSV data format to API format"""
        api_data = {}

        if data_type == 'devices':
            api_data = {
                'device_id': csv_data.get('device_id'),
                'device_name': csv_data.get('device_name'),
                'device_type': csv_data.get('device_type'),
                'status': csv_data.get('status'),
                'battery_level': int(csv_data.get('battery_level', 100)),
                'location': csv_data.get('location', '')
            }

        elif data_type == 'tasks':
            api_data = {
                'task_name': csv_data.get('task_name'),
                'task_type': csv_data.get('task_type'),
                'status': csv_data.get('status'),
                'priority': csv_data.get('priority'),
                'description': csv_data.get('description', ''),
                'from_location': csv_data.get('from_location', ''),
                'to_location': csv_data.get('to_location', ''),
            }

            # Add optional fields if they exist
            if csv_data.get('assigned_device_id'):
                api_data['assigned_device_id'] = int(csv_data['assigned_device_id'])
            # Multi-assign: send as list of ints if present
            ids_str = str(csv_data.get('assigned_device_ids') or '').strip()
            if ids_str:
                try:
                    api_data['assigned_device_ids'] = [int(s) for s in ids_str.split(',') if str(s).strip()]
                except Exception:
                    # Fallback to raw strings
                    api_data['assigned_device_ids'] = [s.strip() for s in ids_str.split(',') if s.strip()]
            if csv_data.get('assigned_user_id'):
                api_data['assigned_user_id'] = int(csv_data['assigned_user_id'])
            if csv_data.get('estimated_duration'):
                api_data['estimated_duration'] = int(csv_data['estimated_duration'])

        elif data_type == 'maps':
            api_data = {
                'name': csv_data.get('name'),
                'description': csv_data.get('description', ''),
                'width': int(csv_data.get('width', 1000)),
                'height': int(csv_data.get('height', 800))
            }

        # Remove None values
        api_data = {k: v for k, v in api_data.items() if v is not None}

        return api_data

    def get_last_sync_time(self, data_type: str) -> Optional[datetime]:
        """Get last sync time for a data type"""
        # This could be stored in a separate sync metadata file
        # For now, return None to always sync
        return None