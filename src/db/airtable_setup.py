"""Airtable setup and table creation utilities."""
from typing import List, Dict, Any
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
                {"name": "tasklistId", "type": "singleLineText"},
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

