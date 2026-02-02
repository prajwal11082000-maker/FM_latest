from typing import Dict, List, Optional
from .client import APIClient
from utils.logger import setup_logger


class TasksAPI:
    def __init__(self, client: APIClient):
        self.client = client
        self.logger = setup_logger('tasks_api')

    def list_tasks(self, params: Dict = None) -> Dict:
        """Get list of all tasks"""
        return self.client.get('/tasks/', params=params)

    def get_task(self, task_id: int) -> Dict:
        """Get specific task by ID"""
        return self.client.get(f'/tasks/{task_id}/')

    def create_task(self, task_data: Dict) -> Dict:
        """Create new task"""
        return self.client.post('/tasks/', task_data)

    def update_task(self, task_id: int, task_data: Dict) -> Dict:
        """Update existing task"""
        return self.client.put(f'/tasks/{task_id}/', task_data)

    def delete_task(self, task_id: int) -> Dict:
        """Delete task"""
        return self.client.delete(f'/tasks/{task_id}/')

    def start_task(self, task_id: int) -> Dict:
        """Start a task"""
        return self.client.post(f'/tasks/{task_id}/start_task/')

    def complete_task(self, task_id: int) -> Dict:
        """Complete a task"""
        return self.client.post(f'/tasks/{task_id}/complete_task/')

    def get_task_summary(self) -> Dict:
        """Get task summary statistics"""
        return self.client.get('/tasks/task_summary/')