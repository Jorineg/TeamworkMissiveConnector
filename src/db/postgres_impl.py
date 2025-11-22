"""PostgreSQL implementation of the database interface."""
from src.db.interface import DatabaseInterface
from src.db.postgres_connection import PostgresConnection
from src.db.postgres_schema import PostgresSchema
from src.db.postgres_teamwork import PostgresTeamworkOps
from src.db.postgres_missive import PostgresMissiveOps
from src.db.postgres_legacy import PostgresLegacyOps
from src.logging_conf import logger


class PostgresDatabase(
    PostgresConnection,
    PostgresTeamworkOps,
    PostgresMissiveOps,
    PostgresLegacyOps,
    DatabaseInterface
):
    """PostgreSQL implementation of database operations.
    
    This class combines functionality from multiple modules:
    - PostgresConnection: Connection management and helper utilities
    - PostgresTeamworkOps: Teamwork entity operations
    - PostgresMissiveOps: Missive entity operations  
    - PostgresLegacyOps: Legacy email/task/checkpoint operations
    - DatabaseInterface: Abstract interface definition
    """
    
    def __init__(self):
        """Initialize database connection and ensure tables exist."""
        # Initialize the connection (from PostgresConnection)
        PostgresConnection.__init__(self)
        
        # Ensure all tables are created
        schema = PostgresSchema()
        schema.ensure_tables(self.conn)
        
        logger.info("PostgreSQL database initialized successfully")
