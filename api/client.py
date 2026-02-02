import requests
import json
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

from config.settings import API_BASE_URL, API_TIMEOUT, RETRY_ATTEMPTS
from utils.logger import setup_logger


class APIClient:
    def __init__(self):
        self.base_url = API_BASE_URL
        self.session = requests.Session()
        self.session.timeout = API_TIMEOUT
        self.access_token = None
        self.refresh_token = None
        self.logger = setup_logger('api_client')

        # Set default headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

    def set_auth_token(self, access_token: str, refresh_token: str = None):
        """Set authentication tokens"""
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.session.headers['Authorization'] = f'Bearer {access_token}'

    def clear_auth(self):
        """Clear authentication tokens"""
        self.access_token = None
        self.refresh_token = None
        if 'Authorization' in self.session.headers:
            del self.session.headers['Authorization']

    def _make_request(self, method: str, endpoint: str, data: Dict = None, params: Dict = None) -> Dict:
        """Make HTTP request with error handling and retries"""
        url = urljoin(self.base_url + '/', endpoint.lstrip('/'))

        for attempt in range(RETRY_ATTEMPTS):
            try:
                if method.upper() == 'GET':
                    response = self.session.get(url, params=params)
                elif method.upper() == 'POST':
                    response = self.session.post(url, json=data, params=params)
                elif method.upper() == 'PUT':
                    response = self.session.put(url, json=data, params=params)
                elif method.upper() == 'DELETE':
                    response = self.session.delete(url, params=params)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                # Handle 401 - try to refresh token
                if response.status_code == 401 and self.refresh_token:
                    if self._refresh_access_token():
                        # Retry the request with new token
                        continue
                    else:
                        # Refresh failed, clear auth
                        self.clear_auth()
                        return {'error': 'Authentication failed', 'status_code': 401}

                # Check if request was successful
                if response.status_code < 400:
                    try:
                        return response.json() if response.content else {}
                    except json.JSONDecodeError:
                        return {'data': response.text}
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    self.logger.error(f"API Error for {method} {url}: {error_msg}")
                    return {
                        'error': error_msg,
                        'status_code': response.status_code
                    }

            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Request attempt {attempt + 1} failed: {e}")
                if attempt == RETRY_ATTEMPTS - 1:
                    return {'error': f'Network error: {str(e)}', 'status_code': 0}

        return {'error': 'Max retry attempts exceeded', 'status_code': 0}

    def _refresh_access_token(self) -> bool:
        """Refresh the access token using refresh token"""
        if not self.refresh_token:
            return False

        try:
            # Temporarily remove auth header for refresh request
            auth_header = self.session.headers.get('Authorization')
            if auth_header:
                del self.session.headers['Authorization']

            response = self.session.post(
                urljoin(self.base_url + '/', 'auth/refresh/'),
                json={'refresh': self.refresh_token}
            )

            if response.status_code == 200:
                data = response.json()
                new_access_token = data.get('access')
                if new_access_token:
                    self.set_auth_token(new_access_token, self.refresh_token)
                    self.logger.info("Access token refreshed successfully")
                    return True

            self.logger.error("Failed to refresh access token")
            return False

        except Exception as e:
            self.logger.error(f"Error refreshing token: {e}")
            return False

    def get(self, endpoint: str, params: Dict = None) -> Dict:
        """Make GET request"""
        return self._make_request('GET', endpoint, params=params)

    def post(self, endpoint: str, data: Dict = None, params: Dict = None) -> Dict:
        """Make POST request"""
        return self._make_request('POST', endpoint, data=data, params=params)

    def put(self, endpoint: str, data: Dict = None, params: Dict = None) -> Dict:
        """Make PUT request"""
        return self._make_request('PUT', endpoint, data=data, params=params)

    def delete(self, endpoint: str, params: Dict = None) -> Dict:
        """Make DELETE request"""
        return self._make_request('DELETE', endpoint, params=params)

    def is_authenticated(self) -> bool:
        """Check if client is authenticated"""
        return self.access_token is not None

    def test_connection(self) -> bool:
        """Test API connection"""
        if not self.base_url:
            return False
            
        try:
            # Override timeout just for connection test
            original_timeout = self.session.timeout
            self.session.timeout = 2  # 2 second timeout
            
            response = self.get('/')
            result = 'error' not in response
            
            # Restore original timeout
            self.session.timeout = original_timeout
            return result
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            self.logger.debug("API connection failed (server not available)")
            return False
        except Exception as e:
            self.logger.error(f"API connection test failed: {e}")
            return False