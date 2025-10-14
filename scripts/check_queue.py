#!/usr/bin/env python3
"""Script to check queue status."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.queue.file_queue import FileQueue
from src import settings


def main():
    queue = FileQueue()
    
    print("Queue Status")
    print("=" * 50)
    print(f"Inbox file: {settings.QUEUE_INBOX_FILE}")
    print(f"Offset file: {settings.QUEUE_OFFSET_FILE}")
    print(f"DLQ file: {settings.QUEUE_DLQ_FILE}")
    print()
    
    # Queue size
    size = queue.size()
    print(f"Items in queue: {size}")
    
    # File sizes
    if settings.QUEUE_INBOX_FILE.exists():
        inbox_size = settings.QUEUE_INBOX_FILE.stat().st_size
        print(f"Inbox file size: {inbox_size:,} bytes")
    
    if settings.QUEUE_DLQ_FILE.exists():
        dlq_lines = sum(1 for line in open(settings.QUEUE_DLQ_FILE) if line.strip())
        print(f"Dead letter queue items: {dlq_lines}")
    
    # Current offset
    offset = queue._load_offset()
    print(f"Current offset: {offset:,} bytes")
    print()
    
    # Peek at next item
    if size > 0:
        print("Next item to process:")
        print("-" * 50)
        item = queue.dequeue()
        if item:
            print(f"Source: {item.source}")
            print(f"Event type: {item.event_type}")
            print(f"External ID: {item.external_id}")
            print(f"Attempts: {item.attempts}")
            print(f"Enqueued at: {item.enqueued_at}")


if __name__ == "__main__":
    main()

