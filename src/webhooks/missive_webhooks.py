"""Missive webhook management via API."""
import requests
from typing import Dict, Optional

from src import settings
from src.logging_conf import logger
from src.db.postgres_impl import PostgresDatabase
from src.db.postgres_webhook_config import WebhookConfigManager


class MissiveWebhookManager:
    """Manage Missive webhooks via API."""
    
    def __init__(self, db: Optional[PostgresDatabase] = None):
        self.api_token = settings.MISSIVE_API_TOKEN
        self.base_url = "https://public.missiveapp.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        # Database connection for webhook config
        self.db = db or PostgresDatabase()
        self.webhook_mgr = WebhookConfigManager(self.db.conn)
        
        # Events we want to subscribe to
        self.desired_events = [
            "incoming_email",
            "new_comment"
        ]
    
    def setup_webhook(self, webhook_url: str) -> bool:
        """
        Set up webhooks for Missive.
        Deletes old webhooks (if exists) and creates new ones for all desired events.
        
        Args:
            webhook_url: The URL to send webhooks to (e.g., ngrok URL)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Setting up Missive webhooks to: {webhook_url}")
            
            # Delete old webhooks if they exist
            old_webhook_ids = self._load_webhook_ids()
            for event_type, webhook_id in old_webhook_ids.items():
                if webhook_id:
                    logger.info(f"Deleting old Missive webhook for {event_type}: {webhook_id}")
                    self._delete_webhook(webhook_id)
            
            # Create webhooks for all desired events
            created_webhooks = {}
            all_success = True
            
            for event_type in self.desired_events:
                webhook_id = self._create_webhook(webhook_url, event_type)
                if webhook_id:
                    created_webhooks[event_type] = webhook_id
                else:
                    logger.error(f"Failed to create Missive webhook for {event_type}")
                    all_success = False
            
            # Save all webhook IDs
            if created_webhooks:
                self._save_webhook_ids(created_webhooks)
                logger.info(f"✓ Missive webhooks configured successfully for: {list(created_webhooks.keys())}")
            
            return all_success
        
        except Exception as e:
            logger.error(f"Failed to setup Missive webhooks: {e}", exc_info=True)
            return False
    
    def _create_webhook(self, url: str, event_type: str) -> Optional[str]:
        """Create a new webhook and return its ID."""
        try:
            data = {
                "hooks": {
                    "type": event_type,
                    "url": url
                }
            }
            
            response = requests.post(
                f"{self.base_url}/hooks",
                headers=self.headers,
                json=data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                webhook_id = result.get("hooks", {}).get("id")
                logger.info(f"✓ Created Missive webhook for event: {event_type}")
                return webhook_id
            else:
                logger.warning(f"Failed to create Missive webhook: {response.status_code}")
                logger.debug(f"Response: {response.text}")
                return None
        
        except Exception as e:
            logger.warning(f"Could not create Missive webhook: {e}")
            return None
    
    def _delete_webhook(self, webhook_id: str) -> bool:
        """Delete a webhook by ID."""
        try:
            response = requests.delete(
                f"{self.base_url}/hooks/{webhook_id}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code in [200, 204]:
                logger.info(f"✓ Deleted old Missive webhook")
                return True
            elif response.status_code == 404:
                logger.info("Old webhook no longer exists (404)")
                return True
            else:
                logger.warning(f"Failed to delete webhook {webhook_id}: {response.status_code}")
                return False
        
        except Exception as e:
            logger.warning(f"Could not delete webhook {webhook_id}: {e}")
            return False
    
    def _load_webhook_id(self) -> Optional[str]:
        """Load the stored webhook ID from database (legacy - single webhook)."""
        ids = self._load_webhook_ids()
        # Return first available webhook ID for backwards compatibility
        for webhook_id in ids.values():
            if webhook_id:
                return webhook_id
        return None
    
    def _load_webhook_ids(self) -> Dict[str, str]:
        """Load all stored webhook IDs from database."""
        try:
            config = self.webhook_mgr.get_webhook_ids('missive')
            if config and isinstance(config, dict):
                # New format: {event_type: webhook_id, ...}
                if any(k in config for k in self.desired_events):
                    return config
                # Legacy format: {"webhook_id": "..."}
                if "webhook_id" in config:
                    return {"incoming_email": config["webhook_id"]}
            elif config and isinstance(config, str):
                # Very old format: just the ID string
                return {"incoming_email": config}
        except Exception as e:
            logger.debug(f"Could not load webhook IDs: {e}")
        return {}
    
    def _save_webhook_id(self, webhook_id: str) -> None:
        """Save the webhook ID to database (legacy - single webhook)."""
        self._save_webhook_ids({"incoming_email": webhook_id})
    
    def _save_webhook_ids(self, webhook_ids: Dict[str, str]) -> None:
        """Save all webhook IDs to database."""
        try:
            self.webhook_mgr.save_webhook_ids(
                'missive',
                webhook_ids,
                webhook_url=None
            )
        except Exception as e:
            logger.warning(f"Could not save webhook IDs: {e}")

