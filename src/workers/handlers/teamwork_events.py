"""Teamwork event handler."""
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Set, Tuple

from src.db.models import Task
from src.db.interface import DatabaseInterface
from src.connectors.teamwork_client import TeamworkClient
from src.logging_conf import logger
from src import settings


# Module-level sync filter cache (shared across instances)
_sync_filters_cache: Tuple[Set[int], Set[int]] = (set(), set())


def refresh_sync_filters(db: DatabaseInterface) -> Tuple[Set[int], Set[int]]:
    """Refresh the sync filters cache from database."""
    global _sync_filters_cache
    if hasattr(db, 'get_sync_filters'):
        _sync_filters_cache = db.get_sync_filters()
        if _sync_filters_cache[0] or _sync_filters_cache[1]:
            logger.info(f"Sync filters loaded: {len(_sync_filters_cache[0])} companies, {len(_sync_filters_cache[1])} projects excluded")
    return _sync_filters_cache


def get_sync_filters() -> Tuple[Set[int], Set[int]]:
    """Get current sync filters (excluded_company_ids, excluded_project_ids)."""
    return _sync_filters_cache


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
        
        # Check if task should be filtered based on sync exclusions
        if self._should_filter_by_exclusion(task_data, included):
            logger.info(f"Task {task_id} filtered: project or company is in sync exclusion list")
            return None
        
        # Upsert all related entities from included resources (in dependency order)
        # This ensures foreign key constraints are satisfied when upserting task
        self._upsert_included_entities(included, task_data)
        
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
    
    def _upsert_included_entities(self, included: Dict[str, Any], task_data: Dict[str, Any]) -> None:
        """
        Upsert all related entities from included resources in dependency order.
        
        Args:
            included: Included resources from API response
            task_data: Task data (to extract specific relationships)
        """
        # Check if db has the new relational methods
        if not hasattr(self.db, 'upsert_tw_company'):
            logger.debug("Database doesn't support relational structure, skipping entity upserts")
            return
        
        # 1. Upsert companies (no dependencies)
        if "companies" in included:
            for company_id, company_data in included["companies"].items():
                try:
                    self.db.upsert_tw_company(company_data)
                except Exception as e:
                    logger.error(f"Failed to upsert company {company_id}: {e}")
        
        # 2. Upsert users (depends on companies)
        if "users" in included:
            for user_id, user_data in included["users"].items():
                try:
                    self.db.upsert_tw_user(user_data)
                except Exception as e:
                    logger.error(f"Failed to upsert user {user_id}: {e}")
        
        # 3. Upsert teams (no dependencies)
        if "teams" in included:
            for team_id, team_data in included["teams"].items():
                try:
                    self.db.upsert_tw_team(team_data)
                    
                    # Link users to teams if available
                    # Note: In Teamwork API, team membership is usually in user.teams
                    # We'll handle this when processing users
                except Exception as e:
                    logger.error(f"Failed to upsert team {team_id}: {e}")
        
        # Link users to their teams
        if "users" in included:
            for user_id, user_data in included["users"].items():
                try:
                    # Extract team IDs from user data
                    team_refs = user_data.get("teams", [])
                    team_ids = []
                    for team_ref in team_refs:
                        if isinstance(team_ref, dict):
                            tid = team_ref.get("id")
                            if tid:
                                team_ids.append(int(tid))
                        elif team_ref:
                            team_ids.append(int(team_ref))
                    
                    if team_ids:
                        self.db.link_user_teams(int(user_id), team_ids)
                except Exception as e:
                    logger.error(f"Failed to link user {user_id} to teams: {e}")
        
        # 4. Upsert tags (may have project dependency)
        if "tags" in included:
            for tag_id, tag_data in included["tags"].items():
                try:
                    self.db.upsert_tw_tag(tag_data)
                except Exception as e:
                    logger.error(f"Failed to upsert tag {tag_id}: {e}")
        
        # 5. Upsert projects (depends on companies and users)
        if "projects" in included:
            for project_id, project_data in included["projects"].items():
                try:
                    self.db.upsert_tw_project(project_data)
                except Exception as e:
                    logger.error(f"Failed to upsert project {project_id}: {e}")
        
        # 6. Upsert tasklists (depends on projects)
        if "tasklists" in included:
            for tasklist_id, tasklist_data in included["tasklists"].items():
                try:
                    self.db.upsert_tw_tasklist(tasklist_data)
                except Exception as e:
                    logger.error(f"Failed to upsert tasklist {tasklist_id}: {e}")
        
        # 7. Link task to tags (will be done after task is upserted)
        # Extract tag IDs from task data
        tag_refs = task_data.get("tags") or []
        tag_ids = []
        for tag_ref in tag_refs:
            if isinstance(tag_ref, dict):
                tid = tag_ref.get("id")
                if tid:
                    tag_ids.append(int(tid))
            elif tag_ref:
                try:
                    tag_ids.append(int(tag_ref))
                except (ValueError, TypeError):
                    pass
        
        # Store for later linking (after task upsert)
        if tag_ids and hasattr(task_data, '__setitem__'):
            task_data["_tag_ids_to_link"] = tag_ids
        
        # 8. Link task to assignees (will be done after task is upserted)
        # Extract assignee user IDs from task data
        assignee_refs = task_data.get("assignees") or []
        assignee_user_ids = []
        for assignee_ref in assignee_refs:
            if isinstance(assignee_ref, dict):
                if assignee_ref.get("type") == "users":
                    uid = assignee_ref.get("id")
                    if uid:
                        try:
                            assignee_user_ids.append(int(uid))
                        except (ValueError, TypeError):
                            pass
        
        # Store for later linking (after task upsert)
        if assignee_user_ids and hasattr(task_data, '__setitem__'):
            task_data["_assignee_user_ids_to_link"] = assignee_user_ids
    
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
    
    def _should_filter_by_exclusion(self, task_data: Dict[str, Any], included: Dict[str, Any]) -> bool:
        """
        Check if task should be filtered based on sync exclusion settings.
        
        Args:
            task_data: Task data from API
            included: Included resources (projects, tasklists, etc.)
        
        Returns:
            True if task should be filtered (skipped), False otherwise
        """
        excluded_companies, excluded_projects = get_sync_filters()
        if not excluded_companies and not excluded_projects:
            return False
        
        # Get project ID from task
        project_id = None
        if task_data.get("tasklist") and isinstance(task_data["tasklist"], dict):
            tasklist_id = str(task_data["tasklist"].get("id", ""))
            if tasklist_id and "tasklists" in included:
                tasklist_data = included["tasklists"].get(tasklist_id, {})
                if tasklist_data.get("project") and isinstance(tasklist_data["project"], dict):
                    project_id = tasklist_data["project"].get("id")
        
        if project_id:
            try:
                project_id = int(project_id)
                # Check if project is directly excluded
                if project_id in excluded_projects:
                    return True
                
                # Check if project's company is excluded
                if excluded_companies and "projects" in included:
                    project_data = included["projects"].get(str(project_id), {})
                    company_ref = project_data.get("company")
                    if company_ref:
                        company_id = company_ref.get("id") if isinstance(company_ref, dict) else company_ref
                        if company_id and int(company_id) in excluded_companies:
                            return True
            except (ValueError, TypeError):
                pass
        
        return False

