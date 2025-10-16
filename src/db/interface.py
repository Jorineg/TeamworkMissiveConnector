"""Abstract database interface."""
from abc import ABC, abstractmethod
from typing import Optional, List

from src.db.models import Email, Task, Checkpoint


class DatabaseInterface(ABC):
    """Abstract interface for database operations."""
    
    @abstractmethod
    def upsert_email(self, email: Email) -> None:
        """Insert or update an email record."""
        pass
    
    @abstractmethod
    def upsert_task(self, task: Task) -> None:
        """Insert or update a task record."""
        pass
    
    @abstractmethod
    def upsert_emails_batch(self, emails: List[Email]) -> None:
        """Insert or update multiple email records in a batch.
        
        Args:
            emails: List of Email objects to upsert (up to 10 recommended)
        """
        pass
    
    @abstractmethod
    def upsert_tasks_batch(self, tasks: List[Task]) -> None:
        """Insert or update multiple task records in a batch.
        
        Args:
            tasks: List of Task objects to upsert (up to 10 recommended)
        """
        pass
    
    @abstractmethod
    def mark_email_deleted(self, email_id: str) -> None:
        """Mark an email as deleted."""
        pass
    
    @abstractmethod
    def mark_task_deleted(self, task_id: str) -> None:
        """Mark a task as deleted."""
        pass
    
    @abstractmethod
    def get_checkpoint(self, source: str) -> Optional[Checkpoint]:
        """Get the last sync checkpoint for a source."""
        pass
    
    @abstractmethod
    def set_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Save a sync checkpoint for a source."""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close database connections."""
        pass

