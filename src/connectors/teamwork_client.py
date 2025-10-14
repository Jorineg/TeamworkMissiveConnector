"""Teamwork API client."""
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import requests
from requests.auth import HTTPBasicAuth

from src import settings
from src.logging_conf import logger


class TeamworkClient:
    """Client for Teamwork API."""
    
    def __init__(self):
        self.base_url = settings.TEAMWORK_BASE_URL
        self.api_key = settings.TEAMWORK_API_KEY
        self.auth = HTTPBasicAuth(self.api_key, "")
        self.session = requests.Session()
        self.session.auth = self.auth
    
    def get_tasks_updated_since(self, since: datetime, include_deleted: bool = True) -> List[Dict[str, Any]]:
        """
        Get all tasks updated since a given datetime.
        
        Args:
            since: Datetime to fetch tasks from
            include_deleted: Whether to include deleted/completed tasks
        
        Returns:
            List of task dictionaries
        """
        tasks = []
        page = 1
        page_size = 100
        
        # Format datetime for Teamwork API (YYYYMMDDHHMMSS)
        updated_after = since.strftime("%Y%m%d%H%M%S")
        
        while True:
            try:
                params = {
                    "page": page,
                    "pageSize": page_size,
                    "updatedAfterDate": updated_after,
                    "includeCompletedTasks": "true" if include_deleted else "false",
                    "includeArchivedProjects": "true" if include_deleted else "false"
                }
                
                response = self._request("GET", "/projects/api/v3/tasks.json", params=params)
                
                if response and "tasks" in response:
                    batch = response["tasks"]
                    tasks.extend(batch)
                    
                    logger.info(f"Fetched {len(batch)} tasks from Teamwork (page {page})")
                    
                    # Check if there are more pages
                    if len(batch) < page_size:
                        break
                    page += 1
                else:
                    break
            
            except Exception as e:
                logger.error(f"Error fetching tasks from Teamwork: {e}", exc_info=True)
                break
        
        return tasks
    
    def get_task_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a single task by ID."""
        try:
            response = self._request("GET", f"/projects/api/v3/tasks/{task_id}.json")
            if response and "task" in response:
                return response["task"]
        except Exception as e:
            logger.error(f"Error fetching task {task_id} from Teamwork: {e}", exc_info=True)
        return None
    
    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> Optional[Dict[str, Any]]:
        """
        Make an API request with retry logic.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            json_data: JSON body
            retry_count: Current retry attempt
        
        Returns:
            Response JSON or None
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers={"Accept": "application/json"},
                timeout=30
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.warning(f"Rate limited by Teamwork API. Waiting {retry_after}s...")
                time.sleep(retry_after)
                return self._request(method, endpoint, params, json_data, retry_count)
            
            # Handle server errors with exponential backoff
            if response.status_code >= 500 and retry_count < 3:
                wait_time = 2 ** retry_count
                logger.warning(f"Server error {response.status_code}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                return self._request(method, endpoint, params, json_data, retry_count + 1)
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Teamwork API request failed: {e}", exc_info=True)
            
            # Retry on connection errors
            if retry_count < 3 and isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                wait_time = 2 ** retry_count
                logger.info(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)
                return self._request(method, endpoint, params, json_data, retry_count + 1)
            
            return None

