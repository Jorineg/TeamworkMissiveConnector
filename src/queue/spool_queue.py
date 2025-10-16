"""Spool-directory based queue.

Creates one file per event ID under per-source directories. Processing deletes
the file on success. Failures rename to `.retry` and are retried only when the
file's mtime is at least `SPOOL_RETRY_SECONDS` old. Very simple, restart-safe.
"""
import os
import re
import time
from pathlib import Path
from typing import Optional, List

from src import settings
from src.logging_conf import logger
from src.queue.models import QueueItem


class SpoolQueue:
    """A minimal spool-based queue implementation."""

    def __init__(self):
        self.base_dir: Path = settings.SPOOL_BASE_DIR
        self.teamwork_dir: Path = settings.SPOOL_TEAMWORK_DIR
        self.missive_dir: Path = settings.SPOOL_MISSIVE_DIR
        self.retry_seconds: int = settings.SPOOL_RETRY_SECONDS

        # Ensure directories exist
        self.teamwork_dir.mkdir(parents=True, exist_ok=True)
        self.missive_dir.mkdir(parents=True, exist_ok=True)

        # Track the currently dequeued file for ack/fail operations
        self._current_file: Optional[Path] = None
        self._current_item: Optional[QueueItem] = None
        
        # Track batch operations
        self._current_batch_files: List[Path] = []
        self._current_batch_items: List[QueueItem] = []

    def enqueue(self, item: QueueItem) -> None:
        """Enqueue an item by creating a file named with its external ID."""
        try:
            dir_path = self._dir_for_source(item.source)
            if dir_path is None:
                logger.warning(f"Unknown source for spool enqueue: {item.source}")
                return

            filename = f"{self._safe_id(item.external_id)}.evt"
            path = dir_path / filename

            # Exclusive create to naturally deduplicate
            try:
                with open(path, "x") as f:
                    # We intentionally store no content; ID is in the filename
                    f.write("")
                logger.info(
                    f"Spool enqueued {item.source}:{item.external_id}",
                    extra={"source": item.source, "event_id": item.external_id}
                )
            except FileExistsError:
                # Already queued; skip silently
                logger.debug(
                    f"Spool item already present {item.source}:{item.external_id}",
                    extra={"source": item.source, "event_id": item.external_id}
                )
        except Exception as e:
            logger.error(f"Failed to spool enqueue: {e}", exc_info=True)
            raise

    def dequeue(self) -> Optional[QueueItem]:
        """Return the next item by scanning for `.evt` or eligible `.retry` files."""
        batch = self.dequeue_batch(max_items=1)
        return batch[0] if batch else None

    def dequeue_batch(self, max_items: int = 10) -> List[QueueItem]:
        """Return up to max_items from the queue.
        
        Args:
            max_items: Maximum number of items to dequeue (default 10)
            
        Returns:
            List of QueueItems (may be empty if queue is empty)
        """
        try:
            items = []
            claimed_files = []
            
            # Process ready `.evt` first, then eligible `.retry`
            for source in ("teamwork", "missive"):
                if len(items) >= max_items:
                    break
                    
                dir_path = self._dir_for_source(source)
                if dir_path is None:
                    continue

                # Ready files
                evt_files = self._list_files(dir_path, ".evt")
                for file_path in evt_files:
                    if len(items) >= max_items:
                        break
                    item = self._claim_file(source, file_path)
                    items.append(item)
                    claimed_files.append(file_path)

                # Retry files eligible by age
                if len(items) < max_items:
                    retry_files = self._list_files(dir_path, ".retry")
                    eligible = [p for p in retry_files if self._is_retry_eligible(p)]
                    for file_path in eligible:
                        if len(items) >= max_items:
                            break
                        item = self._claim_file(source, file_path)
                        items.append(item)
                        claimed_files.append(file_path)

            # Store claimed files for batch operations
            if items:
                self._current_batch_files = claimed_files
                self._current_batch_items = items
            
            return items
        except Exception as e:
            logger.error(f"Failed to dequeue batch from spool: {e}", exc_info=True)
            return []

    def mark_processed(self) -> None:
        """Acknowledge current item by deleting its file."""
        if not self._current_file:
            return
        try:
            self._current_file.unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"Failed to delete spool file {self._current_file}: {e}")
        finally:
            self._current_file = None
            self._current_item = None

    def mark_batch_processed(self) -> None:
        """Acknowledge all items in current batch by deleting their files."""
        if not self._current_batch_files:
            return
        for file_path in self._current_batch_files:
            try:
                file_path.unlink(missing_ok=True)
            except Exception as e:
                logger.error(f"Failed to delete spool file {file_path}: {e}")
        self._current_batch_files = []
        self._current_batch_items = []

    def mark_failed(self, item: QueueItem, error: str) -> None:
        """Rename current file to `.retry` and update its mtime to now."""
        if not self._current_file:
            return
        try:
            retry_path = self._current_file.with_suffix(".retry")
            # Rename to .retry (idempotent if already .retry)
            if self._current_file.suffix != ".retry":
                try:
                    os.replace(self._current_file, retry_path)
                except FileNotFoundError:
                    # Already processed elsewhere
                    pass
            else:
                retry_path = self._current_file

            # Touch to set mtime to now so it waits retry_seconds
            try:
                now = time.time()
                os.utime(retry_path, (now, now))
            except Exception:
                pass

            logger.info(
                f"Spool mark_failed; will retry in ~{self.retry_seconds}s: {item.external_id}",
                extra={"source": item.source, "event_id": item.external_id}
            )
        except Exception as e:
            logger.error(f"Failed to mark spool item failed: {e}", exc_info=True)
        finally:
            self._current_file = None
            self._current_item = None

    def mark_batch_failed(self, failed_items: List[QueueItem], error: str) -> None:
        """Rename files for failed items to `.retry` and update their mtime to now."""
        if not self._current_batch_files or not failed_items:
            return
        
        failed_ids = {item.external_id for item in failed_items}
        
        for i, file_path in enumerate(self._current_batch_files):
            if i < len(self._current_batch_items):
                item = self._current_batch_items[i]
                if item.external_id in failed_ids:
                    try:
                        retry_path = file_path.with_suffix(".retry")
                        # Rename to .retry (idempotent if already .retry)
                        if file_path.suffix != ".retry":
                            try:
                                os.replace(file_path, retry_path)
                            except FileNotFoundError:
                                # Already processed elsewhere
                                pass
                        else:
                            retry_path = file_path

                        # Touch to set mtime to now so it waits retry_seconds
                        try:
                            now = time.time()
                            os.utime(retry_path, (now, now))
                        except Exception:
                            pass

                        logger.info(
                            f"Spool mark_failed (batch); will retry in ~{self.retry_seconds}s: {item.external_id}",
                            extra={"source": item.source, "event_id": item.external_id}
                        )
                    except Exception as e:
                        logger.error(f"Failed to mark spool item failed: {e}", exc_info=True)
        
        self._current_batch_files = []
        self._current_batch_items = []

    def size(self) -> int:
        """Approximate number of queued files (evt + retry)."""
        try:
            total = 0
            for dir_path in (self.teamwork_dir, self.missive_dir):
                total += len(self._list_files(dir_path, ".evt"))
                total += len(self._list_files(dir_path, ".retry"))
            return total
        except Exception:
            return 0

    # Internal helpers
    def _dir_for_source(self, source: str) -> Optional[Path]:
        if source == "teamwork":
            return self.teamwork_dir
        if source == "missive":
            return self.missive_dir
        return None

    def _safe_id(self, value: str) -> str:
        # Replace unsafe filename characters; keep it simple and Windows-safe
        return re.sub(r"[^A-Za-z0-9._-]", "_", value)[:200]

    def _list_files(self, directory: Path, suffix: str) -> List[Path]:
        try:
            files = [p for p in directory.iterdir() if p.is_file() and p.suffix == suffix]
            # Sort by modification time (oldest first) for fairness
            files.sort(key=lambda p: p.stat().st_mtime)
            return files
        except FileNotFoundError:
            return []

    def _is_retry_eligible(self, path: Path) -> bool:
        try:
            age = time.time() - path.stat().st_mtime
            return age >= self.retry_seconds
        except FileNotFoundError:
            return False

    def _claim_file(self, source: str, file_path: Path) -> QueueItem:
        # Track current file so mark_processed/failed can act on it
        self._current_file = file_path
        # Build a minimal QueueItem; event_type unknown, payload empty
        external_id = file_path.stem
        item = QueueItem.create(
            source=source,
            event_type="unknown",
            external_id=external_id,
            payload={}
        )
        self._current_item = item
        return item


