"""Missive event handler."""
from datetime import datetime, timezone
from typing import Dict, Any, List

from src.db.models import Email, Attachment
from src.db.interface import DatabaseInterface
from src.connectors.missive_client import MissiveClient
from src.logging_conf import logger


class MissiveEventHandler:
    """Handler for Missive webhook events."""
    
    def __init__(self, db: DatabaseInterface):
        self.db = db
        self.client = MissiveClient()
    
    def handle_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """
        Handle a Missive event.
        
        Args:
            event_type: Type of event (e.g., "conversation.created", "message.received")
            payload: Event payload
        """
        logger.info(f"Handling Missive event: {event_type}")
        
        # Extract conversation/message data
        conversation_id = self._extract_conversation_id(payload)
        if not conversation_id:
            logger.warning(f"No conversation ID found in payload for event {event_type}")
            return
        
        # Handle deletion/trash events: fetch messages first, then mark deleted
        if "deleted" in event_type.lower() or "trashed" in event_type.lower():
            messages = self.client.get_conversation_messages(conversation_id)
            for msg in messages:
                msg_id = str(msg.get("id", ""))
                if msg_id:
                    self.db.mark_email_deleted(msg_id)
            return
        
        # Always fetch fresh messages from API to ensure consistency
        messages = self.client.get_conversation_messages(conversation_id)
        
        # Process each message
        for message_data in messages:
            try:
                email = self._parse_message(message_data, conversation_id)
                self.db.upsert_email(email)
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
    
    def _extract_conversation_id(self, payload: Dict[str, Any]) -> str:
        """Extract conversation ID from payload."""
        if "conversation" in payload:
            return str(payload["conversation"].get("id", ""))
        if "conversation_id" in payload:
            return str(payload["conversation_id"])
        if "conversationId" in payload:
            return str(payload["conversationId"])
        if "id" in payload:
            return str(payload["id"])
        return ""
    
    def _parse_message(self, data: Dict[str, Any], conversation_id: str) -> Email:
        """Parse Missive message data into Email model."""
        message_id = str(data.get("id", ""))
        
        # Parse dates
        sent_at = None
        if data.get("delivered_at"):
            try:
                sent_at = datetime.fromisoformat(data["delivered_at"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        
        received_at = None
        if data.get("received_at"):
            try:
                received_at = datetime.fromisoformat(data["received_at"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        
        # Parse from address
        from_address = None
        from_field = data.get("from_field", data.get("from"))
        if from_field:
            if isinstance(from_field, dict):
                from_address = from_field.get("address") or from_field.get("email")
            elif isinstance(from_field, str):
                from_address = from_field
        
        # Parse to addresses
        to_addresses = self._parse_email_addresses(data.get("to_fields", data.get("to", [])))
        cc_addresses = self._parse_email_addresses(data.get("cc_fields", data.get("cc", [])))
        bcc_addresses = self._parse_email_addresses(data.get("bcc_fields", data.get("bcc", [])))
        
        # Parse body
        body_text = data.get("body", data.get("preview", ""))
        body_html = data.get("body_html", "")
        
        # Parse labels/tags
        labels = []
        if data.get("labels"):
            labels = [label.get("name", str(label)) if isinstance(label, dict) else str(label)
                     for label in data["labels"]]
        
        # Check if deleted/trashed
        deleted = data.get("deleted", False) or data.get("trashed", False)
        deleted_at = None
        if deleted and data.get("trashed_at"):
            try:
                deleted_at = datetime.fromisoformat(data["trashed_at"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        
        # Parse attachments
        attachments = self._parse_attachments(data.get("attachments", []))
        
        return Email(
            email_id=message_id,
            thread_id=conversation_id,
            subject=data.get("subject"),
            from_address=from_address,
            to_addresses=to_addresses,
            cc_addresses=cc_addresses,
            bcc_addresses=bcc_addresses,
            body_text=body_text,
            body_html=body_html,
            sent_at=sent_at,
            received_at=received_at or sent_at or datetime.now(timezone.utc),
            labels=labels,
            deleted=deleted,
            deleted_at=deleted_at,
            source_links={"missive_url": data.get("web_url", "")} if data.get("web_url") else {},
            attachments=attachments
        )
    
    def _parse_email_addresses(self, addresses: Any) -> List[str]:
        """Parse email addresses from various formats."""
        if not addresses:
            return []
        
        if isinstance(addresses, str):
            return [addresses]
        
        if isinstance(addresses, list):
            result = []
            for addr in addresses:
                if isinstance(addr, dict):
                    email = addr.get("address") or addr.get("email")
                    if email:
                        result.append(email)
                elif isinstance(addr, str):
                    result.append(addr)
            return result
        
        return []
    
    def _parse_attachments(self, attachments_data: List[Dict[str, Any]]) -> List[Attachment]:
        """Parse attachment data."""
        attachments = []
        
        for att_data in attachments_data:
            try:
                attachment = Attachment(
                    filename=att_data.get("filename", att_data.get("name", "unknown")),
                    content_type=att_data.get("content_type", att_data.get("type", "application/octet-stream")),
                    byte_size=att_data.get("size", 0),
                    source_url=att_data.get("download_url", att_data.get("url", "")),
                    checksum=att_data.get("checksum")
                )
                attachments.append(attachment)
            except Exception as e:
                logger.error(f"Error parsing attachment: {e}", exc_info=True)
        
        return attachments

