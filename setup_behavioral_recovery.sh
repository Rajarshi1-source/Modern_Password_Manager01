#!/bin/bash

# Behavioral Recovery Setup Script
# Automated setup for Neuromorphic Behavioral Biometric Recovery System

echo "=========================================="
echo " Behavioral Recovery Setup"
echo " Phase 1 MVP Installation"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Backend Dependencies
echo -e "${BLUE}[1/6] Installing backend dependencies...${NC}"
cd password_manager
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Backend dependencies installed${NC}"
else
    echo -e "${YELLOW}⚠ Warning: Some dependencies may have failed. Check output above.${NC}"
fi

# Step 2: Database Migrations
echo -e "\n${BLUE}[2/6] Running database migrations...${NC}"
python manage.py makemigrations behavioral_recovery
python manage.py migrate behavioral_recovery

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Database migrations completed${NC}"
else
    echo -e "${YELLOW}⚠ Warning: Migration failed. Check Django configuration.${NC}"
fi

# Step 3: Frontend Dependencies
echo -e "\n${BLUE}[3/6] Installing frontend dependencies...${NC}"
cd ../frontend
npm install

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Frontend dependencies installed${NC}"
else
    echo -e "${YELLOW}⚠ Warning: npm install failed. Check npm configuration.${NC}"
fi

# Step 4: Verify TensorFlow.js
echo -e "\n${BLUE}[4/6] Verifying TensorFlow.js installation...${NC}"
if npm list @tensorflow/tfjs > /dev/null 2>&1; then
    echo -e "${GREEN}✓ TensorFlow.js installed${NC}"
else
    echo -e "${YELLOW}⚠ TensorFlow.js not found. Installing...${NC}"
    npm install @tensorflow/tfjs @tensorflow/tfjs-backend-webgl
fi

# Step 5: Run Tests
echo -e "\n${BLUE}[5/6] Running tests...${NC}"
cd ../password_manager
python manage.py test tests.behavioral_recovery --verbosity=1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed${NC}"
else
    echo -e "${YELLOW}⚠ Some tests failed. Review test output above.${NC}"
fi

# Step 6: Verification
echo -e "\n${BLUE}[6/6] Verifying installation...${NC}"

# Check if behavioral_recovery app is installed
python manage.py shell -c "import behavioral_recovery; print('✓ Behavioral recovery app found')" 2>/dev/null

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Behavioral recovery app installed${NC}"
else
    echo -e "${YELLOW}⚠ Behavioral recovery app not found${NC}"
fi

# Final Summary
echo ""
echo "=========================================="
echo -e "${GREEN} SETUP COMPLETE!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Start backend:  cd password_manager && python manage.py runserver"
echo "  2. Start frontend: cd frontend && npm run dev"
echo "  3. Visit: http://localhost:3000/password-recovery"
echo "  4. Verify: 'Behavioral Recovery' tab visible"
echo ""
echo "Documentation:"
echo "  • Quick Start: BEHAVIORAL_RECOVERY_QUICK_START.md"
echo "  • Architecture: BEHAVIORAL_RECOVERY_ARCHITECTURE.md"
echo "  • API Docs: BEHAVIORAL_RECOVERY_API.md"
echo ""
echo "Happy recovering! 🧬🔐"

