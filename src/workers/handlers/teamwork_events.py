"""Teamwork event handler."""
from datetime import datetime, timezone
from typing import Dict, Any

from src.db.models import Task
from src.db.interface import DatabaseInterface
from src.connectors.teamwork_client import TeamworkClient
from src.logging_conf import logger


class TeamworkEventHandler:
    """Handler for Teamwork webhook events."""
    
    def __init__(self, db: DatabaseInterface):
        self.db = db
        self.client = TeamworkClient()
    
    def handle_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """
        Handle a Teamwork event.
        
        Args:
            event_type: Type of event (e.g., "task.created", "task.updated")
            payload: Event payload
        """
        logger.info(f"Handling Teamwork event: {event_type}")
        
        # Extract task ID from payload
        task_id = self._extract_task_id(payload)
        if not task_id:
            logger.warning(f"No task ID found in payload for event {event_type}")
            return
        
        # Handle deletion events
        if "deleted" in event_type.lower() or payload.get("deleted"):
            self.db.mark_task_deleted(task_id)
            return
        
        # Fetch full task data from API
        task_data = self.client.get_task_by_id(task_id)
        if not task_data:
            logger.warning(f"Could not fetch task {task_id} from Teamwork API")
            # Use payload data as fallback
            task_data = payload.get("task", payload)
        
        # Convert to Task model
        task = self._parse_task(task_data)
        
        # Store in database
        self.db.upsert_task(task)
    
    def _extract_task_id(self, payload: Dict[str, Any]) -> str:
        """Extract task ID from various payload formats."""
        # Try different payload structures
        if "task" in payload:
            return str(payload["task"].get("id", ""))
        if "id" in payload:
            return str(payload["id"])
        if "taskId" in payload:
            return str(payload["taskId"])
        if "task_id" in payload:
            return str(payload["task_id"])
        return ""
    
    def _parse_task(self, data: Dict[str, Any]) -> Task:
        """Parse Teamwork task data into Task model."""
        task_id = str(data.get("id", ""))
        
        # Parse dates
        updated_at = None
        if data.get("updatedAt"):
            try:
                updated_at = datetime.fromisoformat(data["updatedAt"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        
        due_at = None
        if data.get("dueDate"):
            try:
                due_at = datetime.fromisoformat(data["dueDate"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        
        # Parse tags
        tags = []
        if data.get("tags"):
            if isinstance(data["tags"], list):
                tags = [tag.get("name", str(tag)) if isinstance(tag, dict) else str(tag) 
                       for tag in data["tags"]]
        
        # Parse assignees
        assignees = []
        if data.get("assignees"):
            if isinstance(data["assignees"], list):
                assignees = [
                    assignee.get("fullName", assignee.get("name", str(assignee)))
                    if isinstance(assignee, dict) else str(assignee)
                    for assignee in data["assignees"]
                ]
        
        # Check if deleted/completed
        deleted = data.get("deleted", False) or data.get("completed", False)
        deleted_at = None
        if deleted and data.get("completedAt"):
            try:
                deleted_at = datetime.fromisoformat(data["completedAt"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        
        return Task(
            task_id=task_id,
            project_id=str(data.get("projectId", "")) if data.get("projectId") else None,
            title=data.get("name") or data.get("title"),
            description=data.get("description"),
            status=data.get("status") or data.get("state"),
            tags=tags,
            assignees=assignees,
            due_at=due_at,
            updated_at=updated_at or datetime.now(timezone.utc),
            deleted=deleted,
            deleted_at=deleted_at,
            source_links={"teamwork_url": data.get("url", "")} if data.get("url") else {}
        )

