"""PostgreSQL-backed queue implementation with connection resilience."""
import uuid
import time
from typing import List, Optional

from psycopg2.extras import Json
from psycopg2 import OperationalError, InterfaceError

from src import settings
from src.queue.models import QueueItem
from src.logging_conf import logger


def is_connection_error(exc: Exception) -> bool:
    """Check if an exception indicates a connection problem."""
    if isinstance(exc, (OperationalError, InterfaceError)):
        return True
    error_msg = str(exc).lower()
    connection_indicators = [
        'connection', 'server closed', 'network', 'timeout',
        'could not connect', 'terminating connection', 'connection refused',
        'no route to host', 'connection reset', 'broken pipe',
    ]
    return any(indicator in error_msg for indicator in connection_indicators)


class PostgresQueue:
    """PostgreSQL-backed event queue with ACID compliance, retry logic, and connection resilience."""
    
    def __init__(self, db):
        """
        Initialize PostgreSQL queue.
        
        Args:
            db: PostgresDatabase instance (with resilient connection)
        """
        self._db = db
        self.worker_id = str(uuid.uuid4())[:8]
        logger.info(f"PostgreSQL queue initialized with worker_id: {self.worker_id}")
    
    @property
    def conn(self):
        """Get connection from the database instance (ensures valid connection)."""
        return self._db.conn
    
    def _execute_with_retry(self, operation_name: str, operation, fallback_result=None):
        """
        Execute a database operation with retry logic.
        
        Args:
            operation_name: Name for logging
            operation: Callable that performs the operation (receives cursor)
            fallback_result: Value to return if all retries fail
            
        Returns:
            Result of operation or fallback_result on failure
        """
        last_exception = None
        delay = settings.DB_RECONNECT_DELAY
        
        for attempt in range(settings.DB_OPERATION_RETRIES + 1):
            try:
                with self.conn.cursor() as cur:
                    result = operation(cur)
                    self.conn.commit()
                    return result
                    
            except Exception as e:
                last_exception = e
                
                # Rollback any failed transaction
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                
                if is_connection_error(e):
                    if attempt < settings.DB_OPERATION_RETRIES:
                        logger.warning(
                            f"Queue {operation_name} failed (attempt {attempt + 1}): {e}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                        # Force reconnection by accessing conn property (db handles reconnect)
                        self._db._mark_connection_invalid()
                        delay = min(delay * 2, settings.DB_MAX_RECONNECT_DELAY)
                    else:
                        logger.error(f"Queue {operation_name} failed after {settings.DB_OPERATION_RETRIES + 1} attempts: {e}")
                        if fallback_result is not None:
                            return fallback_result
                        raise
                else:
                    # Non-connection error, log and potentially use fallback
                    logger.error(f"Queue {operation_name} failed: {e}", exc_info=True)
                    if fallback_result is not None:
                        return fallback_result
                    raise
        
        if fallback_result is not None:
            return fallback_result
        raise last_exception
    
    def enqueue(self, item: QueueItem) -> bool:
        """
        Enqueue a single item.
        
        Args:
            item: Queue item to enqueue
            
        Returns:
            True if enqueued successfully, False otherwise
        """
        def do_enqueue(cur):
            cur.execute("""
                INSERT INTO teamworkmissiveconnector.queue_items (
                    source, event_type, external_id, payload, status, created_at
                ) VALUES (%s, %s, %s, %s, %s, NOW())
            """, (
                item.source,
                item.event_type,
                item.external_id,
                Json(item.payload),
                'pending'
            ))
            logger.debug(f"Enqueued {item.source}/{item.event_type}/{item.external_id}")
            return True
        
        try:
            return self._execute_with_retry("enqueue", do_enqueue, fallback_result=False)
        except Exception as e:
            logger.error(f"Failed to enqueue item: {e}", exc_info=True)
            return False
    
    def enqueue_batch(self, items: List[QueueItem]) -> bool:
        """
        Enqueue multiple items in a batch.
        
        Args:
            items: List of queue items to enqueue
            
        Returns:
            True if all items enqueued successfully, False otherwise
        """
        if not items:
            return True
        
        def do_enqueue_batch(cur):
            for item in items:
                cur.execute("""
                    INSERT INTO teamworkmissiveconnector.queue_items (
                        source, event_type, external_id, payload, status, created_at
                    ) VALUES (%s, %s, %s, %s, %s, NOW())
                """, (
                    item.source,
                    item.event_type,
                    item.external_id,
                    Json(item.payload),
                    'pending'
                ))
            logger.info(f"Enqueued batch of {len(items)} items")
            return True
        
        try:
            return self._execute_with_retry("enqueue_batch", do_enqueue_batch, fallback_result=False)
        except Exception as e:
            logger.error(f"Failed to enqueue batch: {e}", exc_info=True)
            return False
    
    def dequeue_batch(self, max_items: int = 10, source: Optional[str] = None) -> List[QueueItem]:
        """
        Dequeue items for processing using database function.
        
        Args:
            max_items: Maximum number of items to dequeue
            source: Optional source filter ('teamwork' or 'missive')
        
        Returns:
            List of queue items ready for processing (empty list on failure)
        """
        def do_dequeue(cur):
            cur.execute("""
                SELECT id, source, event_type, external_id, payload, retry_count
                FROM teamworkmissiveconnector.dequeue_items(%s, %s, %s)
            """, (self.worker_id, max_items, source))
            
            rows = cur.fetchall()
            
            items = []
            for row in rows:
                item = QueueItem.create(
                    source=row[1],
                    event_type=row[2],
                    external_id=row[3],
                    payload=row[4] or {}
                )
                item._db_id = row[0]
                item._retry_count = row[5]
                items.append(item)
            
            if items:
                logger.debug(f"Dequeued {len(items)} items")
            
            return items
        
        try:
            return self._execute_with_retry("dequeue_batch", do_dequeue, fallback_result=[])
        except Exception as e:
            logger.error(f"Failed to dequeue items: {e}", exc_info=True)
            return []
    
    def mark_batch_processed(self, items: Optional[List[QueueItem]] = None) -> None:
        """
        Mark items as successfully processed.
        
        Note: If items is None, assumes last dequeued batch.
        In the new implementation, we mark items individually.
        """
        pass
    
    def mark_item_completed(self, item: QueueItem, processing_time_ms: Optional[int] = None) -> bool:
        """
        Mark a single item as completed.
        
        Args:
            item: Queue item that was processed successfully
            processing_time_ms: Optional processing time in milliseconds
            
        Returns:
            True if marked successfully, False otherwise
        """
        if not hasattr(item, '_db_id'):
            logger.warning("Item has no _db_id, cannot mark as completed")
            return False
        
        def do_mark_completed(cur):
            cur.execute("""
                SELECT teamworkmissiveconnector.mark_completed(%s, %s)
            """, (item._db_id, processing_time_ms))
            logger.debug(f"Marked item {item._db_id} as completed")
            return True
        
        try:
            return self._execute_with_retry("mark_completed", do_mark_completed, fallback_result=False)
        except Exception as e:
            logger.error(f"Failed to mark item as completed: {e}", exc_info=True)
            return False
    
    def mark_batch_failed(self, items: List[QueueItem], error_msg: str) -> None:
        """
        Mark items as failed with retry logic.
        
        Args:
            items: List of queue items that failed
            error_msg: Error message describing the failure
        """
        for item in items:
            self.mark_item_failed(item, error_msg, retry=True)
    
    def mark_item_failed(self, item: QueueItem, error_msg: str, retry: bool = True) -> bool:
        """
        Mark a single item as failed.
        
        Args:
            item: Queue item that failed
            error_msg: Error message
            retry: Whether to retry (with exponential backoff)
            
        Returns:
            True if marked successfully, False otherwise
        """
        if not hasattr(item, '_db_id'):
            logger.warning(f"Item has no _db_id, cannot mark as failed: {error_msg}")
            return False
        
        def do_mark_failed(cur):
            cur.execute("""
                SELECT teamworkmissiveconnector.mark_failed(%s, %s, %s)
            """, (item._db_id, error_msg, retry))
            logger.debug(f"Marked item {item._db_id} as failed (retry={retry})")
            return True
        
        try:
            return self._execute_with_retry("mark_failed", do_mark_failed, fallback_result=False)
        except Exception as e:
            logger.error(f"Failed to mark item as failed: {e}", exc_info=True)
            return False
    
    def get_queue_health(self) -> dict:
        """
        Get queue health metrics.
        
        Returns:
            Dictionary with queue health statistics by source (empty dict on failure)
        """
        def do_get_health(cur):
            cur.execute("""
                SELECT 
                    source,
                    pending_count,
                    processing_count,
                    failed_count,
                    dead_letter_count,
                    avg_processing_time_ms,
                    stuck_items
                FROM teamworkmissiveconnector.queue_health
            """)
            
            rows = cur.fetchall()
            health = {}
            
            for row in rows:
                health[row[0]] = {
                    'pending': row[1] or 0,
                    'processing': row[2] or 0,
                    'failed': row[3] or 0,
                    'dead_letter': row[4] or 0,
                    'avg_processing_time_ms': float(row[5]) if row[5] else 0.0,
                    'stuck_items': row[6] or 0
                }
            
            return health
        
        try:
            return self._execute_with_retry("get_queue_health", do_get_health, fallback_result={})
        except Exception as e:
            logger.error(f"Failed to get queue health: {e}", exc_info=True)
            return {}
    
    def cleanup_old_items(self, retention_days: int = 7) -> int:
        """
        Clean up old completed items.
        
        Args:
            retention_days: Number of days to retain completed items
        
        Returns:
            Number of items deleted (0 on failure)
        """
        def do_cleanup(cur):
            cur.execute("""
                SELECT teamworkmissiveconnector.cleanup_old_items(%s)
            """, (retention_days,))
            
            deleted_count = cur.fetchone()[0]
            logger.info(f"Cleaned up {deleted_count} old queue items")
            return deleted_count
        
        try:
            return self._execute_with_retry("cleanup_old_items", do_cleanup, fallback_result=0)
        except Exception as e:
            logger.error(f"Failed to cleanup old items: {e}", exc_info=True)
            return 0
    
    def reset_stuck_items(self, stuck_threshold_minutes: int = 30) -> int:
        """
        Reset items stuck in processing state.
        
        Args:
            stuck_threshold_minutes: Minutes after which an item is considered stuck
        
        Returns:
            Number of items reset (0 on failure)
        """
        def do_reset(cur):
            cur.execute("""
                SELECT teamworkmissiveconnector.reset_stuck_items(%s)
            """, (stuck_threshold_minutes,))
            
            reset_count = cur.fetchone()[0]
            if reset_count > 0:
                logger.warning(f"Reset {reset_count} stuck queue items")
            return reset_count
        
        try:
            return self._execute_with_retry("reset_stuck_items", do_reset, fallback_result=0)
        except Exception as e:
            logger.error(f"Failed to reset stuck items: {e}", exc_info=True)
            return 0
