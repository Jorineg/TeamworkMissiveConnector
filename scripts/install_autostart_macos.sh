#!/bin/bash

# Teamwork & Missive Connector - macOS Autostart Installation
# This script installs the connector as a LaunchAgent that starts automatically at login

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Teamwork & Missive Connector - macOS Autostart Setup${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Get script directory and project directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Get current username
USERNAME=$(whoami)

# LaunchAgent paths
PLIST_TEMPLATE="$SCRIPT_DIR/com.teamworkmissive.connector.plist"
PLIST_FILENAME="com.teamworkmissive.connector.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_DEST="$LAUNCH_AGENTS_DIR/$PLIST_FILENAME"

echo -e "${YELLOW}Project directory:${NC} $PROJECT_DIR"
echo -e "${YELLOW}Username:${NC} $USERNAME"
echo ""

# Check if .env exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please configure your .env file before setting up autostart"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo -e "${YELLOW}Warning: Virtual environment not found${NC}"
    echo "Creating virtual environment..."
    cd "$PROJECT_DIR"
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Create LaunchAgents directory if it doesn't exist
mkdir -p "$LAUNCH_AGENTS_DIR"

# Create a temporary plist file with the correct paths
echo -e "${YELLOW}Creating LaunchAgent configuration...${NC}"
TEMP_PLIST=$(mktemp)

sed -e "s|/Users/YOUR_USERNAME/TeamworkMissiveConnector|$PROJECT_DIR|g" \
    "$PLIST_TEMPLATE" > "$TEMP_PLIST"

# Copy the plist file to LaunchAgents
cp "$TEMP_PLIST" "$PLIST_DEST"
rm "$TEMP_PLIST"

echo -e "${GREEN}✓ Configuration created at: $PLIST_DEST${NC}"

# Unload existing agent if it's running
if launchctl list | grep -q "com.teamworkmissive.connector"; then
    echo -e "${YELLOW}Stopping existing service...${NC}"
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    sleep 1
fi

# Load the LaunchAgent
echo -e "${YELLOW}Loading LaunchAgent...${NC}"
launchctl load "$PLIST_DEST"

# Verify it's loaded
sleep 2
if launchctl list | grep -q "com.teamworkmissive.connector"; then
    echo ""
    echo -e "${GREEN}✅ SUCCESS! The connector is now installed and running.${NC}"
    echo ""
    echo -e "${GREEN}It will automatically start:${NC}"
    echo "  • When you log in"
    echo "  • If it crashes (automatic restart)"
    echo ""
    echo -e "${YELLOW}Useful commands:${NC}"
    echo "  • Check status:   launchctl list | grep teamworkmissive"
    echo "  • Stop service:   launchctl unload ~/Library/LaunchAgents/$PLIST_FILENAME"
    echo "  • Start service:  launchctl load ~/Library/LaunchAgents/$PLIST_FILENAME"
    echo "  • Restart:        launchctl kickstart -k gui/\$(id -u)/com.teamworkmissive.connector"
    echo "  • View logs:      tail -f $PROJECT_DIR/logs/launchd.*.log"
    echo "  • View app logs:  tail -f $PROJECT_DIR/logs/app.log"
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
else
    echo ""
    echo -e "${RED}❌ ERROR: LaunchAgent failed to load${NC}"
    echo "Check the logs for errors:"
    echo "  tail -f $PROJECT_DIR/logs/launchd.err.log"
    exit 1
fi



