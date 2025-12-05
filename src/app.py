"""Flask application for webhook endpoints with database resilience."""
import sys
import threading
import time
from flask import Flask, request, jsonify
from datetime import datetime, timezone
from typing import Optional

from src import settings
from src.logging_conf import logger
from src.queue.postgres_queue import PostgresQueue
from src.queue.models import QueueItem
from src.http.security import verify_teamwork_webhook, verify_missive_webhook
from src.db.postgres_impl import PostgresDatabase


# Create Flask app
app = Flask(__name__)


class DatabaseManager:
    """
    Manages database connection with lazy initialization and resilience.
    
    This class ensures the application can start even if the database is unavailable,
    and will automatically reconnect when the database becomes available again.
    """
    
    def __init__(self):
        self._db: Optional[PostgresDatabase] = None
        self._queue: Optional[PostgresQueue] = None
        self._lock = threading.Lock()
        self._last_connection_attempt = 0
        self._min_retry_interval = 5  # Minimum seconds between connection attempts
    
    def _try_connect(self) -> bool:
        """Attempt to establish database connection."""
        try:
            self._db = PostgresDatabase()
            self._queue = PostgresQueue(self._db)
            logger.info("Database connection established for Flask app")
            return True
        except Exception as e:
            logger.warning(f"Failed to connect to database: {e}")
            self._db = None
            self._queue = None
            return False
    
    def get_db(self) -> Optional[PostgresDatabase]:
        """
        Get the database instance, attempting to connect if not available.
        
        Returns:
            PostgresDatabase instance or None if unavailable
        """
        with self._lock:
            # Check if we have a valid connection
            if self._db is not None:
                try:
                    if self._db.is_connected():
                        return self._db
                except Exception:
                    pass
                
                # Connection is invalid, clean up
                try:
                    self._db.close()
                except Exception:
                    pass
                self._db = None
                self._queue = None
            
            # Rate limit connection attempts
            current_time = time.time()
            if current_time - self._last_connection_attempt < self._min_retry_interval:
                return None
            
            self._last_connection_attempt = current_time
            self._try_connect()
            return self._db
    
    def get_queue(self) -> Optional[PostgresQueue]:
        """
        Get the queue instance, attempting to connect if database not available.
        
        Returns:
            PostgresQueue instance or None if database unavailable
        """
        # Ensure database is connected first
        self.get_db()
        return self._queue
    
    def is_available(self) -> bool:
        """Check if database is currently available."""
        db = self.get_db()
        return db is not None
    
    def close(self):
        """Close database connection."""
        with self._lock:
            if self._db is not None:
                try:
                    self._db.close()
                except Exception:
                    pass
                self._db = None
                self._queue = None


# Global database manager (lazy initialization)
db_manager = DatabaseManager()

# Periodic backfill timer
_backfill_timer = None
_backfill_stop_event = threading.Event()

