"""Teamwork API client."""
import time
from datetime import datetime, timedelta, timezone
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
    
    def get_tasks_updated_since(self, since: datetime, include_completed: bool = True) -> List[Dict[str, Any]]:
        """
        Get all tasks updated since a given datetime.

        Args:
            since: Datetime to fetch tasks from
            include_completed: Whether to include completed tasks

        Returns:
            List of task dictionaries
        """
        return self._get_tasks_with_filter("updatedAfter", since, include_completed)

    def get_tasks_created_since(self, since: datetime, include_completed: bool = True) -> List[Dict[str, Any]]:
            """
            Get all tasks created since a given datetime.

            Args:
                since: Datetime to fetch tasks from
                include_completed: Whether to include completed tasks

            Returns:
                List of task dictionaries
            """
            return self._get_tasks_with_filter("createdAfter", since, include_completed)

    def _get_tasks_with_filter(self, filter_param: str, since: datetime, include_completed: bool = True) -> List[Dict[str, Any]]:
        """
        Get all tasks using a specified filter parameter.

        Args:
            filter_param: The API parameter to use ("updatedAfter" or "createdAfter")
            since: Datetime to fetch tasks from
            include_completed: Whether to include completed tasks

        Returns:
            List of task dictionaries
        """
        tasks = []
        page = 1
        page_size = 100

        # Format datetime for Teamwork API: ISO 8601 in UTC, seconds precision
        # Example: 2025-10-15T22:12:53Z
        since_utc = since.astimezone(timezone.utc) if since.tzinfo else since.replace(tzinfo=timezone.utc)
        filter_value = since_utc.isoformat(timespec="seconds").replace("+00:00", "Z")

        while True:
            try:
                params = {
                    "page": page,
                    "pageSize": page_size,
                    filter_param: filter_value,
                    "includeCompletedTasks": "true" if include_completed else "false",
                    "includeArchivedProjects": "true" if include_completed else "false"
                }

                response = self._request("GET", "/projects/api/v3/tasks.json", params=params)

                if response and "tasks" in response:
                    batch = response["tasks"]
                    tasks.extend(batch)

                    logger.info(f"Fetched {len(batch)} tasks from Teamwork (page {page}, filter: {filter_param})")

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
    
    def get_task_by_id(self, task_id: str, include: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a single task by ID with related resources.
        
        Args:
            task_id: The task ID
            include: Comma-separated list of resources to include. 
                    If None, defaults to "projects,tasklists,tags,users,companies,teams"
        
        Returns:
            Full API response with task and included sections, or None if error
        """
        try:
            # Default to including all related resources we need
            if include is None:
                include = "projects,tasklists,tags,users,companies,teams"
            
            params = {"include": include} if include else {}
            
            response = self._request("GET", f"/projects/api/v3/tasks/{task_id}.json", params=params)
            if response and "task" in response:
                return response  # Returns full response with task and included sections
        except Exception as e:
            logger.error(f"Error fetching task {task_id} from Teamwork: {e}", exc_info=True)
        return None

    def get_tasklist_by_id(self, tasklist_id: str) -> Optional[Dict[str, Any]]:
        """Get a tasklist by ID (used to derive projectId)."""
        try:
            response = self._request("GET", f"/projects/api/v3/tasklists/{tasklist_id}.json")
            if response and "tasklist" in response:
                return response["tasklist"]
        except Exception as e:
            logger.error(f"Error fetching tasklist {tasklist_id} from Teamwork: {e}", exc_info=True)
        return None

    def get_people(self) -> List[Dict[str, Any]]:
        """
        Get all people from Teamwork.
        
        Returns:
            List of people dictionaries
        """
        try:
            response = self._request("GET", "/projects/api/v3/people.json")
            if response and "people" in response:
                logger.info(f"Fetched {len(response['people'])} people from Teamwork")
                return response["people"]
        except Exception as e:
            logger.error(f"Error fetching people from Teamwork: {e}", exc_info=True)
        return []
    
    def get_tags(self) -> List[Dict[str, Any]]:
        """
        Get all tags from Teamwork.
        
        Returns:
            List of tag dictionaries
        """
        try:
            response = self._request("GET", "/projects/api/v3/tags.json")
            if response and "tags" in response:
                logger.info(f"Fetched {len(response['tags'])} tags from Teamwork")
                return response["tags"]
        except Exception as e:
            logger.error(f"Error fetching tags from Teamwork: {e}", exc_info=True)
        return []
    
    def get_companies(self) -> List[Dict[str, Any]]:
        """
        Get all companies from Teamwork.
        
        Returns:
            List of company dictionaries
        """
        companies = []
        page = 1
        page_size = 100
        
        while True:
            try:
                params = {
                    "page": page,
                    "pageSize": page_size
                }
                
                response = self._request("GET", "/projects/api/v3/companies.json", params=params)
                
                if response and "companies" in response:
                    batch = response["companies"]
                    companies.extend(batch)
                    
                    logger.info(f"Fetched {len(batch)} companies from Teamwork (page {page})")
                    
                    # Check if there are more pages
                    if len(batch) < page_size:
                        break
                    page += 1
                else:
                    break
            
            except Exception as e:
                logger.error(f"Error fetching companies from Teamwork: {e}", exc_info=True)
                break
        
        logger.info(f"Total companies fetched: {len(companies)}")
        return companies

    def build_task_web_url(self, task_id: str) -> str:
        """Best-effort construction of a human web URL to the task."""
        base = settings.TEAMWORK_BASE_URL.rstrip("/")
        # Teamwork web UI typically routes via /#/tasks/{id}
        return f"{base}/#/tasks/{task_id}"
    
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
            
            # Surface error body details on client / 4xx errors
            if response.status_code >= 400:
                body_preview: str
                try:
                    body_preview = response.text
                except Exception:
                    body_preview = "<no body>"
                logger.error(
                    f"Teamwork API error {response.status_code} for {url}: {body_preview[:2000]}"
                )
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

