"""Handler for Craft document events."""
from typing import Dict, Any, Optional

from src.logging_conf import logger
from src.db.interface import DatabaseInterface
from src.connectors.craft_client import CraftClient
from src.connectors.craft_markdown_parser import parse_craft_markdown


class CraftEventHandler:
    """Handles Craft document events from the queue."""
    
    def __init__(self, db: DatabaseInterface):
        self.db = db
        self.craft_client = CraftClient()
    
    def handle_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Handle a Craft event (legacy method for compatibility)."""
        self.process_event(event_type, payload)
    
    def process_event(self, event_type: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process a Craft event and return the document data.
        
        Payload should contain path metadata from backfill:
        - title, folder_path, folder_id, location, daily_note_date
        - lastModifiedAt, createdAt, isDeleted
        """
        doc_id = payload.get("id") or payload.get("document_id")
        
        if not doc_id:
            logger.warning("Craft event missing document ID")
            return None
        
        logger.debug(f"Processing Craft event: {event_type} for document {doc_id}")
        
        if event_type == "document.deleted":
            return self._handle_document_deleted(doc_id)
        
        # Check if document is marked as deleted in payload
        if payload.get("isDeleted", False):
            logger.info(f"Craft document {doc_id} is marked as deleted")
            self._handle_document_deleted(doc_id)
            return None
        
        return self._handle_document_update(doc_id, payload)
    
    def _handle_document_update(self, doc_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Handle document update/create event.
        
        Uses path metadata from payload, only fetches content from API.
        """
        if not self.craft_client.is_configured():
            logger.warning("Craft client not configured")
            return None
        
        # Fetch document content
        raw_content = self.craft_client.get_document_content(doc_id, fetch_metadata=True)
        
        if raw_content is None:
            logger.warning(f"Failed to fetch content for Craft document {doc_id}")
            # Still save metadata even without content
            raw_content = ""
        
        # Parse markdown
        parsed_content = parse_craft_markdown(raw_content) if raw_content else None
        
        # Build document data - use payload metadata + fetched content
        doc_data = {
            "id": doc_id,
            "title": payload.get("title"),
            "markdown_content": parsed_content,
            "isDeleted": payload.get("isDeleted", False),
            "folder_path": payload.get("folder_path"),
            "folder_id": payload.get("folder_id"),
            "location": payload.get("location"),
            "daily_note_date": payload.get("daily_note_date"),
            "lastModifiedAt": payload.get("lastModifiedAt"),
            "createdAt": payload.get("createdAt"),
        }
        
        # Upsert to database
        self.db.upsert_craft_document(doc_data)
        logger.info(f"Upserted Craft document {doc_id}: {payload.get('title')}")
        
        return doc_data
    
    def _handle_document_deleted(self, doc_id: str) -> None:
        """Handle document deletion event."""
        self.db.mark_craft_document_deleted(doc_id)
        logger.info(f"Marked Craft document {doc_id} as deleted")
