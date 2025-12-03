"""Worker dispatcher that processes the queue."""
import time
import signal
import sys
from typing import Optional

from src import settings
from src.logging_conf import logger
from src.queue.postgres_queue import PostgresQueue
from src.queue.models import QueueItem
from src.db.interface import DatabaseInterface
from src.db.airtable_impl import AirtableDatabase
from src.db.postgres_impl import PostgresDatabase
from src.workers.handlers.teamwork_events import TeamworkEventHandler
from src.workers.handlers.missive_events import MissiveEventHandler


class WorkerDispatcher:
    """Dispatcher that processes queued events."""
    
    def __init__(self):
        self.db = self._create_database()
        self.queue = PostgresQueue(self.db.conn)
        self.teamwork_handler = TeamworkEventHandler(self.db)
        self.missive_handler = MissiveEventHandler(self.db)
        self.running = True
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _create_database(self) -> DatabaseInterface:
        """Create database instance based on configuration."""
        try:
            if settings.DB_BACKEND == "airtable":
                logger.info("Using Airtable database")
                return AirtableDatabase()
            elif settings.DB_BACKEND == "postgres":
                logger.info("Using PostgreSQL database")
                return PostgresDatabase()
            else:
                raise ValueError(f"Invalid DB_BACKEND: {settings.DB_BACKEND}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}", exc_info=True)
            raise
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}. Shutting down gracefully...")
        self.running = False
    
    def run(self):
        """Main worker loop."""
        logger.info("Worker dispatcher started")
        
        while self.running:
            try:
                # Get up to 10 items from queue
                items = self.queue.dequeue_batch(max_items=10)
                
                if not items:
                    # Queue is empty, sleep briefly and check again
                    time.sleep(0.5)
                    continue
                
                # Process the batch
                try:
                    self._process_batch(items)
                    logger.info(
                        f"Successfully processed batch of {len(items)} events"
                    )
                
                except Exception as e:
                    error_msg = f"Error processing batch: {e}"
                    logger.error(error_msg, exc_info=True)
                    # Mark all items as failed for retry
                    self.queue.mark_batch_failed(items, error_msg)
            
            except Exception as e:
                logger.error(f"Unexpected error in worker loop: {e}", exc_info=True)
                time.sleep(5)  # Back off on unexpected errors
        
        # Cleanup
        logger.info("Worker dispatcher shutting down")
        self.db.close()
    
    def _process_batch(self, items: list) -> None:
        """
        Process a batch of queue items.
        
        Args:
            items: List of QueueItems to process
        """
        from src.db.models import Email, Task
        
        # Separate items by source
        teamwork_items = [item for item in items if item.source == "teamwork"]
        missive_items = [item for item in items if item.source == "missive"]
        
        # Process Teamwork items
        if teamwork_items:
            # Track items and their corresponding tasks for proper completion marking
            item_task_pairs = []  # List of (item, task_or_none)
            
            for item in teamwork_items:
                try:
                    payload = dict(item.payload or {})
                    payload.setdefault("id", item.external_id)
                    
                    # Collect tasks from handler
                    task = self.teamwork_handler.process_event(item.event_type, payload)
                    item_task_pairs.append((item, task))
                    
                except Exception as e:
                    logger.error(f"Error processing teamwork item {item.external_id}: {e}", exc_info=True)
                    self.queue.mark_item_failed(item, str(e), retry=True)
            
            # Batch upsert tasks - only mark completed AFTER successful DB operations
            tasks = [task for _, task in item_task_pairs if task]
            if tasks:
                try:
                    self.db.upsert_tasks_batch(tasks)
                    
                    # Link tags and assignees if using relational structure
                    if hasattr(self.db, 'link_task_tags'):
                        for task in tasks:
                            try:
                                # Link tags if available
                                tag_ids = task.raw.get("_tag_ids_to_link", [])
                                if tag_ids:
                                    self.db.link_task_tags(task.task_id, tag_ids)
                                
                                # Link assignees if available
                                assignee_user_ids = task.raw.get("_assignee_user_ids_to_link", [])
                                if assignee_user_ids:
                                    self.db.link_task_assignees(task.task_id, assignee_user_ids)
                            except Exception as e:
                                logger.error(f"Error linking task {task.task_id} relationships: {e}", exc_info=True)
                    
                    # Mark all items as completed only after successful batch upsert
                    for item, _ in item_task_pairs:
                        self.queue.mark_item_completed(item)
                        
                except Exception as e:
                    logger.warning(f"Batch upsert failed, falling back to individual processing: {e}")
                    # Fallback: process each item individually to isolate failures
                    self._process_teamwork_items_individually(item_task_pairs)
            else:
                # No tasks to upsert, mark items as completed (e.g., deleted tasks)
                for item, _ in item_task_pairs:
                    self.queue.mark_item_completed(item)
        
        # Process Missive items
        if missive_items:
            # Track items and their corresponding emails for proper completion marking
            item_email_pairs = []  # List of (item, emails_list_or_none)
            
            for item in missive_items:
                try:
                    payload = dict(item.payload or {})
                    payload.setdefault("conversation_id", item.external_id)
                    payload.setdefault("id", item.external_id)
                    
                    # Collect emails from handler
                    item_emails = self.missive_handler.process_event(item.event_type, payload)
                    item_email_pairs.append((item, item_emails))
                    
                except Exception as e:
                    logger.error(f"Error processing missive item {item.external_id}: {e}", exc_info=True)
                    self.queue.mark_item_failed(item, str(e), retry=True)
            
            # Batch upsert emails
            all_emails = []
            for _, emails in item_email_pairs:
                if emails:
                    all_emails.extend(emails)
            
            if all_emails:
                try:
                    self.db.upsert_emails_batch(all_emails)
                    # Mark all items as completed only after successful batch upsert
                    for item, _ in item_email_pairs:
                        self.queue.mark_item_completed(item)
                except Exception as e:
                    logger.warning(f"Batch email upsert failed, falling back to individual processing: {e}")
                    # Fallback: process each item individually
                    self._process_missive_items_individually(item_email_pairs)
            else:
                # No emails to upsert, mark items as completed
                for item, _ in item_email_pairs:
                    self.queue.mark_item_completed(item)
    
    def _process_teamwork_items_individually(self, item_task_pairs: list) -> None:
        """
        Process teamwork items one by one when batch processing fails.
        This isolates failing items so others can succeed.
        """
        for item, task in item_task_pairs:
            if task:
                try:
                    self.db.upsert_tasks_batch([task])
                    
                    # Link tags and assignees
                    if hasattr(self.db, 'link_task_tags'):
                        tag_ids = task.raw.get("_tag_ids_to_link", [])
                        if tag_ids:
                            self.db.link_task_tags(task.task_id, tag_ids)
                        
                        assignee_user_ids = task.raw.get("_assignee_user_ids_to_link", [])
                        if assignee_user_ids:
                            self.db.link_task_assignees(task.task_id, assignee_user_ids)
                    
                    self.queue.mark_item_completed(item)
                    logger.debug(f"Successfully processed task {task.task_id} individually")
                except Exception as e:
                    error_msg = f"Individual task upsert failed for {task.task_id}: {e}"
                    logger.error(error_msg)
                    self.queue.mark_item_failed(item, error_msg, retry=True)
            else:
                # No task (e.g., deletion event) - mark as completed
                self.queue.mark_item_completed(item)
    
    def _process_missive_items_individually(self, item_email_pairs: list) -> None:
        """
        Process missive items one by one when batch processing fails.
        This isolates failing items so others can succeed.
        """
        for item, emails in item_email_pairs:
            if emails:
                try:
                    self.db.upsert_emails_batch(emails)
                    self.queue.mark_item_completed(item)
                    logger.debug(f"Successfully processed emails for {item.external_id} individually")
                except Exception as e:
                    error_msg = f"Individual email upsert failed for {item.external_id}: {e}"
                    logger.error(error_msg)
                    self.queue.mark_item_failed(item, error_msg, retry=True)
            else:
                # No emails - mark as completed
                self.queue.mark_item_completed(item)
    
    def _process_item(self, item: QueueItem) -> None:
        """
        Process a single queue item (legacy method, kept for compatibility).
        
        Args:
            item: Queue item to process
        """
        # Enrich payload with external ID so handlers can operate with ID-only queue items
        payload = dict(item.payload or {})
        if item.source == "teamwork":
            payload.setdefault("id", item.external_id)
            self.teamwork_handler.handle_event(item.event_type, payload)
        elif item.source == "missive":
            # For Missive, prefer conversation ID
            payload.setdefault("conversation_id", item.external_id)
            payload.setdefault("id", item.external_id)
            self.missive_handler.handle_event(item.event_type, payload)
        else:
            logger.warning(f"Unknown source: {item.source}")


def main():
    """Entry point for worker process."""
    try:
        settings.validate_config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    
    dispatcher = WorkerDispatcher()
    
    try:
        dispatcher.run()
    except Exception as e:
        logger.error(f"Fatal error in dispatcher: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

