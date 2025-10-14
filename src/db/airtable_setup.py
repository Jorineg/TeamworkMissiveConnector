"""Airtable setup and table creation utilities."""
from typing import List, Dict, Any
import requests

from src import settings
from src.logging_conf import logger


class AirtableSetup:
    """Helper for setting up and validating Airtable tables."""
    
    # Required fields for each table
    EMAILS_REQUIRED_FIELDS = {
        "Email ID": "singleLineText",
        "Subject": "singleLineText",
        "From": "singleLineText",
        "Deleted": "checkbox",
    }
    
    TASKS_REQUIRED_FIELDS = {
        "Task ID": "singleLineText",
        "Title": "singleLineText",
        "Deleted": "checkbox",
    }
    
    # Optional but recommended fields
    EMAILS_OPTIONAL_FIELDS = {
        "Thread ID": "singleLineText",
        "To": "multilineText",
        "Cc": "multilineText",
        "Bcc": "multilineText",
        "Body Text": "multilineText",
        "Body HTML": "multilineText",
        "Sent At": "date",
        "Received At": "date",
        "Labels": "multipleSelects",
        "Deleted At": "date",
        "Source Links": "multilineText",
        "Attachments": "multipleAttachments",
    }
    
    TASKS_OPTIONAL_FIELDS = {
        "Project ID": "singleLineText",
        "Description": "multilineText",
        "Status": "singleSelect",
        "Tags": "multipleSelects",
        "Assignees": "multilineText",
        "Due At": "date",
        "Updated At": "date",
        "Deleted At": "date",
        "Source Links": "multilineText",
    }
    
    def __init__(self):
        self.api_key = settings.AIRTABLE_API_KEY
        self.base_id = settings.AIRTABLE_BASE_ID
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def ensure_tables_exist(self) -> bool:
        """
        Ensure Airtable tables exist, creating them if necessary.
        Returns True if successful, False otherwise.
        """
        logger.info("Checking Airtable tables...")
        
        try:
            # Get existing tables
            existing_tables = self._get_existing_tables()
            existing_table_names = [t["name"] for t in existing_tables]
            
            # Check/create Emails table
            if settings.AIRTABLE_EMAILS_TABLE not in existing_table_names:
                logger.info(f"Creating table: {settings.AIRTABLE_EMAILS_TABLE}")
                self._create_emails_table()
            else:
                logger.info(f"✓ Table '{settings.AIRTABLE_EMAILS_TABLE}' exists")
            
            # Check/create Tasks table
            if settings.AIRTABLE_TASKS_TABLE not in existing_table_names:
                logger.info(f"Creating table: {settings.AIRTABLE_TASKS_TABLE}")
                self._create_tasks_table()
            else:
                logger.info(f"✓ Table '{settings.AIRTABLE_TASKS_TABLE}' exists")
                # Ensure additional fields exist (text-based for data-dependent fields)
                try:
                    self._ensure_tasks_extra_fields()
                except Exception as e:
                    logger.error(f"Failed ensuring extra fields on Tasks: {e}")
            
            logger.info("✓ Airtable setup complete")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup Airtable tables: {e}", exc_info=True)
            return False
    
    def _get_existing_tables(self) -> List[Dict[str, Any]]:
        """Get list of existing tables in the base."""
        url = f"https://api.airtable.com/v0/meta/bases/{self.base_id}/tables"
        response = requests.get(url, headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json().get("tables", [])
    
    def _create_emails_table(self) -> Dict[str, Any]:
        """Create the Emails table with all necessary fields."""
        url = f"https://api.airtable.com/v0/meta/bases/{self.base_id}/tables"
        
        # Create a single table via schema API
        data = {
            "name": settings.AIRTABLE_EMAILS_TABLE,
            "description": "Email messages from Missive",
            "fields": [
                {"name": "Email ID", "type": "singleLineText"},
                {"name": "Thread ID", "type": "singleLineText"},
                {"name": "Subject", "type": "singleLineText"},
                {"name": "From", "type": "singleLineText"},
                {"name": "To", "type": "multilineText"},
                {"name": "Cc", "type": "multilineText"},
                {"name": "Bcc", "type": "multilineText"},
                {"name": "Body Text", "type": "multilineText"},
                {"name": "Body HTML", "type": "multilineText"},
                {"name": "Sent At", "type": "dateTime", "options": {"timeZone": "utc", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
                {"name": "Received At", "type": "dateTime", "options": {"timeZone": "utc", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
                {"name": "Labels", "type": "multipleSelects", "options": {"choices": []}},
                {"name": "Deleted", "type": "checkbox", "options": {"color": "greenBright", "icon": "check"}},
                {"name": "Deleted At", "type": "dateTime", "options": {"timeZone": "utc", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
                {"name": "Source Links", "type": "multilineText"},
                {"name": "Attachments", "type": "multipleAttachments"}
            ]
        }
        
        response = requests.post(url, headers=self.headers, json=data, timeout=30)
        try:
            response.raise_for_status()
        except requests.HTTPError as http_err:
            # Include response text for easier troubleshooting
            logger.error(f"Error creating table '{settings.AIRTABLE_EMAILS_TABLE}': {response.status_code} - {response.text}")
            raise
        logger.info(f"✓ Created table '{settings.AIRTABLE_EMAILS_TABLE}'")
        return response.json()
    
    def _create_tasks_table(self) -> Dict[str, Any]:
        """Create the Tasks table with all necessary fields."""
        url = f"https://api.airtable.com/v0/meta/bases/{self.base_id}/tables"
        
        # Create a single table via schema API
        data = {
            "name": settings.AIRTABLE_TASKS_TABLE,
            "description": "Tasks from Teamwork",
            "fields": [
                {"name": "Task ID", "type": "singleLineText"},
                {"name": "Project ID", "type": "singleLineText"},
                {"name": "Title", "type": "singleLineText"},
                {"name": "Description", "type": "multilineText"},
                {"name": "Status", "type": "singleSelect", "options": {"choices": [{"name": "new"}]}},
                {"name": "Tags", "type": "multipleSelects", "options": {"choices": []}},
                {"name": "Assignees", "type": "multilineText"},
                {"name": "Due At", "type": "dateTime", "options": {"timeZone": "utc", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
                {"name": "Updated At", "type": "dateTime", "options": {"timeZone": "utc", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
                {"name": "Deleted", "type": "checkbox", "options": {"color": "greenBright", "icon": "check"}},
                {"name": "Deleted At", "type": "dateTime", "options": {"timeZone": "utc", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
                {"name": "Source Links", "type": "multilineText"}
            ]
        }
        
        response = requests.post(url, headers=self.headers, json=data, timeout=30)
        try:
            response.raise_for_status()
        except requests.HTTPError:
            logger.error(f"Error creating table '{settings.AIRTABLE_TASKS_TABLE}': {response.status_code} - {response.text}")
            raise
        logger.info(f"✓ Created table '{settings.AIRTABLE_TASKS_TABLE}'")
        return response.json()

    def _ensure_tasks_extra_fields(self) -> None:
        """Ensure text-based fields and requested additional fields exist on Tasks table."""
        # Fetch tables and locate Tasks table ID and fields
        tables = self._get_existing_tables()
        tasks_table = next((t for t in tables if t.get("name") == settings.AIRTABLE_TASKS_TABLE), None)
        if not tasks_table:
            return
        table_id = tasks_table.get("id")
        existing_field_names = {f.get("name") for f in tasks_table.get("fields", [])}

        # Desired extra fields (avoid select option writes)
        desired_fields = [
            {"name": "Status Text", "type": "singleLineText"},
            {"name": "Tags Text", "type": "multilineText"},
            # User-requested additional fields (text where ambiguous)
            {"name": "id", "type": "singleLineText"},
            {"name": "name", "type": "singleLineText"},
            {"name": "description", "type": "multilineText"},
            {"name": "priority", "type": "singleLineText"},
            {"name": "progress", "type": "number", "options": {"precision": 0}},
            {"name": "tagIds", "type": "multilineText"},
            {"name": "updatedAt", "type": "dateTime", "options": {"timeZone": "utc", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
            {"name": "updatedby", "type": "singleLineText"},
            {"name": "parentTask", "type": "singleLineText"},
            {"name": "status", "type": "singleLineText"},
            {"name": "tasklistid", "type": "singleLineText"},
            {"name": "startdate", "type": "dateTime", "options": {"timeZone": "utc", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
            {"name": "dueDate", "type": "dateTime", "options": {"timeZone": "utc", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
            {"name": "estimateMinutes", "type": "number", "options": {"precision": 0}},
            {"name": "accumulatedEstimatedMinutes", "type": "number", "options": {"precision": 0}},
            {"name": "assigneeuserids", "type": "multilineText"},
            {"name": "attachments", "type": "multilineText"},
            {"name": "createdby", "type": "singleLineText"},
            {"name": "createdat", "type": "dateTime", "options": {"timeZone": "utc", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
            {"name": "dateUpdated", "type": "dateTime", "options": {"timeZone": "utc", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
            {"name": "createdByUserId", "type": "singleLineText"},
        ]

        create_url = f"https://api.airtable.com/v0/meta/bases/{self.base_id}/tables/{table_id}/fields"
        for field in desired_fields:
            if field["name"] in existing_field_names:
                continue
            resp = requests.post(create_url, headers=self.headers, json=field, timeout=15)
            if resp.status_code not in (200, 201):
                logger.error(f"Failed to create field '{field['name']}' on Tasks: {resp.status_code} - {resp.text}")
            else:
                logger.info(f"✓ Added field to Tasks: {field['name']}")
    
def ensure_airtable_tables() -> bool:
    """
    Ensure Airtable tables exist, creating them if necessary.
    Returns True if successful, False otherwise.
    """
    setup = AirtableSetup()
    return setup.ensure_tables_exist()

