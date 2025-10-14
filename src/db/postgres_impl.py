"""PostgreSQL implementation of the database interface."""
import json
from datetime import datetime
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor, Json

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
                    to_addresses TEXT[],
                    cc_addresses TEXT[],
                    bcc_addresses TEXT[],
                    body_text TEXT,
                    body_html TEXT,
                    sent_at TIMESTAMP,
                    received_at TIMESTAMP,
                    labels TEXT[],
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
                    project_id VARCHAR(255),
                    title TEXT,
                    description TEXT,
                    status VARCHAR(100),
                    tags TEXT[],
                    assignees TEXT[],
                    due_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    deleted BOOLEAN DEFAULT FALSE,
                    deleted_at TIMESTAMP,
                    source_links JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE INDEX IF NOT EXISTS idx_tasks_task_id ON tasks(task_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks(project_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_deleted ON tasks(deleted);
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
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO emails (
                        email_id, thread_id, subject, from_address,
                        to_addresses, cc_addresses, bcc_addresses,
                        body_text, body_html, sent_at, received_at,
                        labels, deleted, deleted_at, source_links
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (email_id) DO UPDATE SET
                        thread_id = EXCLUDED.thread_id,
                        subject = EXCLUDED.subject,
                        from_address = EXCLUDED.from_address,
                        to_addresses = EXCLUDED.to_addresses,
                        cc_addresses = EXCLUDED.cc_addresses,
                        bcc_addresses = EXCLUDED.bcc_addresses,
                        body_text = EXCLUDED.body_text,
                        body_html = EXCLUDED.body_html,
                        sent_at = EXCLUDED.sent_at,
                        received_at = EXCLUDED.received_at,
                        labels = EXCLUDED.labels,
                        deleted = EXCLUDED.deleted,
                        deleted_at = EXCLUDED.deleted_at,
                        source_links = EXCLUDED.source_links,
                        updated_at = NOW()
                """, (
                    email.email_id,
                    email.thread_id,
                    email.subject,
                    email.from_address,
                    email.to_addresses,
                    email.cc_addresses,
                    email.bcc_addresses,
                    email.body_text,
                    email.body_html,
                    email.sent_at,
                    email.received_at,
                    email.labels,
                    email.deleted,
                    email.deleted_at,
                    Json(email.source_links)
                ))
                
                # Handle attachments
                if email.attachments:
                    # Delete existing attachments
                    cur.execute("DELETE FROM attachments WHERE email_id = %s", (email.email_id,))
                    
                    # Insert new attachments
                    for att in email.attachments:
                        cur.execute("""
                            INSERT INTO attachments (
                                email_id, filename, content_type, byte_size, source_url, checksum
                            ) VALUES (%s, %s, %s, %s, %s, %s)
                        """, (
                            email.email_id,
                            att.filename,
                            att.content_type,
                            att.byte_size,
                            att.source_url,
                            att.checksum
                        ))
                
                self.conn.commit()
                logger.info(f"Upserted email {email.email_id} in PostgreSQL")
        
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to upsert email {email.email_id}: {e}", exc_info=True)
            raise
    
    def upsert_task(self, task: Task) -> None:
        """Insert or update a task record."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO tasks (
                        task_id, project_id, title, description, status,
                        tags, assignees, due_at, updated_at,
                        deleted, deleted_at, source_links
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (task_id) DO UPDATE SET
                        project_id = EXCLUDED.project_id,
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        status = EXCLUDED.status,
                        tags = EXCLUDED.tags,
                        assignees = EXCLUDED.assignees,
                        due_at = EXCLUDED.due_at,
                        updated_at = EXCLUDED.updated_at,
                        deleted = EXCLUDED.deleted,
                        deleted_at = EXCLUDED.deleted_at,
                        source_links = EXCLUDED.source_links
                """, (
                    task.task_id,
                    task.project_id,
                    task.title,
                    task.description,
                    task.status,
                    task.tags,
                    task.assignees,
                    task.due_at,
                    task.updated_at,
                    task.deleted,
                    task.deleted_at,
                    Json(task.source_links)
                ))
                
                self.conn.commit()
                logger.info(f"Upserted task {task.task_id} in PostgreSQL")
        
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to upsert task {task.task_id}: {e}", exc_info=True)
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
                    SET deleted = TRUE, deleted_at = NOW()
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

