"""Missive event handler."""
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import re
from html import unescape

from src.db.models import Email, Attachment
from src.db.interface import DatabaseInterface
from src.connectors.missive_client import MissiveClient
from src.connectors.label_categories import get_label_categories
from src.logging_conf import logger


class MissiveEventHandler:
    """Handler for Missive webhook events."""
    
    def __init__(self, db: DatabaseInterface):
        self.db = db
        self.client = MissiveClient()
    
    def process_event(self, event_type: str, payload: Dict[str, Any]) -> Optional[List[Email]]:
        """
        Process a Missive event and return Email objects.
        
        Args:
            event_type: Type of event (e.g., "conversation.created", "message.received")
            payload: Event payload
        
        Returns:
            List of Email objects to be batch upserted, or None
        """
        logger.info(f"Processing Missive event: {event_type}")
        
        # Extract conversation/message data
        conversation_id = self._extract_conversation_id(payload)
        if not conversation_id:
            logger.warning(f"No conversation ID found in payload for event {event_type}")
            return None
        
        # Handle deletion/trash events: fetch messages first, then mark deleted
        if "deleted" in event_type.lower() or "trashed" in event_type.lower():
            messages = self.client.get_conversation_messages(conversation_id)
            for msg in messages:
                msg_id = str(msg.get("id", ""))
                if msg_id:
                    self.db.mark_email_deleted(msg_id)
            return None
        
        # Fetch conversation data to get labels (labels are on conversation, not messages)
        conversation_labels = self._fetch_conversation_labels(conversation_id)
        
        # Always fetch fresh messages from API to ensure consistency
        messages = self.client.get_conversation_messages(conversation_id)
        
        emails = []
        # Process each message
        for message_data in messages:
            try:
                # Fetch full message details to get complete body (not just preview)
                message_id = str(message_data.get("id", ""))
                if message_id:
                    full_message = self.client.get_message(message_id)
                    if full_message:
                        # Use full message data which includes complete body
                        message_data = full_message
                
                email = self._parse_message(message_data, conversation_id, conversation_labels)
                emails.append(email)
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
        
        return emails if emails else None
    
    def handle_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """
        Handle a Missive event (legacy method for backwards compatibility).
        
        Args:
            event_type: Type of event (e.g., "conversation.created", "message.received")
            payload: Event payload
        """
        emails = self.process_event(event_type, payload)
        if emails:
            for email in emails:
                self.db.upsert_email(email)
    
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
    
    def _fetch_conversation_labels(self, conversation_id: str) -> List[str]:
        """
        Fetch labels from a conversation.
        Labels are stored on the conversation object, not individual messages.
        
        Args:
            conversation_id: Conversation ID
        
        Returns:
            List of label names
        """
        try:
            conversation = self.client.get_conversation(conversation_id)
            if conversation:
                shared_label_names = conversation.get("shared_label_names", "")
                
                # Parse comma-separated label names into a list
                if shared_label_names:
                    # Split by comma and strip whitespace from each label
                    labels = [label.strip() for label in shared_label_names.split(",") if label.strip()]
                    logger.debug(f"Found {len(labels)} labels for conversation {conversation_id}: {labels}")
                    return labels
        except Exception as e:
            logger.error(f"Error fetching conversation labels for {conversation_id}: {e}", exc_info=True)
        
        return []
    
    def _parse_message(self, data: Dict[str, Any], conversation_id: str, conversation_labels: List[str] = None) -> Email:
        """
        Parse Missive message data into Email model.
        
        Args:
            data: Message data from Missive API
            conversation_id: Conversation ID
            conversation_labels: Labels from the conversation (labels are on conversation, not messages)
        
        Returns:
            Email object
        """
        message_id = str(data.get("id", ""))
        
        # Parse dates
        sent_at = None
        received_at = None
        
        # Try to parse delivered_at (Unix timestamp)
        if data.get("delivered_at"):
            try:
                # delivered_at is a Unix timestamp
                if isinstance(data["delivered_at"], int):
                    sent_at = datetime.fromtimestamp(data["delivered_at"], tz=timezone.utc)
                    received_at = sent_at
                else:
                    # Sometimes it might be ISO format
                    sent_at = datetime.fromisoformat(str(data["delivered_at"]).replace("Z", "+00:00"))
                    received_at = sent_at
            except (ValueError, AttributeError, OSError):
                pass
        
        # Fallback to created_at if delivered_at is not available
        if not received_at and data.get("created_at"):
            try:
                if isinstance(data["created_at"], int):
                    received_at = datetime.fromtimestamp(data["created_at"], tz=timezone.utc)
                else:
                    received_at = datetime.fromisoformat(str(data["created_at"]).replace("Z", "+00:00"))
            except (ValueError, AttributeError, OSError):
                pass
        
        # Parse from address and name
        from_address = None
        from_name = None
        from_field = data.get("from_field", data.get("from"))
        if from_field:
            if isinstance(from_field, dict):
                from_address = from_field.get("address") or from_field.get("email")
                from_name = from_field.get("name")
            elif isinstance(from_field, str):
                from_address = from_field
        
        # Parse to addresses and names
        to_addresses, to_names = self._parse_email_fields(data.get("to_fields", data.get("to", [])))
        cc_addresses, cc_names = self._parse_email_fields(data.get("cc_fields", data.get("cc", [])))
        bcc_addresses, bcc_names = self._parse_email_fields(data.get("bcc_fields", data.get("bcc", [])))
        
        # Parse in_reply_to
        in_reply_to = data.get("in_reply_to", [])
        if not isinstance(in_reply_to, list):
            in_reply_to = [in_reply_to] if in_reply_to else []
        
        # Parse body
        # Missive API returns HTML in the "body" field, not in "body_html"
        body_html = data.get("body", "")
        
        # Convert HTML to plain text for body_text
        body_text = ""
        if body_html:
            body_text = self._html_to_text(body_html)
        
        # Fallback to preview if body is empty
        if not body_html and data.get("preview"):
            body_text = data.get("preview", "")
            body_html = ""
        
        # Use labels from conversation (labels are on conversation, not individual messages)
        labels = conversation_labels if conversation_labels else []
        
        # Categorize labels
        categorized_labels = {}
        if labels:
            label_categories = get_label_categories()
            categorized_labels = label_categories.categorize(labels)
        
        # Parse draft status
        draft = data.get("draft", False)
        
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
            from_name=from_name,
            to_addresses=to_addresses,
            to_names=to_names,
            cc_addresses=cc_addresses,
            cc_names=cc_names,
            bcc_addresses=bcc_addresses,
            bcc_names=bcc_names,
            in_reply_to=in_reply_to,
            body_text=body_text,
            body_html=body_html,
            sent_at=sent_at,
            received_at=received_at or sent_at,
            labels=labels,
            categorized_labels=categorized_labels,
            draft=draft,
            deleted=deleted,
            deleted_at=deleted_at,
            source_links={"missive_url": data.get("web_url", "")} if data.get("web_url") else {},
            attachments=attachments
        )
    
    def _parse_email_addresses(self, addresses: Any) -> List[str]:
        """Parse email addresses from various formats (legacy method)."""
        result, _ = self._parse_email_fields(addresses)
        return result
    
    def _parse_email_fields(self, addresses: Any) -> tuple[List[str], List[str]]:
        """Parse email addresses and names from various formats.
        
        Returns:
            Tuple of (addresses, names) lists
        """
        if not addresses:
            return [], []
        
        if isinstance(addresses, str):
            return [addresses], []
        
        if isinstance(addresses, list):
            result_addresses = []
            result_names = []
            for addr in addresses:
                if isinstance(addr, dict):
                    email = addr.get("address") or addr.get("email")
                    name = addr.get("name")
                    if email:
                        result_addresses.append(email)
                        result_names.append(name or "")
                elif isinstance(addr, str):
                    result_addresses.append(addr)
                    result_names.append("")
            return result_addresses, result_names
        
        return [], []
    
    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text."""
        if not html:
            return ""
        
        # Remove script and style elements
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        
        # Replace common block elements with newlines
        text = re.sub(r'</(div|p|br|tr|h[1-6]|li)>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        
        # Remove all remaining HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Decode HTML entities
        text = unescape(text)
        
        # Clean up whitespace
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)
        # Replace multiple newlines with double newline
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        # Remove leading/trailing whitespace from each line
        text = '\n'.join(line.strip() for line in text.split('\n'))
        # Remove leading/trailing whitespace from entire text
        text = text.strip()
        
        return text
    
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

