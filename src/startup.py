"""Startup module for ngrok and backfill operations."""
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from pyngrok import ngrok, conf

from src import settings
from src.logging_conf import logger
from src.queue.file_queue import FileQueue
from src.queue.models import QueueItem
from src.db.interface import DatabaseInterface
from src.db.airtable_impl import AirtableDatabase
from src.db.postgres_impl import PostgresDatabase
from src.db.models import Checkpoint
from src.db.airtable_setup import AirtableSetup
from src.connectors.teamwork_client import TeamworkClient
from src.connectors.missive_client import MissiveClient
from src.webhooks.teamwork_webhooks import TeamworkWebhookManager
from src.webhooks.missive_webhooks import MissiveWebhookManager


class StartupManager:
    """Manages startup operations including ngrok and backfill."""
    
    def __init__(self):
        self.queue = FileQueue()
        self.db = self._create_database()
        self.teamwork_client = TeamworkClient()
        self.missive_client = MissiveClient()
        self.ngrok_tunnel = None
    
    def _create_database(self) -> DatabaseInterface:
        """Create database instance based on configuration."""
        if settings.DB_BACKEND == "airtable":
            return AirtableDatabase()
        elif settings.DB_BACKEND == "postgres":
            return PostgresDatabase()
        else:
            raise ValueError(f"Invalid DB_BACKEND: {settings.DB_BACKEND}")
    
    def start_ngrok(self) -> Optional[str]:
        """
        Start ngrok tunnel and return the public URL.
        
        Returns:
            Public URL or None if ngrok is not configured
        """
        if not settings.NGROK_AUTHTOKEN:
            logger.warning("NGROK_AUTHTOKEN not configured. Skipping ngrok setup.")
            logger.info("For local development, you need to manually expose your webhook endpoints.")
            return None
        
        try:
            # Set auth token
            conf.get_default().auth_token = settings.NGROK_AUTHTOKEN
            
            # Start tunnel
            logger.info(f"Starting ngrok tunnel on port {settings.APP_PORT}...")
            self.ngrok_tunnel = ngrok.connect(settings.APP_PORT, bind_tls=True)
            public_url = self.ngrok_tunnel.public_url
            
            logger.info(f"✓ ngrok tunnel established: {public_url}")
            logger.info(f"  Teamwork webhook URL: {public_url}/webhook/teamwork")
            logger.info(f"  Missive webhook URL: {public_url}/webhook/missive")
            
            return public_url
        
        except Exception as e:
            logger.error(f"Failed to start ngrok tunnel: {e}", exc_info=True)
            return None
    
    def ensure_airtable_tables(self) -> bool:
        """Ensure Airtable tables exist, creating them if necessary."""
        if settings.DB_BACKEND != "airtable":
            return True  # Not using Airtable, skip
        
        logger.info("Setting up Airtable tables...")
        setup = AirtableSetup()
        return setup.ensure_tables_exist()
    
    def configure_webhooks(self, public_url: str) -> None:
        """Automatically configure webhooks with the given URL."""
        if not public_url:
            logger.warning("No public URL available. Skipping webhook configuration.")
            return
        
        teamwork_webhook_url = f"{public_url}/webhook/teamwork"
        missive_webhook_url = f"{public_url}/webhook/missive"
        
        # Configure Teamwork webhooks (automatic)
        logger.info("Configuring Teamwork webhooks...")
        teamwork_manager = TeamworkWebhookManager()
        teamwork_success = teamwork_manager.setup_webhooks(teamwork_webhook_url)
        
        if not teamwork_success:
            teamwork_manager.print_manual_setup_instructions(teamwork_webhook_url)
        
        # Configure Missive webhook (automatic - deletes old, creates new)
        logger.info("Configuring Missive webhook...")
        missive_manager = MissiveWebhookManager()
        missive_manager.setup_webhook(missive_webhook_url)
    
    def stop_ngrok(self):
        """Stop ngrok tunnel."""
        if self.ngrok_tunnel:
            try:
                ngrok.disconnect(self.ngrok_tunnel.public_url)
                logger.info("ngrok tunnel stopped")
            except Exception as e:
                logger.error(f"Error stopping ngrok: {e}")
    
    def perform_backfill(self):
        """Perform startup backfill to catch missed events."""
        logger.info("Starting backfill operation...")
        
        # Backfill Teamwork tasks
        try:
            self._backfill_teamwork()
        except Exception as e:
            logger.error(f"Error during Teamwork backfill: {e}", exc_info=True)
        
        # Backfill Missive conversations
        try:
            self._backfill_missive()
        except Exception as e:
            logger.error(f"Error during Missive backfill: {e}", exc_info=True)
        
        logger.info("Backfill operation completed")
    
    def _backfill_teamwork(self):
        """Backfill Teamwork tasks."""
        logger.info("Backfilling Teamwork tasks...")
        
        # Get last checkpoint
        checkpoint = self.db.get_checkpoint("teamwork")
        
        if checkpoint:
            # Fetch tasks updated since checkpoint with overlap window
            since = checkpoint.last_event_time - timedelta(seconds=settings.BACKFILL_OVERLAP_SECONDS)
            logger.info(f"Fetching Teamwork tasks updated since {since.isoformat()}")
        else:
            # First run, fetch tasks from last 24 hours
            since = datetime.now(timezone.utc) - timedelta(hours=24)
            logger.info(f"First run: fetching Teamwork tasks from last 24 hours")
        
        # Fetch tasks
        tasks = self.teamwork_client.get_tasks_updated_since(since, include_deleted=True)
        logger.info(f"Found {len(tasks)} Teamwork tasks to backfill")
        
        # Enqueue each task
        for task_data in tasks:
            try:
                task_id = str(task_data.get("id", ""))
                if not task_id:
                    continue
                
                item = QueueItem.create(
                    source="teamwork",
                    event_type="task.backfill",
                    external_id=task_id,
                    payload={"task": task_data}
                )
                self.queue.enqueue(item)
            
            except Exception as e:
                logger.error(f"Error enqueueing Teamwork task: {e}", exc_info=True)
        
        # Update checkpoint
        if tasks:
            # Find the latest updated_at timestamp
            latest_time = datetime.now(timezone.utc)
            for task_data in tasks:
                if task_data.get("updatedAt"):
                    try:
                        task_time = datetime.fromisoformat(task_data["updatedAt"].replace("Z", "+00:00"))
                        if task_time > latest_time:
                            latest_time = task_time
                    except (ValueError, AttributeError):
                        pass
            
            checkpoint = Checkpoint(
                source="teamwork",
                last_event_time=latest_time
            )
            self.db.set_checkpoint(checkpoint)
            logger.info(f"Updated Teamwork checkpoint to {latest_time.isoformat()}")
    
    def _backfill_missive(self):
        """Backfill Missive conversations."""
        logger.info("Backfilling Missive conversations...")
        
        # Get last checkpoint
        checkpoint = self.db.get_checkpoint("missive")
        
        if checkpoint:
            # Fetch conversations updated since checkpoint with overlap window
            since = checkpoint.last_event_time - timedelta(seconds=settings.BACKFILL_OVERLAP_SECONDS)
            logger.info(f"Fetching Missive conversations updated since {since.isoformat()}")
        else:
            # First run, fetch conversations from last 24 hours
            since = datetime.now(timezone.utc) - timedelta(hours=24)
            logger.info(f"First run: fetching Missive conversations from last 24 hours")
        
        # Fetch conversations
        conversations = self.missive_client.get_conversations_updated_since(since)
        logger.info(f"Found {len(conversations)} Missive conversations to backfill")
        
        # Enqueue each conversation
        for conv_data in conversations:
            try:
                conv_id = str(conv_data.get("id", ""))
                if not conv_id:
                    continue
                
                item = QueueItem.create(
                    source="missive",
                    event_type="conversation.backfill",
                    external_id=conv_id,
                    payload={"conversation": conv_data}
                )
                self.queue.enqueue(item)
            
            except Exception as e:
                logger.error(f"Error enqueueing Missive conversation: {e}", exc_info=True)
        
        # Update checkpoint
        if conversations:
            # Find the latest updated_at timestamp
            latest_time = datetime.now(timezone.utc)
            for conv_data in conversations:
                if conv_data.get("updated_at"):
                    try:
                        conv_time = datetime.fromisoformat(conv_data["updated_at"].replace("Z", "+00:00"))
                        if conv_time > latest_time:
                            latest_time = conv_time
                    except (ValueError, AttributeError):
                        pass
            
            checkpoint = Checkpoint(
                source="missive",
                last_event_time=latest_time
            )
            self.db.set_checkpoint(checkpoint)
            logger.info(f"Updated Missive checkpoint to {latest_time.isoformat()}")
    
    def cleanup(self):
        """Cleanup resources."""
        self.stop_ngrok()
        self.db.close()


