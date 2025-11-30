#!/bin/bash
# ML Training Setup Script for Linux/Mac

echo "======================================================"
echo "ML Dark Web Monitoring - Training Setup"
echo "======================================================"
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "✓ Python $python_version"
echo ""

# Install dependencies
echo "Installing Python dependencies..."
pip install -r password_manager/ml_dark_web/requirements_ml_darkweb.txt
if [ $? -eq 0 ]; then
    echo "✓ Dependencies installed"
else
    echo "✗ Error installing dependencies"
    exit 1
fi
echo ""

# Install spaCy model
echo "Installing spaCy model..."
python -m spacy download en_core_web_sm
if [ $? -eq 0 ]; then
    echo "✓ spaCy model installed"
else
    echo "✗ Error installing spaCy model"
    exit 1
fi
echo ""

# Create directories
echo "Creating model directories..."
mkdir -p password_manager/ml_models/dark_web/breach_classifier
mkdir -p password_manager/ml_models/dark_web/credential_matcher
mkdir -p password_manager/ml_models/dark_web/pattern_detector
echo "✓ Directories created"
echo ""

# Run training
echo "======================================================"
echo "Starting ML Model Training"
echo "======================================================"
echo ""
echo "This will take approximately 15-30 minutes..."
echo ""

cd password_manager
python ml_dark_web/training/train_all_models.py --models all --samples 10000 --epochs 10

if [ $? -eq 0 ]; then
    echo ""
    echo "======================================================"
    echo "✅ ML TRAINING COMPLETE!"
    echo "======================================================"
    echo ""
    echo "Models trained and saved to:"
    echo "  - ml_models/dark_web/breach_classifier/"
    echo ""
    echo "Next steps:"
    echo "  1. python manage.py runserver"
    echo "  2. celery -A password_manager worker -l info"
else
    echo ""
    echo "======================================================"
    echo "❌ TRAINING FAILED"
    echo "======================================================"
    echo "Check the logs for errors"
    exit 1
fi

