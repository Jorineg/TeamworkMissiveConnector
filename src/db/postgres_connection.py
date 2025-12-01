"""PostgreSQL connection management and helper utilities."""
from datetime import datetime
from typing import Optional, Any
import psycopg2

from src import settings
from src.logging_conf import logger


class PostgresConnection:
    """Base PostgreSQL connection and utility methods."""
    
    def __init__(self):
        """Initialize database connection."""
        self.conn = psycopg2.connect(settings.PG_DSN)
        logger.info("PostgreSQL connection established")
    
    def close(self) -> None:
        """Close database connections."""
        if self.conn:
            self.conn.close()
            logger.info("PostgreSQL connection closed")
    
    # ========================================
    # HELPER METHODS
    # ========================================
    
    def _parse_dt(self, value: Optional[str]) -> Optional[datetime]:
        """Parse datetime strings."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None
    
    def _parse_date(self, value: Optional[str]) -> Optional[datetime]:
        """Parse date strings (for DATE columns)."""
        if not value:
            return None
        try:
            # Try to parse as full datetime first
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.date()
        except Exception:
            try:
                # Try to parse as date only
                from datetime import date
                return datetime.strptime(value, "%Y-%m-%d").date()
            except Exception:
                return None
    
    def _extract_id(self, value: Any) -> Optional[int]:
        """Extract integer ID from various formats (nested object, string, int).
        Returns None for 0 values as they typically indicate no reference."""
        if value is None:
            return None
        if isinstance(value, dict):
            id_val = value.get("id")
            if id_val is not None:
                extracted = int(id_val)
                return extracted if extracted != 0 else None
            return None
        try:
            extracted = int(value)
            return extracted if extracted != 0 else None
        except (ValueError, TypeError):
            return None
    
    def _validate_fk_exists(self, table: str, fk_id: Optional[int]) -> Optional[int]:
        """Check if a foreign key ID exists in the referenced table.
        Returns the ID if it exists, None otherwise."""
        if fk_id is None:
            return None
        try:
            with self.conn.cursor() as cur:
                cur.execute(f"SELECT 1 FROM {table} WHERE id = %s", (fk_id,))
                if cur.fetchone():
                    return fk_id
                logger.warning(f"Foreign key {fk_id} not found in {table}, setting to NULL")
                return None
        except Exception as e:
            logger.error(f"Error validating foreign key {fk_id} in {table}: {e}")
            return None
    
    def _get_or_create_contact(self, email: Optional[str], name: Optional[str] = None) -> Optional[int]:
        """Get or create a contact by email. Returns contact_id."""
        if not email:
            return None
        
        try:
            with self.conn.cursor() as cur:
                # Try to find existing contact
                cur.execute("SELECT id FROM missive.contacts WHERE email = %s LIMIT 1", (email,))
                row = cur.fetchone()
                if row:
                    # Update name if provided and different
                    if name:
                        cur.execute("""
                            UPDATE missive.contacts SET name = %s, db_updated_at = NOW()
                            WHERE id = %s AND (name IS NULL OR name != %s)
                        """, (name, row[0], name))
                    return row[0]
                
                # Create new contact
                cur.execute("""
                    INSERT INTO missive.contacts (email, name)
                    VALUES (%s, %s)
                    RETURNING id
                """, (email, name))
                return cur.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting/creating contact for {email}: {e}")
            return None
    
    def _convert_unix_timestamp(self, timestamp: Optional[int]) -> Optional[datetime]:
        """Convert Unix timestamp (milliseconds or seconds) to datetime."""
        if timestamp is None:
            return None
        try:
            # Missive uses milliseconds
            if timestamp > 10000000000:  # If > year 2286 in seconds, it's milliseconds
                return datetime.fromtimestamp(timestamp / 1000.0)
            else:
                return datetime.fromtimestamp(timestamp)
        except Exception as e:
            logger.error(f"Error converting timestamp {timestamp}: {e}")
            return None

