"""Teamwork webhook management via API."""
import requests
from typing import List, Dict, Any, Optional
from requests.auth import HTTPBasicAuth

from src import settings
from src.logging_conf import logger


class TeamworkWebhookManager:
    """Manage Teamwork webhooks via API."""
    
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
        Creates or updates webhooks to point to the given URL.
        
        Args:
            webhook_url: The URL to send webhooks to (e.g., ngrok URL)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Setting up Teamwork webhooks to: {webhook_url}")
            
            # Get existing webhooks
            existing_webhooks = self._get_webhooks()
            
            # Check if we already have webhooks for our URL
            our_webhooks = [
                w for w in existing_webhooks
                if w.get("url") == webhook_url
            ]
            
            if our_webhooks:
                logger.info(f"Found {len(our_webhooks)} existing webhooks for this URL")
                # Update existing webhooks
                for webhook in our_webhooks:
                    self._update_webhook(webhook["id"], webhook_url)
                return True
            else:
                # Create new webhooks for each event
                logger.info(f"Creating new webhooks for {len(self.desired_events)} events")
                for event in self.desired_events:
                    self._create_webhook(webhook_url, event)
                
                logger.info("✓ Teamwork webhooks configured successfully")
                return True
        
        except Exception as e:
            logger.error(f"Failed to setup Teamwork webhooks: {e}", exc_info=True)
            logger.warning("You may need to configure Teamwork webhooks manually")
            logger.info(f"  Go to: {self.base_url}/settings/webhooks")
            logger.info(f"  Add webhook URL: {webhook_url}")
            logger.info(f"  Select events: {', '.join(self.desired_events)}")
            return False
    
    def _get_webhooks(self) -> List[Dict[str, Any]]:
        """Get all existing webhooks."""
        try:
            # Note: Teamwork v1 API endpoint for webhooks
            response = requests.get(
                f"{self.base_url}/projects/api/v1/webhooks.json",
                auth=self.auth,
                headers={"Accept": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("webhooks", [])
            elif response.status_code == 404:
                # Webhooks endpoint might not be available in all Teamwork plans
                logger.warning("Webhooks endpoint not available (404). May need Pro plan or higher.")
                return []
            else:
                logger.warning(f"Failed to get webhooks: {response.status_code}")
                return []
        
        except Exception as e:
            logger.warning(f"Could not retrieve existing webhooks: {e}")
            return []
    
    def _create_webhook(self, url: str, event: str) -> Optional[Dict[str, Any]]:
        """Create a new webhook."""
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
                logger.info(f"✓ Created webhook for event: {event}")
                return response.json()
            else:
                logger.warning(f"Failed to create webhook for {event}: {response.status_code}")
                logger.debug(f"Response: {response.text}")
                return None
        
        except Exception as e:
            logger.warning(f"Could not create webhook for {event}: {e}")
            return None
    
    def _update_webhook(self, webhook_id: str, url: str) -> bool:
        """Update an existing webhook."""
        try:
            data = {
                "webhook": {
                    "url": url,
                    "active": True
                }
            }
            
            response = requests.put(
                f"{self.base_url}/projects/api/v1/webhooks/{webhook_id}.json",
                auth=self.auth,
                json=data,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                },
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"✓ Updated webhook {webhook_id}")
                return True
            else:
                logger.warning(f"Failed to update webhook {webhook_id}: {response.status_code}")
                return False
        
        except Exception as e:
            logger.warning(f"Could not update webhook {webhook_id}: {e}")
            return False
    
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

