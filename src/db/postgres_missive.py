"""PostgreSQL operations for Missive entities."""
from typing import Dict, Any
from psycopg2.extras import Json

from src.logging_conf import logger


class PostgresMissiveOps:
    """Missive entity operations."""
    
    def upsert_m_user(self, user_data: Dict[str, Any]) -> None:
        """Upsert a Missive user."""
        try:
            user_id = user_data.get("id")
            if not user_id:
                return
            
            email = user_data.get("email")
            name = user_data.get("name")
            
            # Get or create contact for this user
            contact_id = None
            if email:
                contact_id = self._get_or_create_contact(email, name)
            
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO missive.users (id, name, email, contact_id, raw_data)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        email = EXCLUDED.email,
                        contact_id = EXCLUDED.contact_id,
                        raw_data = EXCLUDED.raw_data,
                        db_updated_at = NOW()
                """, (
                    user_id,
                    name,
                    email,
                    contact_id,
                    Json(user_data)
                ))
                self.conn.commit()
                logger.debug(f"Upserted Missive user {user_id}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to upsert Missive user: {e}", exc_info=True)
    
    def upsert_m_team(self, team_data: Dict[str, Any]) -> None:
        """Upsert a Missive team."""
        try:
            team_id = team_data.get("id")
            if not team_id:
                return
            
            org_id = team_data.get("organization")
            if isinstance(org_id, dict):
                org_id = org_id.get("id")
            
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO missive.teams (id, name, organization_id, raw_data)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        organization_id = EXCLUDED.organization_id,
                        raw_data = EXCLUDED.raw_data,
                        db_updated_at = NOW()
                """, (
                    team_id,
                    team_data.get("name"),
                    org_id,
                    Json(team_data)
                ))
                self.conn.commit()
                logger.debug(f"Upserted Missive team {team_id}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to upsert Missive team: {e}", exc_info=True)
    
    def upsert_m_shared_label(self, label_data: Dict[str, Any]) -> None:
        """Upsert a Missive shared label."""
        try:
            label_id = label_data.get("id")
            if not label_id:
                return
            
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO missive.shared_labels (id, name, raw_data)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        raw_data = EXCLUDED.raw_data,
                        db_updated_at = NOW()
                """, (
                    label_id,
                    label_data.get("name"),
                    Json(label_data)
                ))
                self.conn.commit()
                logger.debug(f"Upserted Missive label {label_id}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to upsert Missive label: {e}", exc_info=True)
    
    def upsert_m_conversation(self, conversation_data: Dict[str, Any]) -> None:
        """Upsert a Missive conversation with all related entities."""
        try:
            conversation_id = conversation_data.get("id")
            if not conversation_id:
                return
            
            # Extract team ID
            team_id = None
            if conversation_data.get("team"):
                team = conversation_data["team"]
                if isinstance(team, dict):
                    team_id = team.get("id")
                    # Upsert team
                    self.upsert_m_team(team)
            
            # Extract organization ID
            org_id = None
            if conversation_data.get("organization"):
                org = conversation_data["organization"]
                if isinstance(org, dict):
                    org_id = org.get("id")
            
            # Convert timestamp
            last_activity_at = self._convert_unix_timestamp(conversation_data.get("last_activity_at"))
            
            with self.conn.cursor() as cur:
                # Upsert conversation
                cur.execute("""
                    INSERT INTO missive.conversations (
                        id, subject, latest_message_subject, team_id, organization_id, color,
                        attachments_count, messages_count, drafts_count, send_later_messages_count,
                        tasks_count, completed_tasks_count, last_activity_at, web_url, app_url, raw_data
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        subject = EXCLUDED.subject,
                        latest_message_subject = EXCLUDED.latest_message_subject,
                        team_id = EXCLUDED.team_id,
                        organization_id = EXCLUDED.organization_id,
                        color = EXCLUDED.color,
                        attachments_count = EXCLUDED.attachments_count,
                        messages_count = EXCLUDED.messages_count,
                        drafts_count = EXCLUDED.drafts_count,
                        send_later_messages_count = EXCLUDED.send_later_messages_count,
                        tasks_count = EXCLUDED.tasks_count,
                        completed_tasks_count = EXCLUDED.completed_tasks_count,
                        last_activity_at = EXCLUDED.last_activity_at,
                        web_url = EXCLUDED.web_url,
                        app_url = EXCLUDED.app_url,
                        raw_data = EXCLUDED.raw_data,
                        db_updated_at = NOW()
                """, (
                    conversation_id,
                    conversation_data.get("subject"),
                    conversation_data.get("latest_message_subject"),
                    team_id,
                    org_id,
                    conversation_data.get("color"),
                    conversation_data.get("attachments_count", 0),
                    conversation_data.get("messages_count", 1),
                    conversation_data.get("drafts_count", 0),
                    conversation_data.get("send_later_messages_count", 0),
                    conversation_data.get("tasks_count", 0),
                    conversation_data.get("completed_tasks_count", 0),
                    last_activity_at,
                    conversation_data.get("web_url"),
                    conversation_data.get("app_url"),
                    Json(conversation_data)
                ))
                
                # Handle users
                if conversation_data.get("users"):
                    # Clear existing users
                    cur.execute("DELETE FROM missive.conversation_users WHERE conversation_id = %s", (conversation_id,))
                    
                    for user in conversation_data["users"]:
                        user_id = user.get("id")
                        if user_id:
                            # Upsert user
                            self.upsert_m_user(user)
                            
                            # Insert into junction table
                            cur.execute("""
                                INSERT INTO missive.conversation_users (
                                    conversation_id, user_id, unassigned, closed, archived,
                                    trashed, junked, assigned, flagged, snoozed
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (conversation_id, user_id) DO UPDATE SET
                                    unassigned = EXCLUDED.unassigned,
                                    closed = EXCLUDED.closed,
                                    archived = EXCLUDED.archived,
                                    trashed = EXCLUDED.trashed,
                                    junked = EXCLUDED.junked,
                                    assigned = EXCLUDED.assigned,
                                    flagged = EXCLUDED.flagged,
                                    snoozed = EXCLUDED.snoozed
                            """, (
                                conversation_id, user_id,
                                user.get("unassigned", True),
                                user.get("closed", False),
                                user.get("archived", False),
                                user.get("trashed", False),
                                user.get("junked", False),
                                user.get("assigned", False),
                                user.get("flagged", False),
                                user.get("snoozed", False)
                            ))
                
                # Handle assignees
                if conversation_data.get("assignees"):
                    # Clear existing assignees
                    cur.execute("DELETE FROM missive.conversation_assignees WHERE conversation_id = %s", (conversation_id,))
                    
                    for assignee in conversation_data["assignees"]:
                        assignee_id = assignee.get("id")
                        if assignee_id:
                            # Upsert user
                            self.upsert_m_user(assignee)
                            
                            # Insert into junction table
                            cur.execute("""
                                INSERT INTO missive.conversation_assignees (conversation_id, user_id)
                                VALUES (%s, %s)
                                ON CONFLICT DO NOTHING
                            """, (conversation_id, assignee_id))
                
                # Handle shared labels
                if conversation_data.get("shared_labels"):
                    # Clear existing labels
                    cur.execute("DELETE FROM missive.conversation_labels WHERE conversation_id = %s", (conversation_id,))
                    
                    for label in conversation_data["shared_labels"]:
                        label_id = label.get("id")
                        if label_id:
                            # Upsert label
                            self.upsert_m_shared_label(label)
                            
                            # Insert into junction table
                            cur.execute("""
                                INSERT INTO missive.conversation_labels (conversation_id, label_id)
                                VALUES (%s, %s)
                                ON CONFLICT DO NOTHING
                            """, (conversation_id, label_id))
                
                # Handle authors
                if conversation_data.get("authors"):
                    # Clear existing authors
                    cur.execute("DELETE FROM missive.conversation_authors WHERE conversation_id = %s", (conversation_id,))
                    
                    for author in conversation_data["authors"]:
                        # Get or create contact for this author
                        contact_id = self._get_or_create_contact(author.get("address"), author.get("name"))
                        
                        if contact_id:
                            cur.execute("""
                                INSERT INTO missive.conversation_authors (conversation_id, contact_id)
                                VALUES (%s, %s)
                            """, (conversation_id, contact_id))
                
                self.conn.commit()
                logger.debug(f"Upserted Missive conversation {conversation_id}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to upsert Missive conversation: {e}", exc_info=True)
    
    def upsert_m_message(self, message_data: Dict[str, Any], conversation_id: str) -> None:
        """Upsert a Missive message with all related entities."""
        try:
            message_id = message_data.get("id")
            if not message_id:
                return
            
            # Extract from field and get/create contact
            from_field = message_data.get("from_field") or message_data.get("from")
            from_contact_id = None
            if from_field and isinstance(from_field, dict):
                from_name = from_field.get("name")
                from_address = from_field.get("address")
                from_contact_id = self._get_or_create_contact(from_address, from_name)
            
            # Convert timestamps
            delivered_at = self._convert_unix_timestamp(message_data.get("delivered_at"))
            created_at = self._convert_unix_timestamp(message_data.get("created_at"))
            updated_at = self._convert_unix_timestamp(message_data.get("updated_at"))
            
            with self.conn.cursor() as cur:
                # Upsert message
                cur.execute("""
                    INSERT INTO missive.messages (
                        id, conversation_id, subject, preview, type, email_message_id, body,
                        from_contact_id, delivered_at, created_at, updated_at, raw_data
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        conversation_id = EXCLUDED.conversation_id,
                        subject = EXCLUDED.subject,
                        preview = EXCLUDED.preview,
                        type = EXCLUDED.type,
                        email_message_id = EXCLUDED.email_message_id,
                        body = EXCLUDED.body,
                        from_contact_id = EXCLUDED.from_contact_id,
                        delivered_at = EXCLUDED.delivered_at,
                        updated_at = EXCLUDED.updated_at,
                        raw_data = EXCLUDED.raw_data,
                        db_updated_at = NOW()
                """, (
                    message_id,
                    conversation_id,
                    message_data.get("subject"),
                    message_data.get("preview"),
                    message_data.get("type"),
                    message_data.get("email_message_id"),
                    message_data.get("body"),
                    from_contact_id,
                    delivered_at,
                    created_at,
                    updated_at,
                    Json(message_data)
                ))
                
                # Clear existing recipients
                cur.execute("DELETE FROM missive.message_recipients WHERE message_id = %s", (message_id,))
                
                # Handle to_fields
                for recipient in message_data.get("to_fields", []):
                    contact_id = self._get_or_create_contact(recipient.get("address"), recipient.get("name"))
                    if contact_id:
                        cur.execute("""
                            INSERT INTO m_message_recipients (message_id, recipient_type, contact_id)
                            VALUES (%s, %s, %s)
                        """, (message_id, "to", contact_id))
                
                # Handle cc_fields
                for recipient in message_data.get("cc_fields", []):
                    contact_id = self._get_or_create_contact(recipient.get("address"), recipient.get("name"))
                    if contact_id:
                        cur.execute("""
                            INSERT INTO missive.message_recipients (message_id, recipient_type, contact_id)
                            VALUES (%s, %s, %s)
                        """, (message_id, "cc", contact_id))
                
                # Handle bcc_fields
                for recipient in message_data.get("bcc_fields", []):
                    contact_id = self._get_or_create_contact(recipient.get("address"), recipient.get("name"))
                    if contact_id:
                        cur.execute("""
                            INSERT INTO missive.message_recipients (message_id, recipient_type, contact_id)
                            VALUES (%s, %s, %s)
                        """, (message_id, "bcc", contact_id))
                
                # Handle attachments
                if message_data.get("attachments"):
                    # Clear existing attachments
                    cur.execute("DELETE FROM missive.attachments WHERE message_id = %s", (message_id,))
                    
                    for attachment in message_data["attachments"]:
                        attachment_id = attachment.get("id")
                        if attachment_id:
                            cur.execute("""
                                INSERT INTO missive.attachments (
                                    id, message_id, filename, extension, url, media_type,
                                    sub_type, size, width, height, raw_data
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (id) DO UPDATE SET
                                    message_id = EXCLUDED.message_id,
                                    filename = EXCLUDED.filename,
                                    extension = EXCLUDED.extension,
                                    url = EXCLUDED.url,
                                    media_type = EXCLUDED.media_type,
                                    sub_type = EXCLUDED.sub_type,
                                    size = EXCLUDED.size,
                                    width = EXCLUDED.width,
                                    height = EXCLUDED.height,
                                    raw_data = EXCLUDED.raw_data
                            """, (
                                attachment_id,
                                message_id,
                                attachment.get("filename"),
                                attachment.get("extension"),
                                attachment.get("url"),
                                attachment.get("media_type"),
                                attachment.get("sub_type"),
                                attachment.get("size"),
                                attachment.get("width"),
                                attachment.get("height"),
                                Json(attachment)
                            ))
                
                self.conn.commit()
                logger.debug(f"Upserted Missive message {message_id}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to upsert Missive message: {e}", exc_info=True)

