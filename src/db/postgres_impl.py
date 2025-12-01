"""PostgreSQL implementation of the database interface."""
from src.db.interface import DatabaseInterface
from src.db.postgres_connection import PostgresConnection
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
    
    Note: Database schema is managed in a separate repository (ibhelmDB).
    This code assumes all tables, columns, and views already exist.
    """
    
    def __init__(self):
        """Initialize database connection."""
        # Initialize the connection (from PostgresConnection)
        PostgresConnection.__init__(self)
        
        logger.info("PostgreSQL database connection initialized successfully")
