#!/bin/bash

# Teamwork & Missive Connector - Ubuntu Autostart Installation (systemd)
# Creates TWO services:
#   1. teamwork-missive-connector.service - Flask app (webhooks + periodic backfill)
#   2. teamwork-missive-worker.service - Worker dispatcher (processes the queue)

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Teamwork & Missive Connector - Ubuntu Autostart Setup${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
CONNECTOR_SERVICE="teamwork-missive-connector"
WORKER_SERVICE="teamwork-missive-worker"

echo -e "${YELLOW}Project directory:${NC} $PROJECT_DIR"

# Check if .env exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    exit 1
fi

# Create virtual environment if needed
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv "$PROJECT_DIR/venv"
    "$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Create systemd user service directory
mkdir -p "$HOME/.config/systemd/user"

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"

# ============================================================
# Service 1: Flask App (webhooks + periodic backfill)
# ============================================================
echo -e "${YELLOW}Creating connector service (Flask app)...${NC}"

cat > "$HOME/.config/systemd/user/$CONNECTOR_SERVICE.service" << EOF
[Unit]
Description=Teamwork & Missive Connector - Flask App
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python -m src.app
Restart=always
RestartSec=10
StandardOutput=append:$PROJECT_DIR/logs/connector.log
StandardError=append:$PROJECT_DIR/logs/connector.err.log

[Install]
WantedBy=default.target
EOF

echo -e "${GREEN}✓ Connector service file created${NC}"

# ============================================================
# Service 2: Worker Dispatcher (processes the queue)
# ============================================================
echo -e "${YELLOW}Creating worker service (queue processor)...${NC}"

cat > "$HOME/.config/systemd/user/$WORKER_SERVICE.service" << EOF
[Unit]
Description=Teamwork & Missive Connector - Worker Dispatcher
After=network-online.target $CONNECTOR_SERVICE.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python -m src.workers.dispatcher
Restart=always
RestartSec=10
StandardOutput=append:$PROJECT_DIR/logs/worker.log
StandardError=append:$PROJECT_DIR/logs/worker.err.log

[Install]
WantedBy=default.target
EOF

echo -e "${GREEN}✓ Worker service file created${NC}"

# Reload systemd
systemctl --user daemon-reload

# Enable and start both services
echo -e "${YELLOW}Enabling and starting services...${NC}"

systemctl --user enable "$CONNECTOR_SERVICE"
systemctl --user enable "$WORKER_SERVICE"
systemctl --user restart "$CONNECTOR_SERVICE"
systemctl --user restart "$WORKER_SERVICE"

# Enable lingering (allows service to run without active login session)
loginctl enable-linger "$USER" 2>/dev/null || true

sleep 2

# Check status of both services
CONNECTOR_OK=false
WORKER_OK=false

if systemctl --user is-active --quiet "$CONNECTOR_SERVICE"; then
    CONNECTOR_OK=true
    echo -e "${GREEN}✓ Connector service is running${NC}"
else
    echo -e "${RED}✗ Connector service failed to start${NC}"
fi

if systemctl --user is-active --quiet "$WORKER_SERVICE"; then
    WORKER_OK=true
    echo -e "${GREEN}✓ Worker service is running${NC}"
else
    echo -e "${RED}✗ Worker service failed to start${NC}"
fi

echo ""

if $CONNECTOR_OK && $WORKER_OK; then
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✅ SUCCESS! Both services are now installed and running.${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${YELLOW}Services:${NC}"
    echo "  • $CONNECTOR_SERVICE - Flask app (webhooks + periodic backfill)"
    echo "  • $WORKER_SERVICE - Worker dispatcher (processes the queue)"
    echo ""
    echo -e "${YELLOW}Useful commands:${NC}"
    echo ""
    echo "  Check status:"
    echo "    systemctl --user status $CONNECTOR_SERVICE"
    echo "    systemctl --user status $WORKER_SERVICE"
    echo ""
    echo "  View logs:"
    echo "    journalctl --user -u $CONNECTOR_SERVICE -f"
    echo "    journalctl --user -u $WORKER_SERVICE -f"
    echo "    # Or view log files directly:"
    echo "    tail -f $PROJECT_DIR/logs/connector.log"
    echo "    tail -f $PROJECT_DIR/logs/worker.log"
    echo ""
    echo "  Stop services:"
    echo "    systemctl --user stop $CONNECTOR_SERVICE $WORKER_SERVICE"
    echo ""
    echo "  Start services:"
    echo "    systemctl --user start $CONNECTOR_SERVICE $WORKER_SERVICE"
    echo ""
    echo "  Restart services:"
    echo "    systemctl --user restart $CONNECTOR_SERVICE $WORKER_SERVICE"
    echo ""
    echo "  Disable autostart:"
    echo "    systemctl --user disable $CONNECTOR_SERVICE $WORKER_SERVICE"
    echo ""
else
    echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}  ❌ ERROR: One or more services failed to start${NC}"
    echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Check logs:"
    echo "  journalctl --user -u $CONNECTOR_SERVICE"
    echo "  journalctl --user -u $WORKER_SERVICE"
    exit 1
fi
