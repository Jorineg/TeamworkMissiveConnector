"""Abstract database interface."""
from abc import ABC, abstractmethod
from typing import Optional

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

