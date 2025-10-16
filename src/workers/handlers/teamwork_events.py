"""Teamwork event handler."""
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from src.db.models import Task
from src.db.interface import DatabaseInterface
from src.connectors.teamwork_client import TeamworkClient
from src.connectors.teamwork_mappings import get_mappings
from src.logging_conf import logger


class TeamworkEventHandler:
    """Handler for Teamwork webhook events."""
    
    def __init__(self, db: DatabaseInterface):
        self.db = db
        self.client = TeamworkClient()
    
    def process_event(self, event_type: str, payload: Dict[str, Any]) -> Optional[Task]:
        """
        Process a Teamwork event and return a Task object.
        
        Args:
            event_type: Type of event (e.g., "task.created", "task.updated")
            payload: Event payload
        
        Returns:
            Task object to be batch upserted, or None
        """
        logger.info(f"Processing Teamwork event: {event_type}")
        
        # Extract task ID from payload
        task_id = self._extract_task_id(payload)
        if not task_id:
            logger.warning(f"No task ID found in payload for event {event_type}")
            return None
        
        # Handle deletion events
        if "deleted" in event_type.lower() or payload.get("deleted"):
            self.db.mark_task_deleted(task_id)
            return None
        
        # Fetch full task data from API
        task_data = self.client.get_task_by_id(task_id)
        if not task_data:
            logger.warning(f"Could not fetch task {task_id} from Teamwork API")
            # Use payload data as fallback
            task_data = payload.get("task", payload)
        
        # Convert to Task model
        task = self._parse_task(task_data)
        return task
    
    def handle_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """
        Handle a Teamwork event (legacy method for backwards compatibility).
        
        Args:
            event_type: Type of event (e.g., "task.created", "task.updated")
            payload: Event payload
        """
        task = self.process_event(event_type, payload)
        if task:
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
        
        # Parse tags - replace IDs with string values
        mappings = get_mappings()
        tags = []
        if data.get("tags"):
            if isinstance(data["tags"], list):
                for tag in data["tags"]:
                    if isinstance(tag, dict):
                        # Try to get name first, fallback to ID lookup
                        if tag.get("name"):
                            tags.append(tag["name"])
                        elif tag.get("id") is not None:
                            tag_name = mappings.get_tag_name(tag["id"])
                            tags.append(tag_name)
                    else:
                        # Assume it's an ID
                        tag_name = mappings.get_tag_name(tag)
                        tags.append(tag_name)
        
        # Parse assignees - replace IDs with string values
        assignees = []
        if data.get("assignees"):
            if isinstance(data["assignees"], list):
                for assignee in data["assignees"]:
                    if isinstance(assignee, dict):
                        # Try to get name first, fallback to ID lookup
                        if assignee.get("fullName") or assignee.get("name"):
                            assignees.append(assignee.get("fullName") or assignee.get("name"))
                        elif assignee.get("id") is not None:
                            person_name = mappings.get_person_name(assignee["id"])
                            assignees.append(person_name)
                    else:
                        # Assume it's an ID
                        person_name = mappings.get_person_name(assignee)
                        assignees.append(person_name)
        
        # Parse createdBy - replace ID with string value
        created_by = None
        if data.get("createdBy"):
            created_by_data = data["createdBy"]
            if isinstance(created_by_data, dict):
                # Try to get name first, fallback to ID lookup
                if created_by_data.get("fullName") or created_by_data.get("name"):
                    created_by = created_by_data.get("fullName") or created_by_data.get("name")
                elif created_by_data.get("id") is not None:
                    created_by = mappings.get_person_name(created_by_data["id"])
            else:
                # Assume it's an ID
                created_by = mappings.get_person_name(created_by_data)
        
        # Parse updatedBy - replace ID with string value
        updated_by = None
        if data.get("updatedBy"):
            updated_by_data = data["updatedBy"]
            if isinstance(updated_by_data, dict):
                # Try to get name first, fallback to ID lookup
                if updated_by_data.get("fullName") or updated_by_data.get("name"):
                    updated_by = updated_by_data.get("fullName") or updated_by_data.get("name")
                elif updated_by_data.get("id") is not None:
                    updated_by = mappings.get_person_name(updated_by_data["id"])
            else:
                # Assume it's an ID
                updated_by = mappings.get_person_name(updated_by_data)
        
        # Check if deleted/completed
        deleted = data.get("deleted", False) or data.get("completed", False)
        deleted_at = None
        if deleted and data.get("completedAt"):
            try:
                deleted_at = datetime.fromisoformat(data["completedAt"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        
        # Project ID may not be present; derive via tasklist if available
        project_id = None
        if data.get("projectId"):
            project_id = str(data.get("projectId"))
        elif data.get("tasklistId"):
            try:
                tl = self.client.get_tasklist_by_id(str(data.get("tasklistId")))
                if tl and tl.get("project") and tl["project"].get("id"):
                    project_id = str(tl["project"]["id"])
            except Exception:
                pass

        # Build a web URL if not provided
        source_links = {}
        if data.get("url"):
            source_links["teamwork_url"] = data.get("url")
        else:
            source_links["teamwork_url"] = self.client.build_task_web_url(task_id)

        return Task(
            task_id=task_id,
            project_id=project_id,
            title=data.get("name") or data.get("title"),
            description=data.get("description"),
            status=data.get("status") or data.get("state"),
            tags=tags,
            assignees=assignees,
            created_by=created_by,
            updated_by=updated_by,
            due_at=due_at,
            updated_at=updated_at or datetime.now(timezone.utc),
            deleted=deleted or bool(data.get("deletedAt")),
            deleted_at=deleted_at,
            source_links=source_links,
            raw=data
        )