def main():
    """Entry point for startup operations."""
    try:
        settings.validate_config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    
    manager = StartupManager()
    
    try:
        # Ensure Airtable tables exist (if using Airtable)
        if not manager.ensure_airtable_tables():
            logger.error("Failed to setup Airtable tables. Check permissions.")
            logger.info("Ensure your API key has schema.bases:write scope")
        
        # Start ngrok
        public_url = manager.start_ngrok()
        
        if public_url:
            print("\n" + "="*70)
            print("WEBHOOK URLS - Configure these in Teamwork and Missive:")
            print("="*70)
            print(f"Teamwork: {public_url}/webhook/teamwork")
            print(f"Missive:  {public_url}/webhook/missive")
            print("="*70 + "\n")
            
            # Automatically configure webhooks
            manager.configure_webhooks(public_url)
        
        # Perform backfill
        manager.perform_backfill()
        
        logger.info("Startup operations completed successfully")
        logger.info("Keep this process running to maintain ngrok tunnel")
        logger.info("Press Ctrl+C to stop")
        
        # Keep running to maintain ngrok tunnel
        if public_url:
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
    
    except Exception as e:
        logger.error(f"Fatal error during startup: {e}", exc_info=True)
        sys.exit(1)
    
    finally:
        manager.cleanup()


if __name__ == "__main__":
    main()

