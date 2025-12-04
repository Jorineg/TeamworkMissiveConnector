"""PostgreSQL operations for legacy email/task tables and checkpoints."""
from typing import List, Optional
from psycopg2.extras import Json, execute_batch
from psycopg2.extras import RealDictCursor

from src.db.models import Email, Task, Checkpoint
from src.logging_conf import logger


class PostgresLegacyOps:
    """Legacy email, task, and checkpoint operations."""
    
    def upsert_email(self, email: Email) -> None:
        """Insert or update an email record (legacy - now no-op, use relational structure)."""
        self.upsert_emails_batch([email])

    def upsert_emails_batch(self, emails: List[Email]) -> None:
        """
        Insert or update multiple email records in a batch.
        
        DEPRECATED: Legacy emails table has been removed. Email data is now stored in
        the relational structure (m_conversations, m_messages, m_message_recipients, etc.)
        which is handled automatically by MissiveEventHandler.process_event().
        
        This method is kept as a no-op for backward compatibility.
        """
        if not emails:
            return
        
        logger.debug(f"Legacy upsert_emails_batch called with {len(emails)} emails (no-op - using relational structure)")
    
    def upsert_task(self, task: Task) -> None:
        """Insert or update a task record."""
        self.upsert_tasks_batch([task])

    def upsert_tasks_batch(self, tasks: List[Task]) -> None:
        """Insert or update multiple task records in a batch with relational structure."""
        if not tasks:
            return
        
        try:
            with self.conn.cursor() as cur:
                # Prepare data for batch insert
                task_data = []
                
                for task in tasks:
                    raw = task.raw or {}
                    
                    # Extract user IDs from nested objects
                    updated_by_id = self._extract_id(raw.get("updatedBy"))
                    created_by_id = self._extract_id(raw.get("createdBy"))
                    
                    # Extract project and tasklist IDs
                    project_id = self._extract_id(raw.get("project") or task.project_id)
                    tasklist_id = self._extract_id(raw.get("tasklist") or raw.get("tasklistId") or task.tasklist_id)
                    
                    # Extract parent task ID (INTEGER in new schema)
                    parent_task_id = self._extract_id(raw.get("parentTask"))
                    
                    # Convert task_id (string) to integer for new schema
                    task_id_int = int(task.task_id)
                    
                    task_data.append((
                        task_id_int,
                        project_id,
                        tasklist_id,
                        raw.get("name"),
                        raw.get("description"),
                        raw.get("status"),
                        raw.get("priority"),
                        int(raw.get("progress")) if raw.get("progress") is not None else None,
                        parent_task_id,
                        self._parse_dt(raw.get("startDate")),
                        self._parse_dt(raw.get("dueDate")),
                        int(raw.get("estimateMinutes")) if raw.get("estimateMinutes") is not None else None,
                        int(raw.get("accumulatedEstimatedMinutes")) if raw.get("accumulatedEstimatedMinutes") is not None else None,
                        self._parse_dt(raw.get("createdAt")),
                        created_by_id,
                        self._parse_dt(raw.get("updatedAt")),
                        updated_by_id,
                        self._parse_dt(raw.get("deletedAt")),
                        Json(task.source_links),
                        Json(raw)
                    ))
                
                # Batch upsert tasks
                execute_batch(cur, """
                    INSERT INTO teamwork.tasks (
                        id, project_id, tasklist_id, name, description, status, priority, progress,
                        parent_task, start_date, due_date, estimate_minutes, accumulated_estimated_minutes,
                        created_at, created_by_id, updated_at, updated_by_id,
                        deleted_at, source_links, raw_data
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        project_id = EXCLUDED.project_id,
                        tasklist_id = EXCLUDED.tasklist_id,
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        status = EXCLUDED.status,
                        priority = EXCLUDED.priority,
                        progress = EXCLUDED.progress,
                        parent_task = EXCLUDED.parent_task,
                        start_date = EXCLUDED.start_date,
                        due_date = EXCLUDED.due_date,
                        estimate_minutes = EXCLUDED.estimate_minutes,
                        accumulated_estimated_minutes = EXCLUDED.accumulated_estimated_minutes,
                        updated_at = EXCLUDED.updated_at,
                        updated_by_id = EXCLUDED.updated_by_id,
                        deleted_at = EXCLUDED.deleted_at,
                        source_links = EXCLUDED.source_links,
                        raw_data = EXCLUDED.raw_data,
                        db_updated_at = NOW()
                """, task_data)
                
                self.conn.commit()
                logger.info(f"Batch upserted {len(tasks)} tasks in PostgreSQL")
        
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to batch upsert tasks: {e}", exc_info=True)
            raise
    
    def mark_email_deleted(self, email_id: str) -> None:
        """
        Mark an email as deleted.
        
        DEPRECATED: Legacy emails table has been removed. Messages are now in m_messages table.
        Deletion is handled by the relational structure.
        
        This method is kept as a no-op for backward compatibility.
        """
        logger.debug(f"Legacy mark_email_deleted called for {email_id} (no-op - using relational structure)")
    
    def mark_task_deleted(self, task_id: str) -> None:
        """Mark a task as deleted."""
        try:
            # Convert task_id to integer for new schema
            task_id_int = int(task_id)
            
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE teamwork.tasks
                    SET deleted_at = NOW(), db_updated_at = NOW()
                    WHERE id = %s
                """, (task_id_int,))
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
                    FROM teamworkmissiveconnector.checkpoints
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
                    INSERT INTO teamworkmissiveconnector.checkpoints (source, last_event_time, last_cursor, updated_at)
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

