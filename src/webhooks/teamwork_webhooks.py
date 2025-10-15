"""Teamwork webhook management via API."""
import json
import requests
from typing import List, Dict, Any, Optional
from requests.auth import HTTPBasicAuth

from src import settings
from src.logging_conf import logger


class TeamworkWebhookManager:
    """Manage Teamwork webhooks via API."""
    
    # Store webhook IDs to delete on next run
    WEBHOOK_IDS_FILE = settings.DATA_DIR / "teamwork_webhook_ids.json"
    
    def __init__(self):
        self.base_url = settings.TEAMWORK_BASE_URL
        self.api_key = settings.TEAMWORK_API_KEY
        self.auth = HTTPBasicAuth(self.api_key, "")
        
        # Events we want to subscribe to
        self.desired_events = [
            "task.created",
            "task.updated",
            "task.deleted",
            "task.completed",
        ]
    
    def setup_webhooks(self, webhook_url: str) -> bool:
        """
        Set up webhooks for Teamwork.
        Deletes old webhooks (if exist) and creates new ones.
        
        Args:
            webhook_url: The URL to send webhooks to (e.g., ngrok URL)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Setting up Teamwork webhooks to: {webhook_url}")
            
            # Delete old webhooks if they exist
            old_webhook_ids = self._load_webhook_ids()
            if old_webhook_ids:
                logger.info(f"Deleting {len(old_webhook_ids)} old Teamwork webhooks")
                for webhook_id in old_webhook_ids:
                    self._delete_webhook(webhook_id)
            
            # Create new webhooks for each event
            logger.info(f"Creating new webhooks for {len(self.desired_events)} events")
            new_webhook_ids = []
            for event in self.desired_events:
                webhook_id = self._create_webhook(webhook_url, event)
                if webhook_id:
                    new_webhook_ids.append(webhook_id)
            
            # Save new webhook IDs
            if new_webhook_ids:
                self._save_webhook_ids(new_webhook_ids)
                logger.info("✓ Teamwork webhooks configured successfully")
                return True
            else:
                logger.error("Failed to create any Teamwork webhooks")
                return False
        
        except Exception as e:
            logger.error(f"Failed to setup Teamwork webhooks: {e}", exc_info=True)
            logger.warning("You may need to configure Teamwork webhooks manually")
            logger.info(f"  Go to: {self.base_url}/settings/webhooks")
            logger.info(f"  Add webhook URL: {webhook_url}")
            logger.info(f"  Select events: {', '.join(self.desired_events)}")
            return False
    
    def _create_webhook(self, url: str, event: str) -> Optional[str]:
        """Create a new webhook and return its ID."""
        try:
            data = {
                "webhook": {
                    "url": url,
                    "event": event,
                    "active": True
                }
            }
            
            response = requests.post(
                f"{self.base_url}/projects/api/v1/webhooks.json",
                auth=self.auth,
                json=data,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                },
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                # Try multiple possible response structures
                webhook_id = result.get("webhook", {}).get("id") or result.get("id")
                
                if webhook_id:
                    logger.info(f"✓ Created webhook for event: {event} (ID: {webhook_id})")
                    return str(webhook_id)
                else:
                    logger.warning(f"Webhook created but no ID found in response: {result}")
                    return None
            else:
                logger.warning(f"Failed to create webhook for {event}: {response.status_code}")
                logger.debug(f"Response: {response.text}")
                return None
        
        except Exception as e:
            logger.warning(f"Could not create webhook for {event}: {e}")
            return None
    
    def _delete_webhook(self, webhook_id: str) -> bool:
        """Delete a webhook by ID."""
        try:
            response = requests.delete(
                f"{self.base_url}/projects/api/v1/webhooks/{webhook_id}.json",
                auth=self.auth,
                headers={"Accept": "application/json"},
                timeout=10
            )
            
            if response.status_code in [200, 204]:
                logger.info(f"✓ Deleted old Teamwork webhook {webhook_id}")
                return True
            elif response.status_code == 404:
                logger.info(f"Old webhook {webhook_id} no longer exists (404)")
                return True
            else:
                logger.warning(f"Failed to delete webhook {webhook_id}: {response.status_code}")
                return False
        
        except Exception as e:
            logger.warning(f"Could not delete webhook {webhook_id}: {e}")
            return False
    
    def _load_webhook_ids(self) -> List[str]:
        """Load the stored webhook IDs from file."""
        try:
            if self.WEBHOOK_IDS_FILE.exists():
                with open(self.WEBHOOK_IDS_FILE, "r") as f:
                    data = json.load(f)
                    return data.get("webhook_ids", [])
        except Exception as e:
            logger.debug(f"Could not load webhook IDs: {e}")
        return []
    
    def _save_webhook_ids(self, webhook_ids: List[str]) -> None:
        """Save the webhook IDs to file."""
        try:
            self.WEBHOOK_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self.WEBHOOK_IDS_FILE, "w") as f:
                json.dump({"webhook_ids": webhook_ids}, f)
        except Exception as e:
            logger.warning(f"Could not save webhook IDs: {e}")
    
    def print_manual_setup_instructions(self, webhook_url: str):
        """Print manual setup instructions."""
        print("\n" + "="*70)
        print("TEAMWORK WEBHOOK SETUP (Manual)")
        print("="*70)
        print(f"\nAutomatic setup failed. Please configure manually:")
        print(f"\n1. Go to: {self.base_url}/settings/webhooks")
        print(f"2. Click 'Add Webhook'")
        print(f"3. Enter URL: {webhook_url}")
        print(f"4. Select these events:")
        for event in self.desired_events:
            print(f"   - {event}")
        print(f"5. Click 'Save'")
        print("="*70 + "\n")