# Periodic Craft poll timer (separate from backfill)
_craft_poll_timer = None
_craft_poll_stop_event = threading.Event()


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint with database status."""
    db_available = db_manager.is_available()
    queue = db_manager.get_queue()
    
    # Get queue health if database is available
    health_metrics = {}
    total_pending = 0
    
    if queue is not None:
        try:
            health_metrics = queue.get_queue_health()
            total_pending = sum(m.get('pending', 0) for m in health_metrics.values())
        except Exception as e:
            logger.warning(f"Failed to get queue health: {e}")
    
    status = "healthy" if db_available else "degraded"
    
    return jsonify({
        "status": status,
        "database_available": db_available,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "queue_pending": total_pending,
        "queue_details": health_metrics
    })


@app.route("/webhook/teamwork", methods=["POST"])
def teamwork_webhook():
    """Handle Teamwork webhook events."""
    try:
        # Get raw payload for signature verification
        payload = request.get_data()
        signature = request.headers.get("X-Teamwork-Signature") or request.headers.get("X-Hook-Signature")
        
        # Verify signature if configured
        if not verify_teamwork_webhook(payload, signature):
            logger.warning("Invalid Teamwork webhook signature")
            return jsonify({"error": "Invalid signature"}), 401
        
        # Teamwork sends form data, not JSON
        data = request.form.to_dict()
        if not data:
            return jsonify({"error": "No data received"}), 400
        
        # Extract task ID (different field names for different webhook types)
        task_id = data.get("Task.ID") or data.get("ID")
        if not task_id:
            logger.warning("No task ID found in Teamwork webhook")
            return jsonify({"error": "No task ID found"}), 400
        
        # Get queue (with automatic connection retry)
        queue = db_manager.get_queue()
        
        if queue is None:
            # Database unavailable - log and return service unavailable
            logger.error("Database unavailable, cannot enqueue Teamwork webhook")
            return jsonify({
                "error": "Service temporarily unavailable",
                "message": "Database connection unavailable. Please retry later."
            }), 503
        
        # Create queue item with minimal payload (store only IDs)
        item = QueueItem.create(
            source="teamwork",
            event_type="task.updated",  # Teamwork form webhooks don't specify event type
            external_id=task_id,
            payload={}
        )
        
        # Enqueue
        if queue.enqueue(item):
            logger.info(
                f"Received Teamwork webhook for task {task_id}",
                extra={"source": "teamwork", "event_id": task_id}
            )
            return jsonify({"status": "accepted"}), 200
        else:
            logger.error("Failed to enqueue Teamwork webhook")
            return jsonify({"error": "Failed to queue event"}), 503
    
    except Exception as e:
        logger.error(f"Error handling Teamwork webhook: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/webhook/missive", methods=["POST"])
def missive_webhook():
    """Handle Missive webhook events."""
    try:
        # Get raw payload for signature verification
        payload = request.get_data()
        signature = request.headers.get("X-Missive-Signature") or request.headers.get("X-Hook-Signature")
        
        # Verify signature if configured
        if not verify_missive_webhook(payload, signature):
            logger.warning("Invalid Missive webhook signature")
            return jsonify({"error": "Invalid signature"}), 401
        
        # Parse JSON
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON payload"}), 400
        
        # Extract event information
        event_type = data.get("event", data.get("type", "unknown"))
        
        # Extract conversation/message ID
        external_id = _extract_missive_id(data)
        if not external_id:
            logger.warning("No ID found in Missive webhook")
            return jsonify({"error": "No ID found"}), 400
        
        # Get queue (with automatic connection retry)
        queue = db_manager.get_queue()
        
        if queue is None:
            # Database unavailable - log and return service unavailable
            logger.error("Database unavailable, cannot enqueue Missive webhook")
            return jsonify({
                "error": "Service temporarily unavailable",
                "message": "Database connection unavailable. Please retry later."
            }), 503
        
        # Create queue item with minimal payload (store only IDs)
        item = QueueItem.create(
            source="missive",
            event_type=event_type,
            external_id=external_id,
            payload={}
        )
        
        # Enqueue
        if queue.enqueue(item):
            logger.info(
                f"Received Missive webhook: {event_type}",
                extra={"source": "missive", "event_id": external_id}
            )
            return jsonify({"status": "accepted"}), 200
        else:
            logger.error("Failed to enqueue Missive webhook")
            return jsonify({"error": "Failed to queue event"}), 503
    
    except Exception as e:
        logger.error(f"Error handling Missive webhook: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


def _extract_missive_id(data: dict) -> str:
    """Extract conversation ID from Missive webhook payload (prefer conversation-level ID)."""
    # Prefer explicit conversation object
    if "conversation" in data and isinstance(data["conversation"], dict):
        cid = data["conversation"].get("id")
        if cid:
            return str(cid)
    # Look for top-level conversation id fields
    for key in ("conversation_id", "conversationId"):
        if key in data and data.get(key):
            return str(data[key])
    # Try to derive from message payload if present
    if "message" in data and isinstance(data["message"], dict):
        for key in ("conversation_id", "conversationId"):
            if key in data["message"] and data["message"].get(key):
                return str(data["message"][key])
    # Fallback: no conversation id found
    return ""


def _periodic_backfill():
    """Run backfill periodically to catch events missed by webhooks."""
    if _backfill_stop_event.is_set():
        return
    
    try:
        # Import here to avoid circular dependencies
        from src.startup import StartupManager
        
        logger.info("Running periodic backfill...")
        
        try:
            manager = StartupManager()
            manager.perform_backfill()
            manager.cleanup()
            logger.info("Periodic backfill completed")
        except Exception as e:
            logger.error(f"Error during periodic backfill: {e}", exc_info=True)
    
    except Exception as e:
        logger.error(f"Error initializing periodic backfill: {e}", exc_info=True)
    
    # Schedule next run (configurable interval)
    if not _backfill_stop_event.is_set():
        global _backfill_timer
        _backfill_timer = threading.Timer(float(settings.PERIODIC_BACKFILL_INTERVAL), _periodic_backfill)
        _backfill_timer.daemon = True
        _backfill_timer.start()


def start_periodic_backfill():
    """Start the periodic backfill timer."""
    global _backfill_timer
    interval = settings.PERIODIC_BACKFILL_INTERVAL
    logger.info(f"Starting periodic backfill (every {interval} seconds)...")
    _backfill_timer = threading.Timer(float(interval), _periodic_backfill)
    _backfill_timer.daemon = True
    _backfill_timer.start()


def stop_periodic_backfill():
    """Stop the periodic backfill timer."""
    global _backfill_timer
    logger.info("Stopping periodic backfill...")
    _backfill_stop_event.set()
    if _backfill_timer:
        _backfill_timer.cancel()


def _periodic_craft_poll():
    """Run Craft poll periodically (separate from backfill)."""
    if _craft_poll_stop_event.is_set():
        return
    
    try:
        from src.connectors.craft_client import CraftClient
        from src.db.postgres_impl import PostgresDatabase
        
        craft_client = CraftClient()
        
        if not craft_client.is_configured():
            logger.debug("Craft not configured, skipping periodic poll")
        else:
            logger.info("Running periodic Craft poll...")
            
            try:
                # Create database connection
                db = PostgresDatabase()
                
                # Fetch all documents with content
                documents = craft_client.get_all_documents_with_content(fetch_metadata=True)
                
                if documents:
                    # Upsert to database
                    if hasattr(db, 'upsert_craft_documents_batch'):
                        db.upsert_craft_documents_batch(documents)
                    else:
                        for doc in documents:
                            db.upsert_craft_document(doc)
                    
                    logger.info(f"Periodic Craft poll completed, synced {len(documents)} documents")
                else:
                    logger.info("Periodic Craft poll completed, no documents found")
                
                db.close()
            except Exception as e:
                logger.error(f"Error during periodic Craft poll: {e}", exc_info=True)
    
    except Exception as e:
        logger.error(f"Error initializing periodic Craft poll: {e}", exc_info=True)
    
    # Schedule next run
    if not _craft_poll_stop_event.is_set():
        global _craft_poll_timer
        _craft_poll_timer = threading.Timer(float(settings.CRAFT_POLL_INTERVAL), _periodic_craft_poll)
        _craft_poll_timer.daemon = True
        _craft_poll_timer.start()


def start_periodic_craft_poll():
    """Start the periodic Craft poll timer."""
    from src.connectors.craft_client import CraftClient
    
    craft_client = CraftClient()
    if not craft_client.is_configured():
        logger.info("Craft not configured, skipping periodic poll setup")
        return
    
    global _craft_poll_timer
    interval = settings.CRAFT_POLL_INTERVAL
    logger.info(f"Starting periodic Craft poll (every {interval} seconds)...")
    _craft_poll_timer = threading.Timer(float(interval), _periodic_craft_poll)
    _craft_poll_timer.daemon = True
    _craft_poll_timer.start()


def stop_periodic_craft_poll():
    """Stop the periodic Craft poll timer."""
    global _craft_poll_timer
    logger.info("Stopping periodic Craft poll...")
    _craft_poll_stop_event.set()
    if _craft_poll_timer:
        _craft_poll_timer.cancel()


def main():
    """Entry point for Flask app."""
    try:
        settings.validate_config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    
    # Check initial database connectivity (but don't fail if unavailable)
    if db_manager.is_available():
        logger.info("Initial database connection successful")
    else:
        logger.warning(
            "Database not available at startup. "
            "The application will retry connecting when processing requests."
        )
    
    # Start periodic backfill before running the app
    start_periodic_backfill()
    
    # Start periodic Craft poll (separate interval from backfill)
    start_periodic_craft_poll()
    
    try:
        logger.info(f"Starting Flask app on port {settings.APP_PORT}")
        app.run(host="0.0.0.0", port=settings.APP_PORT, debug=False)
    finally:
        stop_periodic_backfill()
        stop_periodic_craft_poll()
        db_manager.close()


if __name__ == "__main__":
    main()
