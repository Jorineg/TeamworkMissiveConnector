"""Domain models for emails and tasks."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class Attachment:
    """Represents an email attachment."""
    filename: str
    content_type: str
    byte_size: int
    source_url: str
    checksum: Optional[str] = None
    db_url: Optional[str] = None  # URL after upload to database
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "filename": self.filename,
            "content_type": self.content_type,
            "byte_size": self.byte_size,
            "source_url": self.source_url,
            "checksum": self.checksum,
            "db_url": self.db_url
        }


@dataclass
class Email:
    """Represents an email message."""
    email_id: str
    thread_id: Optional[str] = None
    subject: Optional[str] = None
    from_address: Optional[str] = None
    from_name: Optional[str] = None
    to_addresses: List[str] = field(default_factory=list)
    to_names: List[str] = field(default_factory=list)
    cc_addresses: List[str] = field(default_factory=list)
    cc_names: List[str] = field(default_factory=list)
    bcc_addresses: List[str] = field(default_factory=list)
    bcc_names: List[str] = field(default_factory=list)
    in_reply_to: List[str] = field(default_factory=list)
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    sent_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    labels: List[str] = field(default_factory=list)
    draft: bool = False
    deleted: bool = False
    deleted_at: Optional[datetime] = None
    source_links: Dict[str, str] = field(default_factory=dict)
    attachments: List[Attachment] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "email_id": self.email_id,
            "thread_id": self.thread_id,
            "subject": self.subject,
            "from_address": self.from_address,
            "from_name": self.from_name,
            "to_addresses": self.to_addresses,
            "to_names": self.to_names,
            "cc_addresses": self.cc_addresses,
            "cc_names": self.cc_names,
            "bcc_addresses": self.bcc_addresses,
            "bcc_names": self.bcc_names,
            "in_reply_to": self.in_reply_to,
            "body_text": self.body_text,
            "body_html": self.body_html,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "labels": self.labels,
            "draft": self.draft,
            "deleted": self.deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "source_links": self.source_links,
            "attachments": [att.to_dict() for att in self.attachments]
        }


@dataclass
class Task:
    """Represents a Teamwork task."""
    task_id: str
    project_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    assignees: List[str] = field(default_factory=list)
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    due_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted: bool = False
    deleted_at: Optional[datetime] = None
    source_links: Dict[str, str] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "project_id": self.project_id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "tags": self.tags,
            "assignees": self.assignees,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "due_at": self.due_at.isoformat() if self.due_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "deleted": self.deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "source_links": self.source_links
        }


@dataclass
class Checkpoint:
    """Represents a sync checkpoint for a data source."""
    source: str
    last_event_time: datetime
    last_cursor: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "last_event_time": self.last_event_time.isoformat(),
            "last_cursor": self.last_cursor
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Checkpoint":
        return cls(
            source=data["source"],
            last_event_time=datetime.fromisoformat(data["last_event_time"].replace("Z", "+00:00")),
            last_cursor=data.get("last_cursor")
        )

