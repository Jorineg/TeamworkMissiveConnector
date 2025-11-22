"""PostgreSQL-backed queue implementation."""
import uuid
from typing import List, Optional
from datetime import datetime

from src.queue.models import QueueItem
from src.logging_conf import logger


class PostgresQueue:
    """PostgreSQL-backed event queue with ACID compliance and retry logic."""
    
    def __init__(self, conn):
        """
        Initialize PostgreSQL queue.
        
        Args:
            conn: psycopg2 connection object
        """
        self.conn = conn
        self.worker_id = str(uuid.uuid4())[:8]  # Short worker ID for this instance
        logger.info(f"PostgreSQL queue initialized with worker_id: {self.worker_id}")
    
    def enqueue(self, item: QueueItem) -> None:
        """
        Enqueue a single item.
        
        Args:
            item: Queue item to enqueue
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO teamworkmissiveconnector.queue_items (
                        source, event_type, external_id, payload, status, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    item.source,
                    item.event_type,
                    item.external_id,
                    item.payload,  # Will be converted to JSONB
                    'pending',
                    item.created_at or datetime.utcnow()
                ))
                self.conn.commit()
                logger.debug(f"Enqueued {item.source}/{item.event_type}/{item.external_id}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to enqueue item: {e}", exc_info=True)
            raise
    
    def enqueue_batch(self, items: List[QueueItem]) -> None:
        """
        Enqueue multiple items in a batch.
        
        Args:
            items: List of queue items to enqueue
        """
        if not items:
            return
        
        try:
            with self.conn.cursor() as cur:
                for item in items:
                    cur.execute("""
                        INSERT INTO teamworkmissiveconnector.queue_items (
                            source, event_type, external_id, payload, status, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        item.source,
                        item.event_type,
                        item.external_id,
                        item.payload,
                        'pending',
                        item.created_at or datetime.utcnow()
                    ))
                self.conn.commit()
                logger.info(f"Enqueued batch of {len(items)} items")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to enqueue batch: {e}", exc_info=True)
            raise
    
    def dequeue_batch(self, max_items: int = 10, source: Optional[str] = None) -> List[QueueItem]:
        """
        Dequeue items for processing using database function.
        
        Args:
            max_items: Maximum number of items to dequeue
            source: Optional source filter ('teamwork' or 'missive')
        
        Returns:
            List of queue items ready for processing
        """
        try:
            with self.conn.cursor() as cur:
                # Use the dequeue function from the database
                cur.execute("""
                    SELECT id, source, event_type, external_id, payload, retry_count
                    FROM teamworkmissiveconnector.dequeue_items(%s, %s, %s)
                """, (self.worker_id, max_items, source))
                
                rows = cur.fetchall()
                self.conn.commit()
                
                items = []
                for row in rows:
                    item = QueueItem(
                        source=row[1],
                        event_type=row[2],
                        external_id=row[3],
                        payload=row[4] or {},
                        created_at=datetime.utcnow()
                    )
                    # Store database ID for later use
                    item._db_id = row[0]
                    item._retry_count = row[5]
                    items.append(item)
                
                if items:
                    logger.debug(f"Dequeued {len(items)} items")
                
                return items
        
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to dequeue items: {e}", exc_info=True)
            return []
    
    def mark_batch_processed(self, items: Optional[List[QueueItem]] = None) -> None:
        """
        Mark items as successfully processed.
        
        Note: If items is None, assumes last dequeued batch.
        In the new implementation, we mark items individually.
        """
        # This method exists for backward compatibility but does nothing
        # Items are marked individually in the new implementation
        pass
    
    def mark_item_completed(self, item: QueueItem, processing_time_ms: Optional[int] = None) -> None:
        """
        Mark a single item as completed.
        
        Args:
            item: Queue item that was processed successfully
            processing_time_ms: Optional processing time in milliseconds
        """
        if not hasattr(item, '_db_id'):
            logger.warning("Item has no _db_id, cannot mark as completed")
            return
        
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT teamworkmissiveconnector.mark_completed(%s, %s)
                """, (item._db_id, processing_time_ms))
                self.conn.commit()
                logger.debug(f"Marked item {item._db_id} as completed")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to mark item as completed: {e}", exc_info=True)
    
    def mark_batch_failed(self, items: List[QueueItem], error_msg: str) -> None:
        """
        Mark items as failed with retry logic.
        
        Args:
            items: List of queue items that failed
            error_msg: Error message describing the failure
        """
        for item in items:
            self.mark_item_failed(item, error_msg, retry=True)
    
    def mark_item_failed(self, item: QueueItem, error_msg: str, retry: bool = True) -> None:
        """
        Mark a single item as failed.
        
        Args:
            item: Queue item that failed
            error_msg: Error message
            retry: Whether to retry (with exponential backoff)
        """
        if not hasattr(item, '_db_id'):
            logger.warning(f"Item has no _db_id, cannot mark as failed: {error_msg}")
            return
        
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT teamworkmissiveconnector.mark_failed(%s, %s, %s)
                """, (item._db_id, error_msg, retry))
                self.conn.commit()
                logger.debug(f"Marked item {item._db_id} as failed (retry={retry})")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to mark item as failed: {e}", exc_info=True)
    
    def get_queue_health(self) -> dict:
        """
        Get queue health metrics.
        
        Returns:
            Dictionary with queue health statistics by source
        """
        try:
            with self.conn.cursor() as cur:
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
        except Exception as e:
            logger.error(f"Failed to get queue health: {e}", exc_info=True)
            return {}
    
    def cleanup_old_items(self, retention_days: int = 7) -> int:
        """
        Clean up old completed items.
        
        Args:
            retention_days: Number of days to retain completed items
        
        Returns:
            Number of items deleted
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT teamworkmissiveconnector.cleanup_old_items(%s)
                """, (retention_days,))
                
                deleted_count = cur.fetchone()[0]
                self.conn.commit()
                
                logger.info(f"Cleaned up {deleted_count} old queue items")
                return deleted_count
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to cleanup old items: {e}", exc_info=True)
            return 0
    
    def reset_stuck_items(self, stuck_threshold_minutes: int = 30) -> int:
        """
        Reset items stuck in processing state.
        
        Args:
            stuck_threshold_minutes: Minutes after which an item is considered stuck
        
        Returns:
            Number of items reset
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT teamworkmissiveconnector.reset_stuck_items(%s)
                """, (stuck_threshold_minutes,))
                
                reset_count = cur.fetchone()[0]
                self.conn.commit()
                
                if reset_count > 0:
                    logger.warning(f"Reset {reset_count} stuck queue items")
                return reset_count
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to reset stuck items: {e}", exc_info=True)
            return 0

