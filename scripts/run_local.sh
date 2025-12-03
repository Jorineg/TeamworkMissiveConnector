#!/bin/bash

# Teamwork & Missive Connector - Local Development Runner
# This script starts the Flask app and worker in the background

set -e

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$PROJECT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Teamwork & Missive Connector...${NC}"

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please copy .env.example to .env and configure it"
    exit 1
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Check if required packages are installed
if ! python3 -c "import flask" 2>/dev/null; then
    echo -e "${RED}Error: Required packages not installed${NC}"
    echo "Please run: pip install -r requirements.txt"
    exit 1
fi

# Create log directory
mkdir -p logs
mkdir -p data/queue
mkdir -p data/checkpoints

# Start ngrok and perform backfill (runs in background, keeps ngrok alive)
echo -e "${YELLOW}Starting ngrok tunnel and performing backfill...${NC}"
python3 -m src.startup &
STARTUP_PID=$!
echo "Startup process PID: $STARTUP_PID"

# Wait a bit for ngrok to initialize
sleep 3

# Start Flask app
echo -e "${YELLOW}Starting Flask webhook server...${NC}"
python3 -m src.app &
FLASK_PID=$!
echo "Flask app PID: $FLASK_PID"

# Start worker
echo -e "${YELLOW}Starting worker dispatcher...${NC}"
python3 -m src.workers.dispatcher &
WORKER_PID=$!
echo "Worker dispatcher PID: $WORKER_PID"

echo ""
echo -e "${GREEN}✓ All services started${NC}"
echo ""
echo "Process IDs:"
echo "  Startup/ngrok: $STARTUP_PID"
echo "  Flask app:     $FLASK_PID"
echo "  Worker:        $WORKER_PID"
echo ""
echo "Logs are being written to: logs/app.log"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Stopping services...${NC}"
    kill $STARTUP_PID $FLASK_PID $WORKER_PID 2>/dev/null || true
    wait $STARTUP_PID $FLASK_PID $WORKER_PID 2>/dev/null || true
    echo -e "${GREEN}All services stopped${NC}"
    exit 0
}

# Trap SIGINT (Ctrl+C) and SIGTERM
trap cleanup SIGINT SIGTERM

# Wait for all background processes
wait

