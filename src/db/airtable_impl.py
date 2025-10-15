"""Airtable implementation of the database interface."""
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pyairtable import Api

from src import settings
from src.db.interface import DatabaseInterface
from src.db.models import Email, Task, Checkpoint
from src.logging_conf import logger


class AirtableDatabase(DatabaseInterface):
    """Airtable implementation of database operations."""
    
    def __init__(self):
        self.api = Api(settings.AIRTABLE_API_KEY)
        self.base = self.api.base(settings.AIRTABLE_BASE_ID)
        self.emails_table = self.base.table(settings.AIRTABLE_EMAILS_TABLE)
        self.tasks_table = self.base.table(settings.AIRTABLE_TASKS_TABLE)
        
        # Cache for record lookups by external ID
        self._email_cache: Dict[str, str] = {}  # email_id -> airtable_record_id
        self._task_cache: Dict[str, str] = {}  # task_id -> airtable_record_id
    
    def upsert_email(self, email: Email) -> None:
        """Insert or update an email record."""
        try:
            # Build Airtable fields
            fields = {
                "Email ID": email.email_id,
                "Subject": email.subject or "",
                "From": email.from_address or "",
                "To": ", ".join(email.to_addresses) if email.to_addresses else "",
                "Cc": ", ".join(email.cc_addresses) if email.cc_addresses else "",
                "Bcc": ", ".join(email.bcc_addresses) if email.bcc_addresses else "",
                "Body Text": email.body_text or "",
                "Body HTML": email.body_html or "",
                "Deleted": email.deleted,
                "Source Links": json.dumps(email.source_links)
            }
            
            # Add optional fields
            if email.thread_id:
                fields["Thread ID"] = email.thread_id
            if email.sent_at:
                fields["Sent At"] = self._to_utc_z(email.sent_at)
            if email.received_at:
                fields["Received At"] = self._to_utc_z(email.received_at)
            if email.deleted_at:
                fields["Deleted At"] = self._to_utc_z(email.deleted_at)
            if email.labels:
                # Store as plain text to avoid schema option management
                fields["Labels Text"] = ", ".join(email.labels)
            
            # Handle attachments - Airtable expects list of dicts with 'url' keys
            if email.attachments:
                attachment_data = []
                for att in email.attachments:
                    att_dict = {"url": att.source_url}
                    if att.filename:
                        att_dict["filename"] = att.filename
                    attachment_data.append(att_dict)
                fields["Attachments"] = attachment_data
            
            # Check if record exists
            existing_record_id = self._find_email_record(email.email_id)
            
            if existing_record_id:
                # Update existing record
                self.emails_table.update(existing_record_id, fields)
                logger.info(f"Updated email {email.email_id} in Airtable")
            else:
                # Create new record
                record = self.emails_table.create(fields)
                self._email_cache[email.email_id] = record["id"]
                logger.info(f"Created email {email.email_id} in Airtable")
        
        except Exception as e:
            logger.error(f"Failed to upsert email {email.email_id}: {e}", exc_info=True)
            raise
    
    def upsert_task(self, task: Task) -> None:
        """Insert or update a task record using exact Teamwork API fields."""
        try:
            raw = task.raw or {}

            fields: Dict[str, Any] = {}

            def set_if_present(key: str, value: Any) -> None:
                if value is None:
                    return
                fields[key] = value

            def set_dt_if_present(key: str, value: Optional[str]) -> None:
                if not value:
                    return
                try:
                    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    fields[key] = self._to_utc_z(dt)
                except Exception:
                    fields[key] = value

            # Simple scalars
            set_if_present("id", str(raw.get("id", task.task_id)))
            set_if_present("name", raw.get("name"))
            set_if_present("description", raw.get("description"))
            set_if_present("status", raw.get("status"))
            set_if_present("priority", raw.get("priority"))
            if raw.get("progress") is not None:
                set_if_present("progress", int(raw.get("progress")))

            # Tags - store both IDs and names
            if raw.get("tagIds"):
                set_if_present("tagIds", ", ".join(str(t) for t in raw.get("tagIds", [])))
            if task.tags:
                set_if_present("tags", ", ".join(task.tags))
            
            # Assignees - store both IDs and names
            if raw.get("assigneeUserIds"):
                set_if_present("assigneeUserIds", ", ".join(str(u) for u in raw.get("assigneeUserIds", [])))
            if task.assignees:
                set_if_present("assignees", ", ".join(task.assignees))
            
            if raw.get("attachments") is not None:
                set_if_present("attachments", json.dumps(raw.get("attachments")))

            # IDs
            if raw.get("tasklistId") is not None:
                set_if_present("tasklistId", str(raw.get("tasklistId")))
            if raw.get("parentTask") is not None:
                set_if_present("parentTask", str(raw.get("parentTask")))

            # Date/times & numerics
            set_dt_if_present("startDate", raw.get("startDate"))
            set_dt_if_present("dueDate", raw.get("dueDate"))
            set_dt_if_present("updatedAt", raw.get("updatedAt"))
            
            # UpdatedBy - store both ID and name
            if raw.get("updatedBy"):
                if isinstance(raw["updatedBy"], dict) and raw["updatedBy"].get("id"):
                    set_if_present("updatedById", str(raw["updatedBy"]["id"]))
                elif not isinstance(raw["updatedBy"], dict):
                    set_if_present("updatedById", str(raw["updatedBy"]))
            if task.updated_by:
                set_if_present("updatedBy", task.updated_by)
            
            set_dt_if_present("createdAt", raw.get("createdAt"))
            
            # CreatedBy - store both ID and name
            if raw.get("createdBy"):
                if isinstance(raw["createdBy"], dict) and raw["createdBy"].get("id"):
                    set_if_present("createdById", str(raw["createdBy"]["id"]))
                elif not isinstance(raw["createdBy"], dict):
                    set_if_present("createdById", str(raw["createdBy"]))
            if task.created_by:
                set_if_present("createdBy", task.created_by)
            set_dt_if_present("dateUpdated", raw.get("dateUpdated"))
            if raw.get("estimateMinutes") is not None:
                set_if_present("estimateMinutes", int(raw.get("estimateMinutes")))
            if raw.get("accumulatedEstimatedMinutes") is not None:
                set_if_present("accumulatedEstimatedMinutes", int(raw.get("accumulatedEstimatedMinutes")))
            set_dt_if_present("deletedAt", raw.get("deletedAt"))
            
            # Check if record exists
            existing_record_id = self._find_task_record(str(raw.get("id", task.task_id)))
            
            if existing_record_id:
                # Update existing record
                self.tasks_table.update(existing_record_id, fields)
                logger.info(f"Updated task {task.task_id} in Airtable")
            else:
                # Create new record
                record = self.tasks_table.create(fields)
                self._task_cache[str(raw.get("id", task.task_id))] = record["id"]
                logger.info(f"Created task {task.task_id} in Airtable")
        
        except Exception as e:
            logger.error(f"Failed to upsert task {task.task_id}: {e}", exc_info=True)
            raise
    
    def mark_email_deleted(self, email_id: str) -> None:
        """Mark an email as deleted."""
        try:
            record_id = self._find_email_record(email_id)
            if record_id:
                self.emails_table.update(record_id, {
                    "Deleted": True,
                    "Deleted At": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                })
                logger.info(f"Marked email {email_id} as deleted")
        except Exception as e:
            logger.error(f"Failed to mark email {email_id} as deleted: {e}", exc_info=True)
            raise
    
    def mark_task_deleted(self, task_id: str) -> None:
        """Mark a task as deleted."""
        try:
            record_id = self._find_task_record(task_id)
            if record_id:
                self.tasks_table.update(record_id, {
                    "deletedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                })
                logger.info(f"Marked task {task_id} as deleted")
        except Exception as e:
            logger.error(f"Failed to mark task {task_id} as deleted: {e}", exc_info=True)
            raise
    
    def get_checkpoint(self, source: str) -> Optional[Checkpoint]:
        """Get the last sync checkpoint for a source."""
        checkpoint_file = settings.CHECKPOINT_DIR / f"{source}.json"
        if checkpoint_file.exists():
            try:
                with open(checkpoint_file, "r") as f:
                    data = json.load(f)
                    return Checkpoint.from_dict(data)
            except Exception as e:
                logger.error(f"Failed to load checkpoint for {source}: {e}", exc_info=True)
        return None
    
    def set_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Save a sync checkpoint for a source."""
        checkpoint_file = settings.CHECKPOINT_DIR / f"{checkpoint.source}.json"
        try:
            with open(checkpoint_file, "w") as f:
                json.dump(checkpoint.to_dict(), f, indent=2)
            logger.debug(f"Saved checkpoint for {checkpoint.source}")
        except Exception as e:
            logger.error(f"Failed to save checkpoint for {checkpoint.source}: {e}", exc_info=True)
            raise
    
    def close(self) -> None:
        """Close database connections."""
        # Airtable API doesn't need explicit cleanup
        pass
    
    def _find_email_record(self, email_id: str) -> Optional[str]:
        """Find an email record by external ID."""
        # Check cache first
        if email_id in self._email_cache:
            return self._email_cache[email_id]
        
        # Escape single quotes in formula values
        safe_email_id = str(email_id).replace("'", "\\'")
        
        # Search Airtable
        try:
            formula = f"{{Email ID}} = '{safe_email_id}'"
            records = self.emails_table.all(formula=formula, max_records=1)
            if records:
                record_id = records[0]["id"]
                self._email_cache[email_id] = record_id
                return record_id
        except Exception as e:
            logger.error(f"Error finding email record {email_id}: {e}")
        
        return None
    
    def _find_task_record(self, task_id: str) -> Optional[str]:
        """Find a task record by Teamwork id field."""
        # Check cache first
        if task_id in self._task_cache:
            return self._task_cache[task_id]
        
        # Escape single quotes in formula values
        safe_task_id = str(task_id).replace("'", "\\'")
        
        # Search Airtable
        try:
            formula = f"{{id}} = '{safe_task_id}'"
            records = self.tasks_table.all(formula=formula, max_records=1)
            if records:
                record_id = records[0]["id"]
                self._task_cache[task_id] = record_id
                return record_id
        except Exception as e:
            logger.error(f"Error finding task record {task_id}: {e}")
        
        return None

    def _to_utc_z(self, dt: datetime) -> str:
        """Format datetime as UTC ISO string with 'Z' suffix."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")

