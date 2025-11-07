"""PostgreSQL implementation of the database interface."""
import json
from datetime import datetime
from typing import Optional, List
import psycopg2
from psycopg2.extras import RealDictCursor, Json, execute_batch

from src import settings
from src.db.interface import DatabaseInterface
from src.db.models import Email, Task, Checkpoint
from src.logging_conf import logger


class PostgresDatabase(DatabaseInterface):
    """PostgreSQL implementation of database operations."""
    
    def __init__(self):
        self.conn = psycopg2.connect(settings.PG_DSN)
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create tables if they don't exist."""
        with self.conn.cursor() as cur:
            # Emails table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS emails (
                    id SERIAL PRIMARY KEY,
                    email_id VARCHAR(255) UNIQUE NOT NULL,
                    thread_id VARCHAR(255),
                    subject TEXT,
                    from_address VARCHAR(500),
                    from_name VARCHAR(500),
                    to_addresses TEXT[],
                    to_names TEXT[],
                    cc_addresses TEXT[],
                    cc_names TEXT[],
                    bcc_addresses TEXT[],
                    bcc_names TEXT[],
                    in_reply_to TEXT[],
                    body_text TEXT,
                    body_html TEXT,
                    sent_at TIMESTAMP,
                    received_at TIMESTAMP,
                    labels TEXT[],
                    categorized_labels JSONB,
                    draft BOOLEAN DEFAULT FALSE,
                    deleted BOOLEAN DEFAULT FALSE,
                    deleted_at TIMESTAMP,
                    source_links JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE INDEX IF NOT EXISTS idx_emails_email_id ON emails(email_id);
                CREATE INDEX IF NOT EXISTS idx_emails_thread_id ON emails(thread_id);
                CREATE INDEX IF NOT EXISTS idx_emails_deleted ON emails(deleted);
            """)
            
            # Attachments table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS attachments (
                    id SERIAL PRIMARY KEY,
                    email_id VARCHAR(255) REFERENCES emails(email_id) ON DELETE CASCADE,
                    filename VARCHAR(500),
                    content_type VARCHAR(255),
                    byte_size INTEGER,
                    source_url TEXT,
                    checksum VARCHAR(64),
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE INDEX IF NOT EXISTS idx_attachments_email_id ON attachments(email_id);
            """)
            
            # Tasks table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    task_id VARCHAR(255) UNIQUE NOT NULL,
                    name TEXT,
                    description TEXT,
                    status VARCHAR(100),
                    priority VARCHAR(50),
                    progress INTEGER,
                    tag_ids TEXT[],
                    tags TEXT[],
                    categorized_tags JSONB,
                    assignee_user_ids TEXT[],
                    assignees TEXT[],
                    attachments JSONB,
                    project_id VARCHAR(255),
                    project_name TEXT,
                    tasklist_id VARCHAR(255),
                    tasklist_name TEXT,
                    parent_task VARCHAR(255),
                    start_date TIMESTAMP,
                    due_date TIMESTAMP,
                    updated_at TIMESTAMP,
                    updated_by_id VARCHAR(255),
                    updated_by VARCHAR(500),
                    created_at TIMESTAMP,
                    created_by_id VARCHAR(255),
                    created_by VARCHAR(500),
                    date_updated TIMESTAMP,
                    estimate_minutes INTEGER,
                    accumulated_estimated_minutes INTEGER,
                    deleted_at TIMESTAMP,
                    source_links JSONB,
                    db_created_at TIMESTAMP DEFAULT NOW(),
                    db_updated_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE INDEX IF NOT EXISTS idx_tasks_task_id ON tasks(task_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks(project_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_tasklist_id ON tasks(tasklist_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_deleted_at ON tasks(deleted_at);
                CREATE INDEX IF NOT EXISTS idx_tasks_updated_at ON tasks(updated_at);
            """)
            
            # Checkpoints table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    source VARCHAR(50) PRIMARY KEY,
                    last_event_time TIMESTAMP NOT NULL,
                    last_cursor TEXT,
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """)
            
            self.conn.commit()
    
    def upsert_email(self, email: Email) -> None:
        """Insert or update an email record."""
        self.upsert_emails_batch([email])

    def upsert_emails_batch(self, emails: List[Email]) -> None:
        """Insert or update multiple email records in a batch."""
        if not emails:
            return
        
        try:
            with self.conn.cursor() as cur:
                # Prepare data for batch insert
                email_data = []
                attachment_data = []
                
                for email in emails:
                    email_data.append((
                        email.email_id,
                        email.thread_id,
                        email.subject,
                        email.from_address,
                        email.from_name,
                        email.to_addresses,
                        email.to_names,
                        email.cc_addresses,
                        email.cc_names,
                        email.bcc_addresses,
                        email.bcc_names,
                        email.in_reply_to,
                        email.body_text,
                        email.body_html,
                        email.sent_at,
                        email.received_at,
                        email.labels,
                        Json(email.categorized_labels) if email.categorized_labels else None,
                        email.draft,
                        email.deleted,
                        email.deleted_at,
                        Json(email.source_links)
                    ))
                    
                    # Collect attachments
                    if email.attachments:
                        for att in email.attachments:
                            attachment_data.append((
                                email.email_id,
                                att.filename,
                                att.content_type,
                                att.byte_size,
                                att.source_url,
                                att.checksum
                            ))
                
                # Batch upsert emails
                execute_batch(cur, """
                    INSERT INTO emails (
                        email_id, thread_id, subject, from_address, from_name,
                        to_addresses, to_names, cc_addresses, cc_names,
                        bcc_addresses, bcc_names, in_reply_to,
                        body_text, body_html, sent_at, received_at,
                        labels, categorized_labels, draft, deleted, deleted_at, source_links
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (email_id) DO UPDATE SET
                        thread_id = EXCLUDED.thread_id,
                        subject = EXCLUDED.subject,
                        from_address = EXCLUDED.from_address,
                        from_name = EXCLUDED.from_name,
                        to_addresses = EXCLUDED.to_addresses,
                        to_names = EXCLUDED.to_names,
                        cc_addresses = EXCLUDED.cc_addresses,
                        cc_names = EXCLUDED.cc_names,
                        bcc_addresses = EXCLUDED.bcc_addresses,
                        bcc_names = EXCLUDED.bcc_names,
                        in_reply_to = EXCLUDED.in_reply_to,
                        body_text = EXCLUDED.body_text,
                        body_html = EXCLUDED.body_html,
                        sent_at = EXCLUDED.sent_at,
                        received_at = EXCLUDED.received_at,
                        labels = EXCLUDED.labels,
                        categorized_labels = EXCLUDED.categorized_labels,
                        draft = EXCLUDED.draft,
                        deleted = EXCLUDED.deleted,
                        deleted_at = EXCLUDED.deleted_at,
                        source_links = EXCLUDED.source_links,
                        updated_at = NOW()
                """, email_data)
                
                # Delete existing attachments for all emails in batch
                if attachment_data:
                    email_ids = tuple(email.email_id for email in emails if email.attachments)
                    if email_ids:
                        cur.execute("DELETE FROM attachments WHERE email_id = ANY(%s)", (list(email_ids),))
                    
                    # Batch insert attachments
                    execute_batch(cur, """
                        INSERT INTO attachments (
                            email_id, filename, content_type, byte_size, source_url, checksum
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                    """, attachment_data)
                
                self.conn.commit()
                logger.info(f"Batch upserted {len(emails)} emails in PostgreSQL")
        
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to batch upsert emails: {e}", exc_info=True)
            raise
    
    def upsert_task(self, task: Task) -> None:
        """Insert or update a task record."""
        self.upsert_tasks_batch([task])

    def upsert_tasks_batch(self, tasks: List[Task]) -> None:
        """Insert or update multiple task records in a batch."""
        if not tasks:
            return
        
        try:
            with self.conn.cursor() as cur:
                # Prepare data for batch insert
                task_data = []
                
                for task in tasks:
                    raw = task.raw or {}
                    
                    # Helper to parse datetime strings
                    def parse_dt(value: Optional[str]) -> Optional[datetime]:
                        if not value:
                            return None
                        try:
                            return datetime.fromisoformat(value.replace("Z", "+00:00"))
                        except Exception:
                            return None
                    
                    # Extract tag IDs
                    tag_ids = None
                    if raw.get("tagIds"):
                        tag_ids = [str(t) for t in raw.get("tagIds", [])]
                    
                    # Extract assignee user IDs
                    assignee_user_ids = None
                    if raw.get("assigneeUserIds"):
                        assignee_user_ids = [str(u) for u in raw.get("assigneeUserIds", [])]
                    
                    # Extract user IDs from nested objects
                    updated_by_id = None
                    if raw.get("updatedBy"):
                        if isinstance(raw["updatedBy"], dict) and raw["updatedBy"].get("id"):
                            updated_by_id = str(raw["updatedBy"]["id"])
                        elif not isinstance(raw["updatedBy"], dict):
                            updated_by_id = str(raw["updatedBy"])
                    
                    created_by_id = None
                    if raw.get("createdBy"):
                        if isinstance(raw["createdBy"], dict) and raw["createdBy"].get("id"):
                            created_by_id = str(raw["createdBy"]["id"])
                        elif not isinstance(raw["createdBy"], dict):
                            created_by_id = str(raw["createdBy"])
                    
                    task_data.append((
                        task.task_id,
                        raw.get("name"),
                        raw.get("description"),
                        raw.get("status"),
                        raw.get("priority"),
                        int(raw.get("progress")) if raw.get("progress") is not None else None,
                        tag_ids,
                        task.tags if task.tags else None,
                        Json(task.categorized_tags) if task.categorized_tags else None,
                        assignee_user_ids,
                        task.assignees if task.assignees else None,
                        Json(raw.get("attachments")) if raw.get("attachments") is not None else None,
                        task.project_id,
                        task.project_name,
                        task.tasklist_id if task.tasklist_id else (str(raw.get("tasklistId")) if raw.get("tasklistId") is not None else None),
                        task.tasklist_name,
                        str(raw.get("parentTask")) if raw.get("parentTask") is not None else None,
                        parse_dt(raw.get("startDate")),
                        parse_dt(raw.get("dueDate")),
                        parse_dt(raw.get("updatedAt")),
                        updated_by_id,
                        task.updated_by,
                        parse_dt(raw.get("createdAt")),
                        created_by_id,
                        task.created_by,
                        parse_dt(raw.get("dateUpdated")),
                        int(raw.get("estimateMinutes")) if raw.get("estimateMinutes") is not None else None,
                        int(raw.get("accumulatedEstimatedMinutes")) if raw.get("accumulatedEstimatedMinutes") is not None else None,
                        parse_dt(raw.get("deletedAt")),
                        Json(task.source_links)
                    ))
                
                # Batch upsert tasks
                execute_batch(cur, """
                    INSERT INTO tasks (
                        task_id, name, description, status, priority, progress,
                        tag_ids, tags, categorized_tags,
                        assignee_user_ids, assignees, attachments,
                        project_id, project_name, tasklist_id, tasklist_name, parent_task,
                        start_date, due_date, updated_at,
                        updated_by_id, updated_by,
                        created_at, created_by_id, created_by,
                        date_updated, estimate_minutes, accumulated_estimated_minutes,
                        deleted_at, source_links
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (task_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        status = EXCLUDED.status,
                        priority = EXCLUDED.priority,
                        progress = EXCLUDED.progress,
                        tag_ids = EXCLUDED.tag_ids,
                        tags = EXCLUDED.tags,
                        categorized_tags = EXCLUDED.categorized_tags,
                        assignee_user_ids = EXCLUDED.assignee_user_ids,
                        assignees = EXCLUDED.assignees,
                        attachments = EXCLUDED.attachments,
                        project_id = EXCLUDED.project_id,
                        project_name = EXCLUDED.project_name,
                        tasklist_id = EXCLUDED.tasklist_id,
                        tasklist_name = EXCLUDED.tasklist_name,
                        parent_task = EXCLUDED.parent_task,
                        start_date = EXCLUDED.start_date,
                        due_date = EXCLUDED.due_date,
                        updated_at = EXCLUDED.updated_at,
                        updated_by_id = EXCLUDED.updated_by_id,
                        updated_by = EXCLUDED.updated_by,
                        created_at = EXCLUDED.created_at,
                        created_by_id = EXCLUDED.created_by_id,
                        created_by = EXCLUDED.created_by,
                        date_updated = EXCLUDED.date_updated,
                        estimate_minutes = EXCLUDED.estimate_minutes,
                        accumulated_estimated_minutes = EXCLUDED.accumulated_estimated_minutes,
                        deleted_at = EXCLUDED.deleted_at,
                        source_links = EXCLUDED.source_links,
                        db_updated_at = NOW()
                """, task_data)
                
                self.conn.commit()
                logger.info(f"Batch upserted {len(tasks)} tasks in PostgreSQL")
        
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to batch upsert tasks: {e}", exc_info=True)
            raise
    
    def mark_email_deleted(self, email_id: str) -> None:
        """Mark an email as deleted."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE emails
                    SET deleted = TRUE, deleted_at = NOW(), updated_at = NOW()
                    WHERE email_id = %s
                """, (email_id,))
                self.conn.commit()
                logger.info(f"Marked email {email_id} as deleted")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to mark email {email_id} as deleted: {e}", exc_info=True)
            raise
    
    def mark_task_deleted(self, task_id: str) -> None:
        """Mark a task as deleted."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE tasks
                    SET deleted_at = NOW(), db_updated_at = NOW()
                    WHERE task_id = %s
                """, (task_id,))
                self.conn.commit()
                logger.info(f"Marked task {task_id} as deleted")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to mark task {task_id} as deleted: {e}", exc_info=True)
            raise
    
    def get_checkpoint(self, source: str) -> Optional[Checkpoint]:
        """Get the last sync checkpoint for a source."""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT source, last_event_time, last_cursor
                    FROM checkpoints
                    WHERE source = %s
                """, (source,))
                row = cur.fetchone()
                if row:
                    return Checkpoint(
                        source=row["source"],
                        last_event_time=row["last_event_time"],
                        last_cursor=row["last_cursor"]
                    )
        except Exception as e:
            logger.error(f"Failed to get checkpoint for {source}: {e}", exc_info=True)
        return None
    
    def set_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Save a sync checkpoint for a source."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO checkpoints (source, last_event_time, last_cursor, updated_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (source) DO UPDATE SET
                        last_event_time = EXCLUDED.last_event_time,
                        last_cursor = EXCLUDED.last_cursor,
                        updated_at = NOW()
                """, (checkpoint.source, checkpoint.last_event_time, checkpoint.last_cursor))
                self.conn.commit()
                logger.debug(f"Saved checkpoint for {checkpoint.source}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to save checkpoint for {checkpoint.source}: {e}", exc_info=True)
            raise
    
    def close(self) -> None:
        """Close database connections."""
        if self.conn:
            self.conn.close()

