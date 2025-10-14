#!/bin/bash

# Run only the worker (useful for production without ngrok)

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$PROJECT_DIR"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Start Flask app
python -m src.app &
FLASK_PID=$!

# Start worker
python -m src.workers.dispatcher &
WORKER_PID=$!

echo "Flask app PID: $FLASK_PID"
echo "Worker PID: $WORKER_PID"

# Cleanup function
cleanup() {
    echo "Stopping services..."
    kill $FLASK_PID $WORKER_PID 2>/dev/null || true
    wait $FLASK_PID $WORKER_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

wait

