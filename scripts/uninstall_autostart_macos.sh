#!/bin/bash

# Teamwork & Missive Connector - macOS Autostart Uninstallation
# This script removes the connector from autostart

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Teamwork & Missive Connector - Remove from Autostart${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

PLIST_FILENAME="com.teamworkmissive.connector.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$LAUNCH_AGENTS_DIR/$PLIST_FILENAME"

# Check if the plist file exists
if [ ! -f "$PLIST_PATH" ]; then
    echo -e "${YELLOW}LaunchAgent is not installed (plist file not found)${NC}"
    exit 0
fi

# Unload the LaunchAgent if it's loaded
if launchctl list | grep -q "com.teamworkmissive.connector"; then
    echo -e "${YELLOW}Stopping service...${NC}"
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    echo -e "${GREEN}✓ Service stopped${NC}"
else
    echo -e "${YELLOW}Service is not running${NC}"
fi

# Remove the plist file
echo -e "${YELLOW}Removing LaunchAgent configuration...${NC}"
rm "$PLIST_PATH"
echo -e "${GREEN}✓ Configuration removed${NC}"

echo ""
echo -e "${GREEN}✅ Autostart successfully removed${NC}"
echo ""
echo "The connector will no longer start automatically at login."
echo "You can still run it manually with: ./scripts/run_local.sh"
echo ""

