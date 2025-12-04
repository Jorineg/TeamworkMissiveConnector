"""PostgreSQL connection management with automatic reconnection and resilience."""
import time
import functools
from datetime import datetime
from typing import Optional, Any, Callable, TypeVar
from contextlib import contextmanager
import psycopg2
from psycopg2 import OperationalError, InterfaceError

from src import settings
from src.logging_conf import logger

T = TypeVar('T')


def is_connection_error(exc: Exception) -> bool:
    """Check if an exception indicates a connection problem that warrants reconnection."""
    if isinstance(exc, (OperationalError, InterfaceError)):
        return True
    # Check for specific psycopg2 error messages indicating connection issues
    error_msg = str(exc).lower()
    connection_indicators = [
        'connection',
        'server closed',
        'network',
        'timeout',
        'could not connect',
        'terminating connection',
        'connection refused',
        'no route to host',
        'connection reset',
        'broken pipe',
        'ssl connection',
        'server unexpectedly closed',
    ]
    return any(indicator in error_msg for indicator in connection_indicators)


def with_db_retry(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator that adds retry logic with reconnection for database operations.
    
    This decorator will:
    1. Attempt the operation
    2. On connection failure, reconnect and retry up to DB_OPERATION_RETRIES times
    3. Use exponential backoff between retries
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs) -> T:
        last_exception = None
        delay = settings.DB_RECONNECT_DELAY
        
        for attempt in range(settings.DB_OPERATION_RETRIES + 1):
            try:
                # Ensure connection is valid before operation
                self._ensure_connected()
                return func(self, *args, **kwargs)
                
            except Exception as e:
                last_exception = e
                
                if is_connection_error(e):
                    if attempt < settings.DB_OPERATION_RETRIES:
                        logger.warning(
                            f"Database operation failed (attempt {attempt + 1}/{settings.DB_OPERATION_RETRIES + 1}): {e}. "
                            f"Reconnecting in {delay}s..."
                        )
                        time.sleep(delay)
                        # Mark connection as invalid to force reconnect
                        self._mark_connection_invalid()
                        # Exponential backoff with cap
                        delay = min(delay * 2, settings.DB_MAX_RECONNECT_DELAY)
                    else:
                        logger.error(f"Database operation failed after {settings.DB_OPERATION_RETRIES + 1} attempts: {e}")
                        raise
                else:
                    # Non-connection error, don't retry
                    raise
        
        raise last_exception
    
    return wrapper


class PostgresConnection:
    """Base PostgreSQL connection with automatic reconnection and resilience."""
    
    def __init__(self):
        """Initialize database connection manager."""
        self._conn: Optional[psycopg2.extensions.connection] = None
        self._connection_valid = False
        self._last_connection_attempt = 0
        self._connect()
    
    def _connect(self) -> bool:
        """
        Establish database connection with retry logic.
        
        Returns:
            True if connected successfully, False otherwise
        """
        delay = settings.DB_RECONNECT_DELAY
        
        while True:
            try:
                self._last_connection_attempt = time.time()
                
                # Close existing connection if any
                if self._conn is not None:
                    try:
                        self._conn.close()
                    except Exception:
                        pass
                
                # Build connection options
                conn_options = {
                    'dsn': settings.PG_DSN,
                    'connect_timeout': settings.DB_CONNECT_TIMEOUT,
                }
                
                self._conn = psycopg2.connect(**conn_options)
                self._connection_valid = True
                logger.info("PostgreSQL connection established")
                return True
                
            except Exception as e:
                self._connection_valid = False
                logger.warning(
                    f"Failed to connect to PostgreSQL: {e}. "
                    f"Retrying in {delay}s..."
                )
                time.sleep(delay)
                # Exponential backoff with cap
                delay = min(delay * 2, settings.DB_MAX_RECONNECT_DELAY)
    
    def _ensure_connected(self) -> None:
        """Ensure we have a valid database connection, reconnecting if necessary."""
        if self._connection_valid and self._conn is not None:
            try:
                # Quick connection test
                with self._conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return
            except Exception as e:
                logger.warning(f"Connection test failed: {e}")
                self._connection_valid = False
        
        # Need to reconnect
        logger.info("Reconnecting to PostgreSQL...")
        self._connect()
    
    def _mark_connection_invalid(self) -> None:
        """Mark the current connection as invalid (will reconnect on next operation)."""
        self._connection_valid = False
    
    @property
    def conn(self) -> psycopg2.extensions.connection:
        """
        Get the database connection, ensuring it's valid.
        
        Note: This property ensures the connection is valid before returning it.
        For operations that need resilience, use the @with_db_retry decorator.
        """
        self._ensure_connected()
        return self._conn
    
    def is_connected(self) -> bool:
        """Check if database connection is currently valid."""
        if not self._connection_valid or self._conn is None:
            return False
        try:
            with self._conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:
            self._connection_valid = False
            return False
    
    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            try:
                self._conn.close()
                logger.info("PostgreSQL connection closed")
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
            finally:
                self._conn = None
                self._connection_valid = False
    
    @contextmanager
    def get_cursor(self):
        """
        Get a database cursor with automatic connection management.
        
        Usage:
            with self.get_cursor() as cur:
                cur.execute("SELECT ...")
        """
        self._ensure_connected()
        cur = self._conn.cursor()
        try:
            yield cur
        finally:
            cur.close()
    
    def execute_with_retry(self, operation: Callable[[psycopg2.extensions.cursor], T]) -> T:
        """
        Execute a database operation with automatic retry on connection failure.
        
        Args:
            operation: A callable that takes a cursor and performs the operation
            
        Returns:
            The result of the operation
        """
        last_exception = None
        delay = settings.DB_RECONNECT_DELAY
        
        for attempt in range(settings.DB_OPERATION_RETRIES + 1):
            try:
                self._ensure_connected()
                with self._conn.cursor() as cur:
                    return operation(cur)
                    
            except Exception as e:
                last_exception = e
                
                if is_connection_error(e):
                    # Rollback any failed transaction
                    try:
                        self._conn.rollback()
                    except Exception:
                        pass
                    
                    if attempt < settings.DB_OPERATION_RETRIES:
                        logger.warning(
                            f"Database operation failed (attempt {attempt + 1}): {e}. "
                            f"Reconnecting in {delay}s..."
                        )
                        time.sleep(delay)
                        self._mark_connection_invalid()
                        delay = min(delay * 2, settings.DB_MAX_RECONNECT_DELAY)
                    else:
                        logger.error(f"Operation failed after {settings.DB_OPERATION_RETRIES + 1} attempts")
                        raise
                else:
                    # Non-connection error - rollback and re-raise
                    try:
                        self._conn.rollback()
                    except Exception:
                        pass
                    raise
        
        raise last_exception
    
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
