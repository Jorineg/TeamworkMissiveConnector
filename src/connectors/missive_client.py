"""Missive API client."""
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
import requests

from src import settings
from src.logging_conf import logger


class MissiveClient:
    """Client for Missive API."""
    
    def __init__(self):
        self.api_token = settings.MISSIVE_API_TOKEN
        self.base_url = "https://public.missiveapp.com/v1"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json"
        })
    
    def get_conversations_updated_since(self, since: datetime) -> List[Dict[str, Any]]:
        """
        Get all conversations (emails) updated since a given datetime.
        
        Note: Missive API doesn't support filtering by updated_after directly.
        This method fetches conversations using the 'all' mailbox and filters
        them client-side based on last_activity_at.
        
        Args:
            since: Datetime to fetch conversations from
        
        Returns:
            List of conversation dictionaries
        """
        conversations = []
        since_timestamp = int(since.timestamp())
        until = None
        
        while True:
            try:
                # Use 'all' mailbox to get all conversations
                params = {
                    "all": "true",
                    "limit": 50
                }
                
                # Add pagination parameter if we have it
                if until:
                    params["until"] = until
                
                response = self._request("GET", "/conversations", params=params)
                
                if response and "conversations" in response:
                    batch = response["conversations"]
                    
                    # Filter conversations by last_activity_at
                    filtered_batch = [
                        conv for conv in batch 
                        if conv.get("last_activity_at", 0) >= since_timestamp
                    ]
                    
                    conversations.extend(filtered_batch)
                    
                    logger.info(f"Fetched {len(batch)} conversations ({len(filtered_batch)} match filter) from Missive")
                    
                    # If we got fewer than limit conversations, or the oldest conversation
                    # is older than our since timestamp, we're done
                    if len(batch) < 50:
                        break
                    
                    oldest_activity = min(conv.get("last_activity_at", 0) for conv in batch)
                    if oldest_activity < since_timestamp:
                        logger.info(f"Reached conversations older than since timestamp, stopping pagination")
                        break
                    
                    # Use the oldest conversation's last_activity_at for pagination
                    until = oldest_activity
                else:
                    break
            
            except Exception as e:
                logger.error(f"Error fetching conversations from Missive: {e}", exc_info=True)
                break
        
        return conversations
    
    def get_conversation_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get all messages in a conversation."""
        try:
            response = self._request("GET", f"/conversations/{conversation_id}/messages")
            if response and "messages" in response:
                return response["messages"]
        except Exception as e:
            logger.error(f"Error fetching messages for conversation {conversation_id}: {e}", exc_info=True)
        return []
    
    def get_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full message details including complete body.
        
        Args:
            message_id: Message ID
        
        Returns:
            Full message dict with body, or None
        """
        try:
            response = self._request("GET", f"/messages/{message_id}")
            if response and "messages" in response:
                # API returns messages object with single message
                return response["messages"]
            return None
        except Exception as e:
            logger.error(f"Error fetching message {message_id}: {e}", exc_info=True)
            return None
    
    def download_attachment(self, attachment_url: str) -> Optional[bytes]:
        """
        Download an attachment from Missive.
        
        Args:
            attachment_url: URL of the attachment
        
        Returns:
            Attachment bytes or None
        """
        try:
            response = self.session.get(attachment_url, timeout=60)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Error downloading attachment from {attachment_url}: {e}", exc_info=True)
            return None
    
    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> Optional[Dict[str, Any]]:
        """
        Make an API request with retry logic.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            json_data: JSON body
            retry_count: Current retry attempt
        
        Returns:
            Response JSON or None
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                timeout=30
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.warning(f"Rate limited by Missive API. Waiting {retry_after}s...")
                time.sleep(retry_after)
                return self._request(method, endpoint, params, json_data, retry_count)
            
            # Handle server errors with exponential backoff
            if response.status_code >= 500 and retry_count < 3:
                wait_time = 2 ** retry_count
                logger.warning(f"Server error {response.status_code}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                return self._request(method, endpoint, params, json_data, retry_count + 1)
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Missive API request failed: {e}", exc_info=True)
            
            # Retry on connection errors
            if retry_count < 3 and isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                wait_time = 2 ** retry_count
                logger.info(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)
                return self._request(method, endpoint, params, json_data, retry_count + 1)
            
            return None

