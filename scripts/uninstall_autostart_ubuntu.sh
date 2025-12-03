#!/bin/bash

# Teamwork & Missive Connector - Ubuntu Autostart Uninstallation
# This script removes both services from autostart

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Teamwork & Missive Connector - Remove from Autostart${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

CONNECTOR_SERVICE="teamwork-missive-connector"
WORKER_SERVICE="teamwork-missive-worker"
SERVICE_DIR="$HOME/.config/systemd/user"

# Stop and disable connector service
if [ -f "$SERVICE_DIR/$CONNECTOR_SERVICE.service" ]; then
    echo -e "${YELLOW}Stopping and disabling connector service...${NC}"
    systemctl --user stop "$CONNECTOR_SERVICE" 2>/dev/null || true
    systemctl --user disable "$CONNECTOR_SERVICE" 2>/dev/null || true
    rm "$SERVICE_DIR/$CONNECTOR_SERVICE.service"
    echo -e "${GREEN}✓ Connector service removed${NC}"
else
    echo -e "${YELLOW}Connector service not found${NC}"
fi

# Stop and disable worker service
if [ -f "$SERVICE_DIR/$WORKER_SERVICE.service" ]; then
    echo -e "${YELLOW}Stopping and disabling worker service...${NC}"
    systemctl --user stop "$WORKER_SERVICE" 2>/dev/null || true
    systemctl --user disable "$WORKER_SERVICE" 2>/dev/null || true
    rm "$SERVICE_DIR/$WORKER_SERVICE.service"
    echo -e "${GREEN}✓ Worker service removed${NC}"
else
    echo -e "${YELLOW}Worker service not found${NC}"
fi

# Reload systemd
systemctl --user daemon-reload

echo ""
echo -e "${GREEN}✅ Autostart successfully removed${NC}"
echo ""
echo "The connector will no longer start automatically at boot."
echo "You can still run it manually with: ./scripts/run_worker_only.sh"
echo ""

