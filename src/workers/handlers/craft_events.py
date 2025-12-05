"""Handler for Craft document events."""
from typing import Dict, Any, Optional

from src.logging_conf import logger
from src.db.interface import DatabaseInterface
from src.connectors.craft_client import CraftClient


class CraftEventHandler:
    """Handles Craft document events from the queue."""
    
    def __init__(self, db: DatabaseInterface):
        self.db = db
        self.craft_client = CraftClient()
    
    def handle_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """
        Handle a Craft event (legacy method for compatibility).
        
        Args:
            event_type: Type of event (e.g., 'document.backfill')
            payload: Event payload with document ID
        """
        self.process_event(event_type, payload)
    
    def process_event(self, event_type: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process a Craft event and return the document data.
        
        Args:
            event_type: Type of event
            payload: Event payload with document ID
        
        Returns:
            Document data dict if successful, None otherwise
        """
        doc_id = payload.get("id") or payload.get("document_id")
        
        if not doc_id:
            logger.warning("Craft event missing document ID")
            return None
        
        logger.debug(f"Processing Craft event: {event_type} for document {doc_id}")
        
        if event_type in ("document.backfill", "document.updated", "document.created"):
            return self._handle_document_update(doc_id)
        elif event_type == "document.deleted":
            return self._handle_document_deleted(doc_id)
        else:
            logger.warning(f"Unknown Craft event type: {event_type}")
            return self._handle_document_update(doc_id)  # Default to update
    
    def _handle_document_update(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Handle document update/create event.
        
        Fetches the full document content and upserts to database.
        
        Args:
            doc_id: Document ID
        
        Returns:
            Document data dict if successful, None otherwise
        """
        if not self.craft_client.is_configured():
            logger.warning("Craft client not configured")
            return None
        
        # Fetch document metadata first
        documents = self.craft_client.get_documents(fetch_metadata=True)
        doc_metadata = None
        
        for doc in documents:
            if doc.get("id") == doc_id:
                doc_metadata = doc
                break
        
        if not doc_metadata:
            logger.warning(f"Craft document {doc_id} not found in document list")
            return None
        
        # Check if document is deleted
        if doc_metadata.get("isDeleted", False):
            logger.info(f"Craft document {doc_id} is marked as deleted")
            self._handle_document_deleted(doc_id)
            return None
        
        # Fetch full document content as markdown
        markdown_content = self.craft_client.get_document_content(doc_id, fetch_metadata=True)
        
        # Build document data for database
        doc_data = {
            "id": doc_id,
            "title": doc_metadata.get("title"),
            "markdown_content": markdown_content,
            "isDeleted": doc_metadata.get("isDeleted", False),
            "lastModifiedAt": doc_metadata.get("lastModifiedAt"),
            "createdAt": doc_metadata.get("createdAt"),
        }
        
        # Upsert to database
        if hasattr(self.db, 'upsert_craft_document'):
            self.db.upsert_craft_document(doc_data)
            logger.info(f"Upserted Craft document {doc_id}: {doc_metadata.get('title')}")
        else:
            logger.warning("Database does not support upsert_craft_document")
        
        return doc_data
    
    def _handle_document_deleted(self, doc_id: str) -> None:
        """
        Handle document deletion event.
        
        Args:
            doc_id: Document ID
        """
        if hasattr(self.db, 'mark_craft_document_deleted'):
            self.db.mark_craft_document_deleted(doc_id)
            logger.info(f"Marked Craft document {doc_id} as deleted")
        else:
            logger.warning("Database does not support mark_craft_document_deleted")

