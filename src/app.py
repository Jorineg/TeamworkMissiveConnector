"""Flask application with integrated queue worker."""
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
from src.workers.dispatcher import WorkerDispatcher


# Create Flask app
app = Flask(__name__)

# Worker thread
_worker_thread: Optional[threading.Thread] = None
_worker_dispatcher: Optional[WorkerDispatcher] = None


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


def start_worker():
    """Start the queue worker in a background thread."""
    global _worker_thread, _worker_dispatcher
    
    def run_worker():
        global _worker_dispatcher
        try:
            # Don't register signals in thread (only works in main thread)
            _worker_dispatcher = WorkerDispatcher(register_signals=False)
            _worker_dispatcher.run()
        except Exception as e:
            logger.error(f"Worker dispatcher crashed: {e}", exc_info=True)
    
    logger.info("Starting queue worker...")
    _worker_thread = threading.Thread(target=run_worker, daemon=True, name="QueueWorker")
    _worker_thread.start()


def stop_worker():
    """Stop the queue worker."""
    global _worker_dispatcher
    logger.info("Stopping queue worker...")
    if _worker_dispatcher:
        _worker_dispatcher.running = False


def main():
    """Entry point - starts Flask, worker, and backfill."""
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
    
    # Start queue worker (processes queue items)
    start_worker()
    
    # Start periodic backfill (fetches from APIs)
    start_periodic_backfill()
    
    try:
        logger.info(f"Starting Flask app on port {settings.APP_PORT}")
        app.run(host="0.0.0.0", port=settings.APP_PORT, debug=False)
    finally:
        stop_worker()
        stop_periodic_backfill()
        db_manager.close()


if __name__ == "__main__":
    main()
