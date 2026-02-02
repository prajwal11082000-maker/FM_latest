from typing import Dict, List, Optional
from .client import APIClient
from utils.logger import setup_logger


class UsersAPI:
    def __init__(self, client: APIClient):
        self.client = client
        self.logger = setup_logger('users_api')

    def list_users(self, params: Dict = None) -> Dict:
        """Get list of all users"""
        return self.client.get('/user-management/', params=params)

    def get_user(self, user_id: int) -> Dict:
        """Get specific user by ID"""
        return self.client.get(f'/user-management/{user_id}/')

    def create_user(self, user_data: Dict) -> Dict:
        """Create new user"""
        return self.client.post('/user-management/', user_data)

    def update_user(self, user_id: int, user_data: Dict) -> Dict:
        """Update existing user"""
        return self.client.put(f'/user-management/{user_id}/', user_data)

    def delete_user(self, user_id: int) -> Dict:
        """Delete user"""
        return self.client.delete(f'/user-management/{user_id}/')