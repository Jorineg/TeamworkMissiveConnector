"""Queue item models."""
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any, Optional
import json


@dataclass
class QueueItem:
    """Represents an item in the processing queue."""
    source: str  # "teamwork" or "missive"
    event_type: str  # e.g., "task.created", "email.received"
    external_id: str  # The ID from the external system
    payload: Dict[str, Any]  # The raw event payload
    enqueued_at: str  # ISO 8601 timestamp
    attempts: int = 0
    last_error: Optional[str] = None
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))
    
    @classmethod
    def from_json(cls, json_str: str) -> "QueueItem":
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls(**data)
    
    @classmethod
    def create(cls, source: str, event_type: str, external_id: str, payload: Dict[str, Any]) -> "QueueItem":
        """Create a new queue item with current timestamp."""
        return cls(
            source=source,
            event_type=event_type,
            external_id=external_id,
            payload=payload,
            enqueued_at=datetime.utcnow().isoformat() + "Z",
            attempts=0
        )

