#!/bin/bash

# Teamwork & Missive Connector - Ubuntu Autostart Installation (systemd)
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
SERVICE_NAME="teamwork-missive-connector"

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

# Create the systemd service file
cat > "$HOME/.config/systemd/user/$SERVICE_NAME.service" << EOF
[Unit]
Description=Teamwork & Missive Connector
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python -m src.app
Restart=always
RestartSec=10
StandardOutput=append:$PROJECT_DIR/logs/systemd.log
StandardError=append:$PROJECT_DIR/logs/systemd.err.log

[Install]
WantedBy=default.target
EOF

echo -e "${GREEN}✓ Service file created${NC}"

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"

# Reload systemd, enable and start the service
systemctl --user daemon-reload
systemctl --user enable "$SERVICE_NAME"
systemctl --user restart "$SERVICE_NAME"

# Enable lingering (allows service to run without active login session)
loginctl enable-linger "$USER" 2>/dev/null || true

sleep 2
if systemctl --user is-active --quiet "$SERVICE_NAME"; then
    echo ""
    echo -e "${GREEN}✅ SUCCESS! The connector is now installed and running.${NC}"
    echo ""
    echo -e "${YELLOW}Useful commands:${NC}"
    echo "  • Check status:   systemctl --user status $SERVICE_NAME"
    echo "  • View logs:      journalctl --user -u $SERVICE_NAME -f"
    echo "  • Stop service:   systemctl --user stop $SERVICE_NAME"
    echo "  • Start service:  systemctl --user start $SERVICE_NAME"
    echo "  • Disable:        systemctl --user disable $SERVICE_NAME"
    echo ""
else
    echo -e "${RED}❌ ERROR: Service failed to start${NC}"
    echo "Check logs: journalctl --user -u $SERVICE_NAME"
    exit 1
fi

