"""Missive webhook management via API."""
import json
import requests
from pathlib import Path
from typing import Optional, Dict, Any

from src import settings
from src.logging_conf import logger


class MissiveWebhookManager:
    """Manage Missive webhooks via API."""
    
    # Store webhook ID to delete on next run
    WEBHOOK_ID_FILE = settings.DATA_DIR / "missive_webhook_id.json"
    
    def __init__(self):
        self.api_token = settings.MISSIVE_API_TOKEN
        self.base_url = "https://public.missiveapp.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        # Events we want to subscribe to
        self.desired_events = [
            "incoming_email",
            "new_comment"
        ]
    
    def setup_webhook(self, webhook_url: str) -> bool:
        """
        Set up webhook for Missive.
        Deletes old webhook (if exists) and creates a new one.
        
        Args:
            webhook_url: The URL to send webhooks to (e.g., ngrok URL)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Setting up Missive webhook to: {webhook_url}")
            
            # Delete old webhook if exists
            old_webhook_id = self._load_webhook_id()
            if old_webhook_id:
                logger.info(f"Deleting old Missive webhook: {old_webhook_id}")
                self._delete_webhook(old_webhook_id)
            
            # Create new webhook for incoming emails
            webhook_id = self._create_webhook(webhook_url, "incoming_email")
            
            if webhook_id:
                self._save_webhook_id(webhook_id)
                logger.info("✓ Missive webhook configured successfully")
                return True
            else:
                logger.error("Failed to create Missive webhook")
                return False
        
        except Exception as e:
            logger.error(f"Failed to setup Missive webhook: {e}", exc_info=True)
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
        """Load the stored webhook ID from file."""
        try:
            if self.WEBHOOK_ID_FILE.exists():
                with open(self.WEBHOOK_ID_FILE, "r") as f:
                    data = json.load(f)
                    return data.get("webhook_id")
        except Exception as e:
            logger.debug(f"Could not load webhook ID: {e}")
        return None
    
    def _save_webhook_id(self, webhook_id: str) -> None:
        """Save the webhook ID to file."""
        try:
            self.WEBHOOK_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self.WEBHOOK_ID_FILE, "w") as f:
                json.dump({"webhook_id": webhook_id}, f)
        except Exception as e:
            logger.warning(f"Could not save webhook ID: {e}")

