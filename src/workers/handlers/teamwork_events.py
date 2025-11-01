"""Teamwork event handler."""
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from src.db.models import Task
from src.db.interface import DatabaseInterface
from src.connectors.teamwork_client import TeamworkClient
from src.connectors.label_categories import get_label_categories
from src.logging_conf import logger
from src import settings


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
        
        # Fetch full task data from API with included resources
        api_response = self.client.get_task_by_id(task_id)
        if not api_response:
            logger.warning(f"Could not fetch task {task_id} from Teamwork API")
            return None
        
        # Extract task data and included resources
        task_data = api_response.get("task", {})
        included = api_response.get("included", {})
        
        # Check if task should be filtered based on created date
        if self._should_filter_by_date(task_data):
            logger.info(f"Task {task_id} filtered: created before TEAMWORK_PROCESS_AFTER threshold")
            return None
        
        # Convert to Task model using included data
        task = self._parse_task(task_data, included)
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
    
    def _parse_task(self, data: Dict[str, Any], included: Dict[str, Any]) -> Task:
        """
        Parse Teamwork task data into Task model using included resources.
        
        Args:
            data: Task data from API
            included: Included resources (projects, tasklists, users, companies, teams, tags)
        """
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
        
        # Extract project and tasklist info from included data
        project_id = None
        project_name = None
        tasklist_id = None
        tasklist_name = None
        
        # Get tasklist info
        if data.get("tasklist") and isinstance(data["tasklist"], dict):
            tasklist_id = str(data["tasklist"].get("id", ""))
            if tasklist_id and "tasklists" in included:
                tasklist_data = included["tasklists"].get(tasklist_id, {})
                tasklist_name = tasklist_data.get("name")
                
                # Get project from tasklist
                if tasklist_data.get("project") and isinstance(tasklist_data["project"], dict):
                    project_id = str(tasklist_data["project"].get("id", ""))
        
        # Get project info
        if project_id and "projects" in included:
            project_data = included["projects"].get(project_id, {})
            project_name = project_data.get("name")
        
        # Parse tags using included data
        tags = self._resolve_tags(data.get("tags") or [], included.get("tags", {}))
        
        # Categorize tags
        categorized_tags = {}
        if tags:
            label_categories = get_label_categories()
            categorized_tags = label_categories.categorize(tags)
        
        # Parse assignees - handle users, companies, and teams
        assignees = self._resolve_assignees(
            data.get("assignees") or [],
            included.get("users", {}),
            included.get("companies", {}),
            included.get("teams", {})
        )
        
        # Parse createdBy
        created_by = self._resolve_user_name(
            data.get("createdBy"),
            included.get("users", {})
        )
        
        # Parse updatedBy
        updated_by = self._resolve_user_name(
            data.get("updatedBy"),
            included.get("users", {})
        )
        
        # Check if deleted/completed
        deleted = data.get("deleted", False) or data.get("completed", False)
        deleted_at = None
        if deleted and data.get("completedAt"):
            try:
                deleted_at = datetime.fromisoformat(data["completedAt"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        # Build a web URL
        source_links = {}
        if data.get("url"):
            source_links["teamwork_url"] = data.get("url")
        else:
            source_links["teamwork_url"] = self.client.build_task_web_url(task_id)

        return Task(
            task_id=task_id,
            project_id=project_id,
            project_name=project_name,
            tasklist_id=tasklist_id,
            tasklist_name=tasklist_name,
            title=data.get("name") or data.get("title"),
            description=data.get("description"),
            status=data.get("status") or data.get("state"),
            tags=tags,
            categorized_tags=categorized_tags,
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
    
    def _resolve_tags(self, tag_refs: List, tags_included: Dict[str, Any]) -> List[str]:
        """
        Resolve tag IDs to names using included data.
        
        Args:
            tag_refs: List of tag references (can be dicts with id/type or just IDs)
            tags_included: Included tags dictionary
        
        Returns:
            List of tag names
        """
        tags = []
        for tag_ref in tag_refs:
            if isinstance(tag_ref, dict):
                tag_id = str(tag_ref.get("id", ""))
                # Check if tag name is in the included data
                if tag_id and tag_id in tags_included:
                    tag_name = tags_included[tag_id].get("name", tag_id)
                    tags.append(tag_name)
                # Fallback to name in the reference itself
                elif tag_ref.get("name"):
                    tags.append(tag_ref["name"])
            elif tag_ref:
                # Direct ID reference
                tag_id = str(tag_ref)
                if tag_id in tags_included:
                    tags.append(tags_included[tag_id].get("name", tag_id))
                else:
                    tags.append(tag_id)
        return tags
    
    def _resolve_assignees(
        self, 
        assignee_refs: List, 
        users_included: Dict[str, Any],
        companies_included: Dict[str, Any],
        teams_included: Dict[str, Any]
    ) -> List[str]:
        """
        Resolve assignee IDs to names using included data.
        Handles users, companies, and teams.
        
        Args:
            assignee_refs: List of assignee references with id and type
            users_included: Included users dictionary
            companies_included: Included companies dictionary
            teams_included: Included teams dictionary
        
        Returns:
            List of assignee names
        """
        assignees = []
        for assignee_ref in assignee_refs:
            if not isinstance(assignee_ref, dict):
                continue
            
            assignee_id = str(assignee_ref.get("id", ""))
            assignee_type = assignee_ref.get("type", "")
            
            if not assignee_id:
                continue
            
            # Resolve based on type
            if assignee_type == "users" and assignee_id in users_included:
                user = users_included[assignee_id]
                first_name = user.get("firstName", "")
                last_name = user.get("lastName", "")
                full_name = f"{first_name} {last_name}".strip()
                assignees.append(full_name or user.get("email", assignee_id))
            
            elif assignee_type == "companies" and assignee_id in companies_included:
                company = companies_included[assignee_id]
                assignees.append(company.get("name", assignee_id))
            
            elif assignee_type == "teams" and assignee_id in teams_included:
                team = teams_included[assignee_id]
                assignees.append(team.get("name", assignee_id))
            
            else:
                # Fallback - try all dictionaries
                if assignee_id in users_included:
                    user = users_included[assignee_id]
                    first_name = user.get("firstName", "")
                    last_name = user.get("lastName", "")
                    full_name = f"{first_name} {last_name}".strip()
                    assignees.append(full_name or user.get("email", assignee_id))
                elif assignee_id in companies_included:
                    assignees.append(companies_included[assignee_id].get("name", assignee_id))
                elif assignee_id in teams_included:
                    assignees.append(teams_included[assignee_id].get("name", assignee_id))
                else:
                    assignees.append(assignee_id)
        
        return assignees
    
    def _resolve_user_name(self, user_ref: Any, users_included: Dict[str, Any]) -> Optional[str]:
        """
        Resolve a user ID to name using included data.
        
        Args:
            user_ref: User reference (can be ID or dict with id)
            users_included: Included users dictionary
        
        Returns:
            User name or None
        """
        if not user_ref:
            return None
        
        user_id = None
        if isinstance(user_ref, dict):
            user_id = str(user_ref.get("id", ""))
        else:
            user_id = str(user_ref)
        
        if not user_id:
            return None
        
        if user_id in users_included:
            user = users_included[user_id]
            first_name = user.get("firstName", "")
            last_name = user.get("lastName", "")
            full_name = f"{first_name} {last_name}".strip()
            return full_name or user.get("email", user_id)
        
        return user_id
    
    def _should_filter_by_date(self, task_data: Dict[str, Any]) -> bool:
        """
        Check if task should be filtered based on created date.
        
        Args:
            task_data: Task data from API
        
        Returns:
            True if task should be filtered (skipped), False otherwise
        """
        if not settings.TEAMWORK_PROCESS_AFTER:
            return False
        
        try:
            # Parse the threshold date from DD.MM.YYYY format
            threshold_date = datetime.strptime(settings.TEAMWORK_PROCESS_AFTER, "%d.%m.%Y")
            threshold_date = threshold_date.replace(tzinfo=timezone.utc)
            
            # Parse task created date
            created_at_str = task_data.get("createdAt")
            if not created_at_str:
                # If no created date, don't filter
                return False
            
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            
            # Filter if created before threshold
            return created_at < threshold_date
        
        except (ValueError, AttributeError) as e:
            logger.warning(f"Error parsing dates for filtering: {e}")
            return False

