"""Airtable implementation of the database interface."""
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from zoneinfo import ZoneInfo
from pyairtable import Api

from src import settings
from src.db.interface import DatabaseInterface
from src.db.models import Email, Task, Checkpoint
from src.logging_conf import logger


class AirtableDatabase(DatabaseInterface):
    """Airtable implementation of database operations."""
    
    # Airtable long text field limit
    MAX_LONG_TEXT_LENGTH = 100000
    
    def __init__(self):
        self.api = Api(settings.AIRTABLE_API_KEY)
        self.base = self.api.base(settings.AIRTABLE_BASE_ID)
        self.emails_table = self.base.table(settings.AIRTABLE_EMAILS_TABLE)
        self.tasks_table = self.base.table(settings.AIRTABLE_TASKS_TABLE)
        
        # Cache for record lookups by external ID
        self._email_cache: Dict[str, str] = {}  # email_id -> airtable_record_id
        self._task_cache: Dict[str, str] = {}  # task_id -> airtable_record_id
    
    def _sanitize_long_text(self, text: Optional[str], field_name: str = "field", record_id: str = "") -> str:
        """
        Sanitize text for Airtable long text fields.
        
        Airtable long text fields have a 100,000 character limit and may reject
        certain control characters or invalid UTF-8 sequences.
        
        Args:
            text: The text to sanitize
            field_name: Name of the field (for logging)
            record_id: ID of the record (for logging)
        
        Returns:
            Sanitized text string (empty string if input is None)
        """
        if text is None:
            return ""
        
        # Ensure it's a string
        if not isinstance(text, str):
            logger.warning(f"Non-string value for {field_name} in {record_id}, converting to string")
            text = str(text)
        
        # Remove null bytes and other problematic control characters
        # Keep common whitespace (newlines, tabs, spaces)
        text = text.replace('\x00', '')  # Null bytes
        
        # Remove other control characters except newline, carriage return, and tab
        sanitized_chars = []
        for char in text:
            code = ord(char)
            # Keep printable chars, newline (10), carriage return (13), tab (9)
            if code >= 32 or code in (9, 10, 13):
                sanitized_chars.append(char)
        
        text = ''.join(sanitized_chars)
        
        # Truncate if exceeds Airtable's limit
        if len(text) > self.MAX_LONG_TEXT_LENGTH:
            logger.warning(
                f"{field_name} exceeds Airtable limit of {self.MAX_LONG_TEXT_LENGTH} chars "
                f"(was {len(text)} chars) for {record_id}, truncating"
            )
            text = text[:self.MAX_LONG_TEXT_LENGTH]
            # Add truncation indicator
            if len(text) > 50:
                text = text[:-50] + "\n\n[... Content truncated due to length ...]"
        
        return text
    
    def upsert_email(self, email: Email) -> None:
        """Insert or update an email record."""
        self.upsert_emails_batch([email])

    def upsert_emails_batch(self, emails: List[Email]) -> None:
        """Insert or update multiple email records in a batch using Airtable's upsert API."""
        if not emails:
            return
        
        try:
            records = []
            for email in emails:
                # Sanitize long text fields to comply with Airtable's requirements
                subject = self._sanitize_long_text(email.subject, "Subject", email.email_id)
                body_text = self._sanitize_long_text(email.body_text, "Body Text", email.email_id)
                body_html = self._sanitize_long_text(email.body_html, "Body HTML", email.email_id)
                
                # Build Airtable fields
                fields = {
                    "Email ID": email.email_id,
                    "Subject": subject,
                    "From": email.from_address or "",
                    "From Name": email.from_name or "",
                    "To": ", ".join(email.to_addresses) if email.to_addresses else "",
                    "To Names": ", ".join(email.to_names) if email.to_names else "",
                    "Cc": ", ".join(email.cc_addresses) if email.cc_addresses else "",
                    "Cc Names": ", ".join(email.cc_names) if email.cc_names else "",
                    "Bcc": ", ".join(email.bcc_addresses) if email.bcc_addresses else "",
                    "Bcc Names": ", ".join(email.bcc_names) if email.bcc_names else "",
                    "In Reply To": ", ".join(email.in_reply_to) if email.in_reply_to else "",
                    "Body Text": body_text,
                    "Body HTML": body_html,
                    "Draft": email.draft,
                    "Deleted": email.deleted,
                    "Source Links": json.dumps(email.source_links)
                }
                
                # Add optional fields
                if email.thread_id:
                    fields["Thread ID"] = email.thread_id
                if email.sent_at:
                    fields["Sent At"] = self._to_localized_z(email.sent_at)
                if email.received_at:
                    fields["Received At"] = self._to_localized_z(email.received_at)
                if email.deleted_at:
                    fields["Deleted At"] = self._to_localized_z(email.deleted_at)
                if email.labels:
                    # Store as plain text to avoid schema option management
                    fields["Labels Text"] = ", ".join(email.labels)
                
                # Store categorized labels
                if email.categorized_labels:
                    for category, labels in email.categorized_labels.items():
                        if labels:
                            fields[category] = ", ".join(labels)
                
                # Handle attachments - Airtable expects list of dicts with 'url' keys
                if email.attachments:
                    attachment_data = []
                    for att in email.attachments:
                        att_dict = {"url": att.source_url}
                        if att.filename:
                            att_dict["filename"] = att.filename
                        attachment_data.append(att_dict)
                    fields["Attachments"] = attachment_data
                
                records.append({"fields": fields})
            
            # Use Airtable's batch upsert API
            # performUpsert with fieldsToMergeOn uses "Email ID" as the external ID
            response = self.emails_table.batch_upsert(
                records,
                key_fields=["Email ID"],
                replace=False  # PATCH behavior, not PUT
            )
            
            # Update cache with created/updated records
            if response and "records" in response:
                for record in response["records"]:
                    email_id = record.get("fields", {}).get("Email ID")
                    if email_id:
                        self._email_cache[email_id] = record["id"]
            
            logger.info(f"Batch upserted {len(emails)} emails to Airtable")
        
        except Exception as e:
            # Log detailed information about the batch that failed
            logger.error(f"Failed to batch upsert {len(emails)} emails: {e}", exc_info=True)
            
            # Log email IDs and body lengths for debugging
            for i, email in enumerate(emails):
                body_html_len = len(email.body_html) if email.body_html else 0
                body_text_len = len(email.body_text) if email.body_text else 0
                logger.error(
                    f"  Email {i+1}/{len(emails)}: ID={email.email_id}, "
                    f"body_html_len={body_html_len}, body_text_len={body_text_len}, "
                    f"subject_len={len(email.subject) if email.subject else 0}"
                )
            
            # Try to process individually to identify the problematic record
            if len(emails) > 1:
                logger.info("Attempting to upsert emails individually to identify problematic record...")
                failed_emails = []
                for email in emails:
                    try:
                        # Try individual upsert
                        self.upsert_emails_batch([email])
                        logger.info(f"Successfully upserted email {email.email_id} individually")
                    except Exception as individual_error:
                        logger.error(f"Failed to upsert email {email.email_id}: {individual_error}")
                        failed_emails.append(email.email_id)
                
                if failed_emails:
                    logger.error(f"Failed email IDs: {failed_emails}")
            
            raise
    
    def upsert_task(self, task: Task) -> None:
        """Insert or update a task record using exact Teamwork API fields."""
        self.upsert_tasks_batch([task])

    def upsert_tasks_batch(self, tasks: List[Task]) -> None:
        """Insert or update multiple task records in a batch using Airtable's upsert API."""
        if not tasks:
            return
        
        try:
            records = []
            for task in tasks:
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
                        fields[key] = self._to_localized_z(dt)
                    except Exception:
                        fields[key] = value

                # Simple scalars
                set_if_present("id", str(raw.get("id", task.task_id)))
                set_if_present("name", raw.get("name"))
                # Sanitize description as it can be long text
                if raw.get("description"):
                    description = self._sanitize_long_text(
                        raw.get("description"), 
                        "description", 
                        str(raw.get("id", task.task_id))
                    )
                    set_if_present("description", description)
                set_if_present("status", raw.get("status"))
                set_if_present("priority", raw.get("priority"))
                if raw.get("progress") is not None:
                    set_if_present("progress", int(raw.get("progress")))

                # Tags - store both IDs and names
                if raw.get("tagIds"):
                    set_if_present("tagIds", ", ".join(str(t) for t in raw.get("tagIds", [])))
                if task.tags:
                    set_if_present("tags", ", ".join(task.tags))
                
                # Store categorized tags
                if task.categorized_tags:
                    for category, tags in task.categorized_tags.items():
                        if tags:
                            fields[category] = ", ".join(tags)
                
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
                
                records.append({"fields": fields})
            
            # Use Airtable's batch upsert API
            # performUpsert with fieldsToMergeOn uses "id" as the external ID
            response = self.tasks_table.batch_upsert(
                records,
                key_fields=["id"],
                replace=False  # PATCH behavior, not PUT
            )
            
            # Update cache with created/updated records
            if response and "records" in response:
                for record in response["records"]:
                    task_id = record.get("fields", {}).get("id")
                    if task_id:
                        self._task_cache[task_id] = record["id"]
            
            logger.info(f"Batch upserted {len(tasks)} tasks to Airtable")
        
        except Exception as e:
            # Log detailed information about the batch that failed
            logger.error(f"Failed to batch upsert {len(tasks)} tasks: {e}", exc_info=True)
            
            # Log task IDs and description lengths for debugging
            for i, task in enumerate(tasks):
                desc_len = len(task.description) if task.description else 0
                logger.error(
                    f"  Task {i+1}/{len(tasks)}: ID={task.task_id}, "
                    f"description_len={desc_len}, title={task.title}"
                )
            
            raise
    
    def mark_email_deleted(self, email_id: str) -> None:
        """Mark an email as deleted."""
        try:
            record_id = self._find_email_record(email_id)
            if record_id:
                self.emails_table.update(record_id, {
                    "Deleted": True,
                    "Deleted At": self._to_localized_z(datetime.now(timezone.utc))
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
                    "deletedAt": self._to_localized_z(datetime.now(timezone.utc))
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

    def _to_localized_z(self, dt: datetime) -> str:
        """Format datetime as localized ISO string for configured timezone."""
        try:
            tz = ZoneInfo(settings.TIMEZONE)
        except Exception as e:
            logger.warning(f"Invalid timezone '{settings.TIMEZONE}', falling back to UTC: {e}")
            tz = timezone.utc
        
        if dt.tzinfo is None:
            # Assume UTC if naive
            dt = dt.replace(tzinfo=timezone.utc)
        
        # Convert to configured timezone
        dt = dt.astimezone(tz)
        # Return ISO format - Airtable will display according to column's timezone setting
        iso_string = dt.isoformat()
        # Replace timezone offset with 'Z' if UTC, otherwise keep the offset
        if iso_string.endswith("+00:00"):
            return iso_string.replace("+00:00", "Z")
        return iso_string

