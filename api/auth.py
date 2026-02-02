from typing import Dict, Optional
from .client import APIClient
from utils.logger import setup_logger


class AuthAPI:
    def __init__(self, client: APIClient):
        self.client = client
        self.logger = setup_logger('auth_api')

    def login(self, username: str, password: str) -> Dict:
        """Authenticate user and get tokens"""
        try:
            response = self.client.post('/auth/login/', {
                'username': username,
                'password': password
            })

            if 'error' not in response:
                # Extract tokens
                access_token = response.get('access')
                refresh_token = response.get('refresh')

                if access_token:
                    self.client.set_auth_token(access_token, refresh_token)
                    self.logger.info(f"User {username} logged in successfully")
                    return {
                        'success': True,
                        'user': response.get('user', {}),
                        'access_token': access_token,
                        'refresh_token': refresh_token
                    }

            return {'success': False, 'error': response.get('error', 'Login failed')}

        except Exception as e:
            self.logger.error(f"Login error: {e}")
            return {'success': False, 'error': str(e)}

    def logout(self) -> bool:
        """Logout user and clear tokens"""
        try:
            if self.client.refresh_token:
                # Call logout endpoint if available
                self.client.post('/auth/logout/', {
                    'refresh_token': self.client.refresh_token
                })

            self.client.clear_auth()
            self.logger.info("User logged out successfully")
            return True

        except Exception as e:
            self.logger.error(f"Logout error: {e}")
            self.client.clear_auth()  # Clear tokens anyway
            return False

    def refresh_token(self) -> bool:
        """Refresh access token"""
        return self.client._refresh_access_token()

    def get_current_user(self) -> Optional[Dict]:
        """Get current authenticated user info"""
        if not self.client.is_authenticated():
            return None

        try:
            response = self.client.get('/auth/user/')
            if 'error' not in response:
                return response
            return None
        except Exception as e:
            self.logger.error(f"Error getting current user: {e}")
            return None