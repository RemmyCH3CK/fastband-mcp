#!/usr/bin/env bash
#
# Secret Scanning Script for Fastband
#
# Usage:
#   ./scripts/check-secrets.sh              # Scan git history
#   ./scripts/check-secrets.sh --no-git     # Scan working directory only
#   ./scripts/check-secrets.sh --test       # Test detection with dummy secret
#
# Requirements:
#   - gitleaks (install via: brew install gitleaks)
#
# Exit codes:
#   0: No secrets found
#   1: Secrets detected
#   2: Script error (gitleaks not installed, etc.)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$ROOT_DIR/.gitleaks.toml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "============================================================"
echo "Secret Scanning (gitleaks)"
echo "============================================================"
echo ""

# Check if gitleaks is installed
if ! command -v gitleaks &> /dev/null; then
    echo -e "${RED}Error: gitleaks is not installed${NC}"
    echo ""
    echo "Install with:"
    echo "  brew install gitleaks    # macOS"
    echo "  # or see: https://github.com/gitleaks/gitleaks#installing"
    exit 2
fi

echo "gitleaks version: $(gitleaks version)"
echo "Config: $CONFIG_FILE"
echo ""

# Parse arguments
NO_GIT=false
TEST_MODE=false

for arg in "$@"; do
    case $arg in
        --no-git)
            NO_GIT=true
            ;;
        --test)
            TEST_MODE=true
            ;;
        *)
            echo "Unknown argument: $arg"
            echo "Usage: $0 [--no-git] [--test]"
            exit 2
            ;;
    esac
done

# Test mode: Create temp file with dummy secret and scan it
if [ "$TEST_MODE" = true ]; then
    echo -e "${YELLOW}Test Mode: Creating temporary file with dummy secret...${NC}"
    echo ""

    TEMP_DIR=$(mktemp -d)
    TEMP_FILE="$TEMP_DIR/test_secret.txt"

    # Write pattern that gitleaks will detect (generic-api-key rule)
    # Uses high-entropy string that triggers detection but isn't a real secret format
    cat > "$TEMP_FILE" << 'EOF'
# This file contains a fake secret for testing detection
# Pattern triggers generic-api-key rule (high entropy after keyword)
api_token = "xoxb_1234567890abcdefghijABCDEFGHIJ12345"
EOF

    echo "Created: $TEMP_FILE"
    echo "Contents:"
    cat "$TEMP_FILE"
    echo ""
    echo "Scanning temporary file..."
    echo ""

    # Scan the temp directory (not git, just files)
    if gitleaks detect --source="$TEMP_DIR" --config="$CONFIG_FILE" --no-git --verbose; then
        echo ""
        echo -e "${RED}UNEXPECTED: No secrets detected (detection may be broken)${NC}"
        rm -rf "$TEMP_DIR"
        exit 1
    else
        echo ""
        echo -e "${GREEN}SUCCESS: Dummy secret was correctly detected!${NC}"
        echo "gitleaks is working properly."
        rm -rf "$TEMP_DIR"
        exit 0
    fi
fi

# Normal scan mode
cd "$ROOT_DIR"

if [ "$NO_GIT" = true ]; then
    echo "Scanning working directory (no git history)..."
    echo ""

    if gitleaks detect --source="." --config="$CONFIG_FILE" --no-git --verbose; then
        echo ""
        echo -e "${GREEN}PASSED: No secrets detected in working directory${NC}"
        exit 0
    else
        echo ""
        echo -e "${RED}FAILED: Secrets detected!${NC}"
        exit 1
    fi
else
    echo "Scanning git history..."
    echo ""

    if gitleaks detect --source="." --config="$CONFIG_FILE" --verbose; then
        echo ""
        echo -e "${GREEN}PASSED: No secrets detected in git history${NC}"
        exit 0
    else
        echo ""
        echo -e "${RED}FAILED: Secrets detected in git history!${NC}"
        echo ""
        echo "If false positive, add to allowlist in .gitleaks.toml"
        exit 1
    fi
fi
