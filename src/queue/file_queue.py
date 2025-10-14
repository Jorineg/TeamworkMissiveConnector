"""File-based queue implementation using JSONL."""
import json
import os
from pathlib import Path
from typing import Optional
import portalocker

from src import settings
from src.queue.models import QueueItem
from src.logging_conf import logger


class FileQueue:
    """A simple, persistent queue using JSONL files with file locking."""
    
    def __init__(
        self,
        inbox_file: Path = settings.QUEUE_INBOX_FILE,
        offset_file: Path = settings.QUEUE_OFFSET_FILE,
        dlq_file: Path = settings.QUEUE_DLQ_FILE
    ):
        self.inbox_file = inbox_file
        self.offset_file = offset_file
        self.dlq_file = dlq_file
        
        # Ensure files exist
        self.inbox_file.touch(exist_ok=True)
        self.dlq_file.touch(exist_ok=True)
        
        if not self.offset_file.exists():
            self._save_offset(0)
    
    def enqueue(self, item: QueueItem) -> None:
        """Add an item to the queue."""
        try:
            with portalocker.Lock(self.inbox_file, "a", timeout=5) as f:
                f.write(item.to_json() + "\n")
                f.flush()
                os.fsync(f.fileno())
            
            logger.info(
                f"Enqueued {item.source} event: {item.event_type}",
                extra={"source": item.source, "event_id": item.external_id}
            )
        except Exception as e:
            logger.error(f"Failed to enqueue item: {e}", exc_info=True)
            raise
    
    def dequeue(self) -> Optional[QueueItem]:
        """
        Get the next item from the queue.
        Returns None if queue is empty.
        Does not remove the item - call mark_processed() after successful processing.
        """
        try:
            offset = self._load_offset()
            
            with portalocker.Lock(self.inbox_file, "r", timeout=5) as f:
                f.seek(offset)
                line = f.readline()
                
                if not line:
                    return None
                
                item = QueueItem.from_json(line.strip())
                return item
        except json.JSONDecodeError as e:
            logger.error(f"Corrupt queue item at offset {offset}: {e}")
            # Skip this line
            self._advance_offset()
            return self.dequeue()
        except Exception as e:
            logger.error(f"Failed to dequeue item: {e}", exc_info=True)
            return None
    
    def mark_processed(self) -> None:
        """Mark the current item as processed by advancing the offset."""
        self._advance_offset()
    
    def mark_failed(self, item: QueueItem, error: str) -> None:
        """
        Mark an item as failed.
        If max attempts reached, move to DLQ.
        Otherwise, increment attempts and keep in queue.
        """
        item.attempts += 1
        item.last_error = error
        
        if item.attempts >= settings.MAX_QUEUE_ATTEMPTS:
            # Move to DLQ
            try:
                with portalocker.Lock(self.dlq_file, "a", timeout=5) as f:
                    f.write(item.to_json() + "\n")
                    f.flush()
                    os.fsync(f.fileno())
                
                logger.warning(
                    f"Item moved to DLQ after {item.attempts} attempts: {item.external_id}",
                    extra={"source": item.source, "event_id": item.external_id}
                )
                
                # Remove from main queue
                self._advance_offset()
            except Exception as e:
                logger.error(f"Failed to move item to DLQ: {e}", exc_info=True)
        else:
            # Re-enqueue with updated attempts
            logger.info(
                f"Re-enqueueing item (attempt {item.attempts}/{settings.MAX_QUEUE_ATTEMPTS}): {item.external_id}",
                extra={"source": item.source, "event_id": item.external_id}
            )
            # Advance offset to skip current position, then re-enqueue
            self._advance_offset()
            self.enqueue(item)
    
    def _load_offset(self) -> int:
        """Load the current read offset."""
        try:
            with open(self.offset_file, "r") as f:
                data = json.load(f)
                return data.get("offset", 0)
        except (json.JSONDecodeError, FileNotFoundError):
            return 0
    
    def _save_offset(self, offset: int) -> None:
        """Save the current read offset."""
        with portalocker.Lock(self.offset_file, "w", timeout=5) as f:
            json.dump({"offset": offset}, f)
            f.flush()
            os.fsync(f.fileno())
    
    def _advance_offset(self) -> None:
        """Move the offset to the next line."""
        try:
            offset = self._load_offset()
            
            with open(self.inbox_file, "r") as f:
                f.seek(offset)
                line = f.readline()
                new_offset = offset + len(line)
            
            self._save_offset(new_offset)
            
            # Compact if we've processed most of the file
            self._maybe_compact()
        except Exception as e:
            logger.error(f"Failed to advance offset: {e}", exc_info=True)
    
    def _maybe_compact(self) -> None:
        """
        Compact the inbox file if we've processed most of it.
        This prevents unbounded growth.
        """
        try:
            offset = self._load_offset()
            file_size = self.inbox_file.stat().st_size
            
            # Compact if we've processed 80% of the file and it's > 1MB
            if file_size > 1024 * 1024 and offset > file_size * 0.8:
                logger.info("Compacting queue file...")
                
                # Read remaining items
                remaining_items = []
                with open(self.inbox_file, "r") as f:
                    f.seek(offset)
                    for line in f:
                        if line.strip():
                            remaining_items.append(line)
                
                # Write to new file
                temp_file = self.inbox_file.with_suffix(".tmp")
                with portalocker.Lock(temp_file, "w", timeout=10) as f:
                    for line in remaining_items:
                        f.write(line)
                    f.flush()
                    os.fsync(f.fileno())
                
                # Atomic rename
                temp_file.replace(self.inbox_file)
                
                # Reset offset
                self._save_offset(0)
                
                logger.info(f"Queue compacted. Kept {len(remaining_items)} items.")
        except Exception as e:
            logger.error(f"Failed to compact queue: {e}", exc_info=True)
    
    def size(self) -> int:
        """Get approximate number of items in queue (not exact due to compaction)."""
        try:
            offset = self._load_offset()
            with open(self.inbox_file, "r") as f:
                f.seek(offset)
                count = sum(1 for line in f if line.strip())
            return count
        except Exception:
            return 0

