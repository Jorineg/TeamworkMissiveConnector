"""Worker dispatcher that processes the queue."""
import time
import signal
import sys
from typing import Optional

from src import settings
from src.logging_conf import logger
from src.queue.spool_queue import SpoolQueue
from src.queue.models import QueueItem
from src.db.interface import DatabaseInterface
from src.db.airtable_impl import AirtableDatabase
from src.db.postgres_impl import PostgresDatabase
from src.workers.handlers.teamwork_events import TeamworkEventHandler
from src.workers.handlers.missive_events import MissiveEventHandler


class WorkerDispatcher:
    """Dispatcher that processes queued events."""
    
    def __init__(self):
        self.queue = SpoolQueue()
        self.db = self._create_database()
        self.teamwork_handler = TeamworkEventHandler(self.db)
        self.missive_handler = MissiveEventHandler(self.db)
        self.running = True
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _create_database(self) -> DatabaseInterface:
        """Create database instance based on configuration."""
        if settings.DB_BACKEND == "airtable":
            logger.info("Using Airtable database")
            return AirtableDatabase()
        elif settings.DB_BACKEND == "postgres":
            logger.info("Using PostgreSQL database")
            return PostgresDatabase()
        else:
            raise ValueError(f"Invalid DB_BACKEND: {settings.DB_BACKEND}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}. Shutting down gracefully...")
        self.running = False
    
    def run(self):
        """Main worker loop."""
        logger.info("Worker dispatcher started")
        
        while self.running:
            try:
                # Get next item from queue
                item = self.queue.dequeue()
                
                if item is None:
                    # Queue is empty, sleep and check again
                    time.sleep(1)
                    continue
                
                # Process the item
                try:
                    self._process_item(item)
                    self.queue.mark_processed()
                    logger.info(
                        f"Successfully processed {item.source} event: {item.event_type}",
                        extra={"source": item.source, "event_id": item.external_id}
                    )
                
                except Exception as e:
                    error_msg = f"Error processing item: {e}"
                    logger.error(error_msg, exc_info=True)
                    self.queue.mark_failed(item, error_msg)
            
            except Exception as e:
                logger.error(f"Unexpected error in worker loop: {e}", exc_info=True)
                time.sleep(5)  # Back off on unexpected errors
        
        # Cleanup
        logger.info("Worker dispatcher shutting down")
        self.db.close()
    
    def _process_item(self, item: QueueItem) -> None:
        """
        Process a single queue item.
        
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

