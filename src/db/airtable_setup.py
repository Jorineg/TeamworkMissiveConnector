"""Airtable setup and table creation utilities."""
from typing import List, Dict, Any, Optional
import requests

from src import settings
from src.logging_conf import logger


def _get_datetime_field_options() -> Dict[str, Any]:
    """Get the standard datetime field options with the configured timezone."""
    return {
        "timeZone": settings.TIMEZONE,
        "dateFormat": {"name": "iso"},
        "timeFormat": {"name": "24hour"}
    }


class AirtableSetup:
    """Helper for setting up and validating Airtable tables."""

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

            logger.info("✓ Airtable setup complete")
            return True

        except Exception as e:
            logger.error(f"Failed to setup Airtable tables: {e}", exc_info=True)
            return False
    
    def ensure_category_columns(self, category_names: List[str]) -> bool:
        """
        Ensure category columns exist in both Emails and Tasks tables.
        
        Args:
            category_names: List of category column names to create
        
        Returns:
            True if successful, False otherwise
        """
        if not category_names:
            logger.info("No category columns to create")
            return True
        
        logger.info(f"Ensuring {len(category_names)} category columns exist...")
        
        try:
            # Ensure columns in Emails table
            self._ensure_columns_in_table(
                settings.AIRTABLE_EMAILS_TABLE,
                category_names
            )
            
            # Ensure columns in Tasks table
            self._ensure_columns_in_table(
                settings.AIRTABLE_TASKS_TABLE,
                category_names
            )
            
            logger.info("✓ Category columns setup complete")
            return True
        
        except Exception as e:
            logger.error(f"Failed to setup category columns: {e}", exc_info=True)
            return False
    
    def _ensure_columns_in_table(self, table_name: str, column_names: List[str]) -> None:
        """
        Ensure specific columns exist in a table, creating them if necessary.
        
        Args:
            table_name: Name of the table
            column_names: List of column names to ensure exist
        """
        # Get table ID
        table_id = self._get_table_id(table_name)
        if not table_id:
            logger.error(f"Table '{table_name}' not found")
            return
        
        # Get existing fields
        existing_fields = self._get_table_fields(table_id)
        existing_field_names = [f["name"] for f in existing_fields]
        
        # Create missing columns
        for column_name in column_names:
            if column_name not in existing_field_names:
                logger.info(f"Creating column '{column_name}' in table '{table_name}'")
                self._create_field(table_id, column_name)
            else:
                logger.debug(f"✓ Column '{column_name}' exists in table '{table_name}'")
    
    def _get_table_id(self, table_name: str) -> Optional[str]:
        """Get table ID by name."""
        tables = self._get_existing_tables()
        for table in tables:
            if table["name"] == table_name:
                return table["id"]
        return None
    
    def _get_table_fields(self, table_id: str) -> List[Dict[str, Any]]:
        """Get list of fields in a table."""
        url = f"https://api.airtable.com/v0/meta/bases/{self.base_id}/tables"
        response = requests.get(url, headers=self.headers, timeout=10)
        response.raise_for_status()
        
        tables = response.json().get("tables", [])
        for table in tables:
            if table["id"] == table_id:
                return table.get("fields", [])
        
        return []
    
    def _create_field(self, table_id: str, field_name: str) -> Dict[str, Any]:
        """
        Create a new field (column) in a table.
        
        Args:
            table_id: Airtable table ID
            field_name: Name of the field to create
        
        Returns:
            Response data from Airtable API
        """
        url = f"https://api.airtable.com/v0/meta/bases/{self.base_id}/tables/{table_id}/fields"
        
        data = {
            "name": field_name,
            "type": "multilineText"  # Use multilineText for comma-separated values
        }
        
        response = requests.post(url, headers=self.headers, json=data, timeout=30)
        try:
            response.raise_for_status()
        except requests.HTTPError:
            logger.error(
                f"Error creating field '{field_name}': {response.status_code} - {response.text}"
            )
            raise
        
        logger.info(f"✓ Created field '{field_name}'")
        return response.json()

    def _get_existing_tables(self) -> List[Dict[str, Any]]:
        """Get list of existing tables in the base."""
        url = f"https://api.airtable.com/v0/meta/bases/{self.base_id}/tables"
        response = requests.get(url, headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json().get("tables", [])

    def _create_emails_table(self) -> Dict[str, Any]:
        """Create the Emails table with all necessary fields in one request."""
        url = f"https://api.airtable.com/v0/meta/bases/{self.base_id}/tables"

        data = {
            "name": settings.AIRTABLE_EMAILS_TABLE,
            "description": "Email messages from Missive",
            "fields": [
                {"name": "Email ID", "type": "singleLineText"},
                {"name": "Thread ID", "type": "singleLineText"},
                {"name": "Subject", "type": "singleLineText"},
                {"name": "From", "type": "singleLineText"},
                {"name": "From Name", "type": "singleLineText"},
                {"name": "To", "type": "multilineText"},
                {"name": "To Names", "type": "multilineText"},
                {"name": "Cc", "type": "multilineText"},
                {"name": "Cc Names", "type": "multilineText"},
                {"name": "Bcc", "type": "multilineText"},
                {"name": "Bcc Names", "type": "multilineText"},
                {"name": "In Reply To", "type": "multilineText"},
                {"name": "Body Text", "type": "multilineText"},
                {"name": "Body HTML", "type": "multilineText"},
                {"name": "Sent At", "type": "dateTime", "options": _get_datetime_field_options()},
                {"name": "Received At", "type": "dateTime", "options": _get_datetime_field_options()},
                {"name": "Labels Text", "type": "multilineText"},
                {"name": "Draft", "type": "checkbox", "options": {"color": "yellowBright", "icon": "check"}},
                {"name": "Deleted", "type": "checkbox", "options": {"color": "greenBright", "icon": "check"}},
                {"name": "Deleted At", "type": "dateTime", "options": _get_datetime_field_options()},
                {"name": "Source Links", "type": "multilineText"},
                {"name": "Attachments", "type": "multipleAttachments"}
            ]
        }

        response = requests.post(url, headers=self.headers, json=data, timeout=30)
        try:
            response.raise_for_status()
        except requests.HTTPError:
            logger.error(
                f"Error creating table '{settings.AIRTABLE_EMAILS_TABLE}': {response.status_code} - {response.text}"
            )
            raise
        logger.info(f"✓ Created table '{settings.AIRTABLE_EMAILS_TABLE}'")
        return response.json()

    def _create_tasks_table(self) -> Dict[str, Any]:
        """Create the Tasks table with all necessary fields in one request."""
        url = f"https://api.airtable.com/v0/meta/bases/{self.base_id}/tables"

        data = {
            "name": settings.AIRTABLE_TASKS_TABLE,
            "description": "Tasks from Teamwork",
            "fields": [
                # Exact Teamwork API field names only
                {"name": "id", "type": "singleLineText"},
                {"name": "name", "type": "singleLineText"},
                {"name": "description", "type": "multilineText"},
                {"name": "status", "type": "singleLineText"},
                {"name": "priority", "type": "singleLineText"},
                {"name": "progress", "type": "number", "options": {"precision": 0}},
                # Tags - both IDs and names
                {"name": "tagIds", "type": "multilineText"},
                {"name": "tags", "type": "multilineText"},
                # Assignees - both IDs and names
                {"name": "assigneeUserIds", "type": "multilineText"},
                {"name": "assignees", "type": "multilineText"},
                {"name": "attachments", "type": "multilineText"},
                # Project info
                {"name": "projectId", "type": "singleLineText"},
                {"name": "projectName", "type": "singleLineText"},
                # Tasklist info
                {"name": "tasklistId", "type": "singleLineText"},
                {"name": "tasklistName", "type": "singleLineText"},
                {"name": "parentTask", "type": "singleLineText"},
                {"name": "startDate", "type": "dateTime", "options": _get_datetime_field_options()},
                {"name": "dueDate", "type": "dateTime", "options": _get_datetime_field_options()},
                {"name": "updatedAt", "type": "dateTime", "options": _get_datetime_field_options()},
                # UpdatedBy - both ID and name
                {"name": "updatedById", "type": "singleLineText"},
                {"name": "updatedBy", "type": "singleLineText"},
                {"name": "createdAt", "type": "dateTime", "options": _get_datetime_field_options()},
                # CreatedBy - both ID and name
                {"name": "createdById", "type": "singleLineText"},
                {"name": "createdBy", "type": "singleLineText"},
                {"name": "dateUpdated", "type": "dateTime", "options": _get_datetime_field_options()},
                {"name": "estimateMinutes", "type": "number", "options": {"precision": 0}},
                {"name": "accumulatedEstimatedMinutes", "type": "number", "options": {"precision": 0}},
                {"name": "deletedAt", "type": "dateTime", "options": _get_datetime_field_options()}
            ]
        }

        response = requests.post(url, headers=self.headers, json=data, timeout=30)
        try:
            response.raise_for_status()
        except requests.HTTPError:
            logger.error(
                f"Error creating table '{settings.AIRTABLE_TASKS_TABLE}': {response.status_code} - {response.text}"
            )
            raise
        logger.info(f"✓ Created table '{settings.AIRTABLE_TASKS_TABLE}'")
        return response.json()



def ensure_airtable_tables() -> bool:
    """
    Ensure Airtable tables exist, creating them if necessary.
    Returns True if successful, False otherwise.
    """
    setup = AirtableSetup()
    return setup.ensure_tables_exist()

