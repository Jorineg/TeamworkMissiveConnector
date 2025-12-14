"""Worker dispatcher that processes the queue with database resilience."""
import time
import signal
import sys
from typing import Optional

from src import settings
from src.logging_conf import logger
from src.queue.postgres_queue import PostgresQueue
from src.queue.models import QueueItem
from src.db.postgres_impl import PostgresDatabase
from src.workers.handlers.teamwork_events import TeamworkEventHandler
from src.workers.handlers.missive_events import MissiveEventHandler
from src.workers.handlers.craft_events import CraftEventHandler


class WorkerDispatcher:
    """Dispatcher that processes queued events with database resilience."""
    
    def __init__(self):
        self.db: Optional[PostgresDatabase] = None
        self.queue: Optional[PostgresQueue] = None
        self.teamwork_handler: Optional[TeamworkEventHandler] = None
        self.missive_handler: Optional[MissiveEventHandler] = None
        self.craft_handler: Optional[CraftEventHandler] = None
        self.running = True
        self._db_available = False
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Initial database connection (will retry if unavailable)
        self._ensure_database()
    
    def _create_database(self) -> Optional[PostgresDatabase]:
        """Create database instance."""
        try:
            logger.info("Connecting to PostgreSQL database")
            return PostgresDatabase()
        except Exception as e:
            logger.warning(f"Failed to initialize database: {e}")
            return None
    
    def _ensure_database(self) -> bool:
        """
        Ensure database connection is available. Attempt to reconnect if not.
        
        Returns:
            True if database is available, False otherwise
        """
        # If we have a DB connection, verify it's still valid
        if self.db is not None:
            try:
                if hasattr(self.db, 'is_connected') and self.db.is_connected():
                    self._db_available = True
                    return True
            except Exception:
                pass
            
            # Connection is invalid, clean up
            logger.warning("Database connection lost, attempting to reconnect...")
            try:
                self.db.close()
            except Exception:
                pass
            self.db = None
            self.queue = None
            self.teamwork_handler = None
            self.missive_handler = None
            self.craft_handler = None
            self._db_available = False
        
        # Try to create a new database connection
        self.db = self._create_database()
        
        if self.db is not None:
            # Initialize queue and handlers
            self.queue = PostgresQueue(self.db)
            self.teamwork_handler = TeamworkEventHandler(self.db)
            self.missive_handler = MissiveEventHandler(self.db)
            self.craft_handler = CraftEventHandler(self.db)
            self._db_available = True
            logger.info("Database connection established successfully")
            return True
        
        self._db_available = False
        return False
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}. Shutting down gracefully...")
        self.running = False
    
    def run(self):
        """Main worker loop with database resilience."""
        logger.info("Worker dispatcher started")
        
        consecutive_db_failures = 0
        db_retry_delay = settings.DB_RECONNECT_DELAY
        
        while self.running:
            try:
                # Ensure database connection is available
                if not self._ensure_database():
                    consecutive_db_failures += 1
                    logger.warning(
                        f"Database unavailable (attempt {consecutive_db_failures}). "
                        f"Waiting {db_retry_delay}s before retry..."
                    )
                    time.sleep(db_retry_delay)
                    # Exponential backoff with cap
                    db_retry_delay = min(db_retry_delay * 1.5, settings.DB_MAX_RECONNECT_DELAY)
                    continue
                
                # Reset retry delay on successful connection
                consecutive_db_failures = 0
                db_retry_delay = settings.DB_RECONNECT_DELAY
                
                # Get items from queue
                items = self.queue.dequeue_batch(max_items=10)
                
                if not items:
                    # Queue is empty, sleep briefly and check again
                    time.sleep(0.5)
                    continue
                
                # Process the batch
                try:
                    self._process_batch(items)
                    logger.info(f"Successfully processed batch of {len(items)} events")
                    
                except Exception as e:
                    error_msg = f"Error processing batch: {e}"
                    logger.error(error_msg, exc_info=True)
                    
                    # Check if this is a database error
                    if self._is_database_error(e):
                        # Mark connection as invalid for next iteration
                        self._db_available = False
                        logger.warning("Database error detected during processing, will reconnect")
                    else:
                        # Non-database error, mark items as failed
                        try:
                            self.queue.mark_batch_failed(items, error_msg)
                        except Exception as mark_err:
                            logger.error(f"Failed to mark items as failed: {mark_err}")
            
            except Exception as e:
                logger.error(f"Unexpected error in worker loop: {e}", exc_info=True)
                
                # Check if database-related
                if self._is_database_error(e):
                    self._db_available = False
                    consecutive_db_failures += 1
                    time.sleep(db_retry_delay)
                    db_retry_delay = min(db_retry_delay * 1.5, settings.DB_MAX_RECONNECT_DELAY)
                else:
                    time.sleep(5)  # Back off on unexpected non-db errors
        
        # Cleanup
        self._cleanup()
    
    def _is_database_error(self, exc: Exception) -> bool:
        """Check if an exception is database-related."""
        from psycopg2 import OperationalError, InterfaceError
        
        if isinstance(exc, (OperationalError, InterfaceError)):
            return True
        
        error_msg = str(exc).lower()
        db_indicators = [
            'connection', 'server closed', 'network', 'timeout',
            'could not connect', 'terminating connection', 'connection refused',
            'no route to host', 'connection reset', 'broken pipe', 'database',
        ]
        return any(indicator in error_msg for indicator in db_indicators)
    
    def _cleanup(self):
        """Clean up resources."""
        logger.info("Worker dispatcher shutting down")
        if self.db is not None:
            try:
                self.db.close()
            except Exception as e:
                logger.warning(f"Error closing database: {e}")
    
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
        craft_items = [item for item in items if item.source == "craft"]
        
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
        
        # Process Craft items
        # Craft documents are processed individually (handler does DB upsert directly)
        if craft_items:
            for item in craft_items:
                try:
                    payload = dict(item.payload or {})
                    payload.setdefault("id", item.external_id)
                    payload.setdefault("document_id", item.external_id)
                    
                    # Process document - handler does upsert directly
                    result = self.craft_handler.process_event(item.event_type, payload)
                    
                    # Mark as completed (result is None for deleted docs, dict for success)
                    self.queue.mark_item_completed(item)
                    
                except Exception as e:
                    logger.error(f"Error processing craft item {item.external_id}: {e}", exc_info=True)
                    self.queue.mark_item_failed(item, str(e), retry=True)
    
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
        elif item.source == "craft":
            payload.setdefault("id", item.external_id)
            payload.setdefault("document_id", item.external_id)
            self.craft_handler.handle_event(item.event_type, payload)
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
