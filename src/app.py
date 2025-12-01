"""Flask application for webhook endpoints."""
import sys
import threading
from flask import Flask, request, jsonify
from datetime import datetime, timezone

from src import settings
from src.logging_conf import logger
from src.queue.postgres_queue import PostgresQueue
from src.queue.models import QueueItem
from src.http.security import verify_teamwork_webhook, verify_missive_webhook
from src.db.postgres_impl import PostgresDatabase


# Create Flask app
app = Flask(__name__)

# Create database and queue instance (PostgreSQL-backed)
db = PostgresDatabase()
queue = PostgresQueue(db.conn)

# Periodic backfill timer
_backfill_timer = None
_backfill_stop_event = threading.Event()


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    health_metrics = queue.get_queue_health()
    total_pending = sum(m.get('pending', 0) for m in health_metrics.values())
    
    return jsonify({
        "status": "healthy",
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
        
        # Create queue item with minimal payload (store only IDs)
        item = QueueItem.create(
            source="teamwork",
            event_type="task.updated",  # Teamwork form webhooks don't specify event type
            external_id=task_id,
            payload={}
        )
        
        # Enqueue
        queue.enqueue(item)
        
        logger.info(
            f"Received Teamwork webhook for task {task_id}",
            extra={"source": "teamwork", "event_id": task_id}
        )
        
        return jsonify({"status": "accepted"}), 200
    
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
        
        # Create queue item with minimal payload (store only IDs)
        item = QueueItem.create(
            source="missive",
            event_type=event_type,
            external_id=external_id,
            payload={}
        )
        
        # Enqueue
        queue.enqueue(item)
        
        logger.info(
            f"Received Missive webhook: {event_type}",
            extra={"source": "missive", "event_id": external_id}
        )
        
        return jsonify({"status": "accepted"}), 200
    
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
        manager = StartupManager()
        manager.perform_backfill()
        manager.cleanup()
        logger.info("Periodic backfill completed")
    
    except Exception as e:
        logger.error(f"Error during periodic backfill: {e}", exc_info=True)
    
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


def main():
    """Entry point for Flask app."""
    try:
        settings.validate_config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    
    # Start periodic backfill before running the app
    start_periodic_backfill()
    
    try:
        logger.info(f"Starting Flask app on port {settings.APP_PORT}")
        app.run(host="0.0.0.0", port=settings.APP_PORT, debug=False)
    finally:
        stop_periodic_backfill()


if __name__ == "__main__":
    main()

