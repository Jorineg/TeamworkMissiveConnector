"""PostgreSQL-based webhook configuration management."""
from typing import Optional, Dict, Any
import json

from src.logging_conf import logger


class WebhookConfigManager:
    """Manage webhook configuration in PostgreSQL."""
    
    def __init__(self, conn):
        """
        Initialize webhook config manager.
        
        Args:
            conn: psycopg2 connection object
        """
        self.conn = conn
    
    def get_webhook_ids(self, source: str) -> Optional[Dict[str, Any]]:
        """
        Get webhook IDs for a source.
        
        Args:
            source: Source system ('teamwork' or 'missive')
        
        Returns:
            Dictionary of webhook IDs or None if not found
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT webhook_ids
                    FROM teamworkmissiveconnector.webhook_config
                    WHERE source = %s AND is_active = TRUE
                """, (source,))
                
                row = cur.fetchone()
                if row:
                    return row[0]  # JSONB is automatically deserialized
                return None
        except Exception as e:
            logger.error(f"Failed to get webhook IDs for {source}: {e}", exc_info=True)
            return None
    
    def save_webhook_ids(self, source: str, webhook_ids: Dict[str, Any], webhook_url: Optional[str] = None) -> None:
        """
        Save webhook IDs for a source.
        
        Args:
            source: Source system ('teamwork' or 'missive')
            webhook_ids: Dictionary of webhook IDs
            webhook_url: Optional webhook URL
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO teamworkmissiveconnector.webhook_config (
                        source, webhook_ids, webhook_url, is_active, created_at
                    ) VALUES (%s, %s, %s, TRUE, NOW())
                    ON CONFLICT (source) DO UPDATE SET
                        webhook_ids = EXCLUDED.webhook_ids,
                        webhook_url = EXCLUDED.webhook_url,
                        is_active = EXCLUDED.is_active,
                        updated_at = NOW()
                """, (source, json.dumps(webhook_ids), webhook_url))
                
                self.conn.commit()
                logger.info(f"Saved webhook config for {source}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to save webhook IDs for {source}: {e}", exc_info=True)
            raise
    
    def delete_webhook_config(self, source: str) -> None:
        """
        Delete webhook configuration for a source.
        
        Args:
            source: Source system ('teamwork' or 'missive')
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM teamworkmissiveconnector.webhook_config
                    WHERE source = %s
                """, (source,))
                
                self.conn.commit()
                logger.info(f"Deleted webhook config for {source}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to delete webhook config for {source}: {e}", exc_info=True)
            raise
    
    def deactivate_webhooks(self, source: str) -> None:
        """
        Mark webhooks as inactive without deleting.
        
        Args:
            source: Source system ('teamwork' or 'missive')
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE teamworkmissiveconnector.webhook_config
                    SET is_active = FALSE, updated_at = NOW()
                    WHERE source = %s
                """, (source,))
                
                self.conn.commit()
                logger.info(f"Deactivated webhooks for {source}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to deactivate webhooks for {source}: {e}", exc_info=True)
            raise
    
    def verify_webhook(self, source: str) -> None:
        """
        Update last verified timestamp for webhook.
        
        Args:
            source: Source system ('teamwork' or 'missive')
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE teamworkmissiveconnector.webhook_config
                    SET last_verified_at = NOW(), updated_at = NOW()
                    WHERE source = %s
                """, (source,))
                
                self.conn.commit()
                logger.debug(f"Updated verification timestamp for {source}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to verify webhook for {source}: {e}", exc_info=True)

