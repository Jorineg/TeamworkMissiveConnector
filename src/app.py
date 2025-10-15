"""Flask application for webhook endpoints."""
import sys
from flask import Flask, request, jsonify
from datetime import datetime, timezone

from src import settings
from src.logging_conf import logger
from src.queue.spool_queue import SpoolQueue
from src.queue.models import QueueItem
from src.http.security import verify_teamwork_webhook, verify_missive_webhook


# Create Flask app
app = Flask(__name__)

# Create queue instance (spool-based)
queue = SpoolQueue()


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "queue_size": queue.size()
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
        
        # Parse JSON
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON payload"}), 400
        
        # Extract event information
        event_type = data.get("event", data.get("type", "unknown"))
        
        # Extract task ID
        task_id = _extract_teamwork_task_id(data)
        if not task_id:
            logger.warning("No task ID found in Teamwork webhook")
            return jsonify({"error": "No task ID found"}), 400
        
        # Create queue item with minimal payload (store only IDs)
        item = QueueItem.create(
            source="teamwork",
            event_type=event_type,
            external_id=task_id,
            payload={}
        )
        
        # Enqueue
        queue.enqueue(item)
        
        logger.info(
            f"Received Teamwork webhook: {event_type}",
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


def _extract_teamwork_task_id(data: dict) -> str:
    """Extract task ID from Teamwork webhook payload."""
    if "task" in data:
        return str(data["task"].get("id", ""))
    if "taskId" in data:
        return str(data["taskId"])
    if "task_id" in data:
        return str(data["task_id"])
    if "id" in data:
        return str(data["id"])
    return ""


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


def main():
    """Entry point for Flask app."""
    try:
        settings.validate_config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    
    logger.info(f"Starting Flask app on port {settings.APP_PORT}")
    app.run(host="0.0.0.0", port=settings.APP_PORT, debug=False)


if __name__ == "__main__":
    main()

