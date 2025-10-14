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
                fields["Sent At"] = email.sent_at.isoformat()
            if email.received_at:
                fields["Received At"] = email.received_at.isoformat()
            if email.deleted_at:
                fields["Deleted At"] = email.deleted_at.isoformat()
            if email.labels:
                fields["Labels"] = email.labels
            
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
        """Insert or update a task record."""
        try:
            # Build Airtable fields
            fields = {
                "Task ID": task.task_id,
                "Title": task.title or "",
                "Description": task.description or "",
                "Deleted": task.deleted,
                "Source Links": json.dumps(task.source_links)
            }
            
            # Add optional fields
            if task.project_id:
                fields["Project ID"] = task.project_id
            if task.status:
                # Avoid select option writes; use text field
                fields["Status Text"] = task.status
            if task.tags:
                # Store tags as comma-separated text to avoid select options
                fields["Tags Text"] = ", ".join(task.tags)
            if task.assignees:
                fields["Assignees"] = ", ".join(task.assignees)
            if task.due_at:
                fields["Due At"] = task.due_at.isoformat()
            if task.updated_at:
                fields["Updated At"] = task.updated_at.isoformat()
            if task.deleted_at:
                fields["Deleted At"] = task.deleted_at.isoformat()
            
            # Check if record exists
            existing_record_id = self._find_task_record(task.task_id)
            
            if existing_record_id:
                # Update existing record
                self.tasks_table.update(existing_record_id, fields)
                logger.info(f"Updated task {task.task_id} in Airtable")
            else:
                # Create new record
                record = self.tasks_table.create(fields)
                self._task_cache[task.task_id] = record["id"]
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
                    "Deleted": True,
                    "Deleted At": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
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
        
        # Search Airtable
        try:
            formula = f"{{Email ID}} = '{email_id}'"
            records = self.emails_table.all(formula=formula)
            if records:
                record_id = records[0]["id"]
                self._email_cache[email_id] = record_id
                return record_id
        except Exception as e:
            logger.error(f"Error finding email record {email_id}: {e}")
        
        return None
    
    def _find_task_record(self, task_id: str) -> Optional[str]:
        """Find a task record by external ID."""
        # Check cache first
        if task_id in self._task_cache:
            return self._task_cache[task_id]
        
        # Search Airtable
        try:
            formula = f"{{Task ID}} = '{task_id}'"
            records = self.tasks_table.all(formula=formula)
            if records:
                record_id = records[0]["id"]
                self._task_cache[task_id] = record_id
                return record_id
        except Exception as e:
            logger.error(f"Error finding task record {task_id}: {e}")
        
        return None

