#!/bin/bash
# Installation script for Hybrid Cryptography Upgrade
# Password Manager - Hybrid Crypto Implementation

set -e  # Exit on error

echo "========================================="
echo " Hybrid Cryptography Upgrade Installer  "
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -d "frontend" ] || [ ! -d "password_manager" ]; then
    echo -e "${RED}Error: Please run this script from the project root directory${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 1: Installing Frontend Dependencies${NC}"
echo "Installing @noble/curves and @noble/hashes..."
cd frontend

# Check if package.json exists
if [ ! -f "package.json" ]; then
    echo -e "${RED}Error: package.json not found in frontend directory${NC}"
    exit 1
fi

# Install dependencies
npm install

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Frontend dependencies installed successfully${NC}"
else
    echo -e "${RED}✗ Failed to install frontend dependencies${NC}"
    exit 1
fi

# Verify installation
echo ""
echo "Verifying installation..."
npm list @noble/curves @noble/hashes --depth=0 || true

echo ""
echo -e "${YELLOW}Step 2: Applying Backend Migrations${NC}"
cd ../password_manager

# Check if manage.py exists
if [ ! -f "manage.py" ]; then
    echo -e "${RED}Error: manage.py not found in password_manager directory${NC}"
    exit 1
fi

# Activate virtual environment if it exists
if [ -d "../canny/bin" ]; then
    echo "Activating virtual environment..."
    source ../canny/bin/activate
elif [ -d "../canny/Scripts" ]; then
    echo "Activating virtual environment (Windows)..."
    source ../canny/Scripts/activate
fi

# Apply migration
echo "Applying crypto versioning migration..."
python manage.py migrate vault 0002_add_crypto_versioning

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Database migrations applied successfully${NC}"
else
    echo -e "${RED}✗ Failed to apply migrations${NC}"
    exit 1
fi

# Verify migration
echo ""
echo "Verifying migrations..."
python manage.py showmigrations vault

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}   Installation Complete! ✓            ${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Start the backend:"
echo "   cd password_manager"
echo "   python manage.py runserver"
echo ""
echo "2. Start the frontend (in another terminal):"
echo "   cd frontend"
echo "   npm run dev"
echo ""
echo "3. Test the upgrade:"
echo "   - Login with an existing account"
echo "   - Check console for 'Deriving key with Argon2id v2'"
echo "   - Create a new vault item"
echo ""
echo "For detailed documentation, see:"
echo "- HYBRID_CRYPTO_QUICK_START.md"
echo "- HYBRID_CRYPTO_IMPLEMENTATION_SUMMARY.md"
echo ""

