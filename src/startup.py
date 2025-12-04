"""Startup module for ngrok and backfill operations."""
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from pyngrok import ngrok, conf

from src import settings
from src.logging_conf import logger
from src.queue.postgres_queue import PostgresQueue
from src.queue.models import QueueItem
from src.db.interface import DatabaseInterface
from src.db.airtable_impl import AirtableDatabase
from src.db.postgres_impl import PostgresDatabase
from src.db.models import Checkpoint
from src.db.airtable_setup import AirtableSetup
from src.connectors.teamwork_client import TeamworkClient
from src.connectors.missive_client import MissiveClient
from src.connectors.label_categories import get_label_categories
from src.webhooks.teamwork_webhooks import TeamworkWebhookManager
from src.webhooks.missive_webhooks import MissiveWebhookManager


class StartupManager:
    """Manages startup operations including ngrok and backfill."""
    
    def __init__(self):
        self.db = self._create_database()
        self.queue = PostgresQueue(self.db)  # Pass db instance, not conn
        self.teamwork_client = TeamworkClient()
        self.missive_client = MissiveClient()
        self.ngrok_tunnel = None
    
    def _create_database(self) -> DatabaseInterface:
        """Create database instance based on configuration.
        
        Will retry indefinitely until database is available.
        """
        delay = settings.DB_RECONNECT_DELAY
        
        while True:
            try:
                if settings.DB_BACKEND == "airtable":
                    return AirtableDatabase()
                elif settings.DB_BACKEND == "postgres":
                    return PostgresDatabase()
                else:
                    raise ValueError(f"Invalid DB_BACKEND: {settings.DB_BACKEND}")
            except ValueError:
                raise  # Re-raise config errors
            except Exception as e:
                logger.warning(
                    f"Failed to initialize database: {e}. "
                    f"Retrying in {delay}s..."
                )
                time.sleep(delay)
                delay = min(delay * 2, settings.DB_MAX_RECONNECT_DELAY)
    
    def start_ngrok(self) -> Optional[str]:
        """
        Start ngrok tunnel and return the public URL.
        
        Returns:
            Public URL or None if ngrok is not configured or webhooks are disabled
        """
        if settings.DISABLE_WEBHOOKS:
            logger.info("Webhooks disabled. Skipping ngrok setup.")
            return None
        
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
        
        # Create base tables
        if not setup.ensure_tables_exist():
            return False
        
        # Create category columns
        label_categories = get_label_categories()
        category_names = label_categories.get_category_names()
        
        if category_names:
            logger.info(f"Setting up category columns: {', '.join(category_names)}")
            if not setup.ensure_category_columns(category_names):
                logger.warning("Failed to setup category columns, but continuing...")
        else:
            logger.info("No label categories configured, skipping category column creation")
        
        return True
    
    def configure_webhooks(self, public_url: str) -> None:
        """Automatically configure webhooks with the given URL."""
        if settings.DISABLE_WEBHOOKS:
            logger.info("Webhooks disabled. Skipping webhook configuration.")
            return
        
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
            # Use updated date for subsequent syncs (always include completed tasks to capture status changes)
            tasks = self.teamwork_client.get_tasks_updated_since(since, include_completed=True)
        else:
            # First run - use TEAMWORK_PROCESS_AFTER if set, otherwise default to 15 years
            include_completed = settings.INCLUDE_COMPLETED_TASKS_ON_INITIAL_SYNC
            logger.info(f"Initial sync: including completed tasks = {include_completed}")
            
            if settings.TEAMWORK_PROCESS_AFTER:
                try:
                    since = datetime.strptime(settings.TEAMWORK_PROCESS_AFTER, "%d.%m.%Y")
                    since = since.replace(tzinfo=timezone.utc)
                    logger.info(f"First run: fetching Teamwork tasks created since {settings.TEAMWORK_PROCESS_AFTER}")
                    # Use created date for first run
                    tasks = self.teamwork_client.get_tasks_created_since(since, include_completed=include_completed)
                except ValueError:
                    logger.error(f"Invalid TEAMWORK_PROCESS_AFTER format: {settings.TEAMWORK_PROCESS_AFTER}. Using default 15 years.")
                    since = datetime.now(timezone.utc) - timedelta(days=5475)  # 15 years
                    logger.info(f"First run: fetching Teamwork tasks from last 15 years")
                    tasks = self.teamwork_client.get_tasks_updated_since(since, include_completed=include_completed)
            else:
                # Default to 15 years if no filter is set
                since = datetime.now(timezone.utc) - timedelta(days=5475)  # 15 years
                logger.info(f"First run: fetching Teamwork tasks from last 15 years")
                tasks = self.teamwork_client.get_tasks_updated_since(since, include_completed=include_completed)

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
                    payload={}
                )
                self.queue.enqueue(item)
            
            except Exception as e:
                logger.error(f"Error enqueueing Teamwork task: {e}", exc_info=True)
        
        # Update checkpoint to current time (since API call succeeded)
        # This happens even if 0 tasks were found, to advance the checkpoint
        latest_time = datetime.now(timezone.utc)
        
        # If we found tasks, try to use the latest task timestamp
        if tasks:
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
            # First run - use MISSIVE_PROCESS_AFTER if set, otherwise default to 30 days
            if settings.MISSIVE_PROCESS_AFTER:
                try:
                    since = datetime.strptime(settings.MISSIVE_PROCESS_AFTER, "%d.%m.%Y")
                    since = since.replace(tzinfo=timezone.utc)
                    logger.info(f"First run: fetching Missive conversations from {settings.MISSIVE_PROCESS_AFTER} onwards")
                except ValueError:
                    logger.error(f"Invalid MISSIVE_PROCESS_AFTER format: {settings.MISSIVE_PROCESS_AFTER}. Using default 30 days.")
                    since = datetime.now(timezone.utc) - timedelta(days=30)
                    logger.info(f"First run: fetching Missive conversations from last 30 days")
            else:
                # Default to 30 days if no filter is set
                since = datetime.now(timezone.utc) - timedelta(days=30)
                logger.info(f"First run: fetching Missive conversations from last 30 days")
        
        # Fetch conversations - this will raise exception if API call fails
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
                    payload={}
                )
                self.queue.enqueue(item)
            
            except Exception as e:
                logger.error(f"Error enqueueing Missive conversation: {e}", exc_info=True)
        
        # Update checkpoint to current time (since API call succeeded)
        # This happens even if 0 conversations were found, to advance the checkpoint
        latest_time = datetime.now(timezone.utc)
        
        # If we found conversations, try to use the latest conversation timestamp
        if conversations:
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
        
        # Start ngrok (unless webhooks are disabled)
        public_url = manager.start_ngrok()
        
        if settings.DISABLE_WEBHOOKS:
            logger.info("="*70)
            logger.info("POLLING MODE ACTIVE")
            logger.info("="*70)
            logger.info(f"Periodic backfill interval: {settings.PERIODIC_BACKFILL_INTERVAL} seconds")
            logger.info("No webhooks will be configured. System relies on periodic polling.")
            logger.info("="*70)
        elif public_url:
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

