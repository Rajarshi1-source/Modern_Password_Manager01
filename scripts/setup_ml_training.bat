@echo off
REM ML Training Setup Script for Windows

echo ======================================================
echo ML Dark Web Monitoring - Training Setup
echo ======================================================
echo.

REM Check Python version
echo Checking Python version...
python --version
if errorlevel 1 (
    echo X Python not found
    exit /b 1
)
echo.

REM Install dependencies
echo Installing Python dependencies...
pip install -r password_manager\ml_dark_web\requirements_ml_darkweb.txt
if errorlevel 1 (
    echo X Error installing dependencies
    exit /b 1
)
echo V Dependencies installed
echo.

REM Install spaCy model
echo Installing spaCy model...
python -m spacy download en_core_web_sm
if errorlevel 1 (
    echo X Error installing spaCy model
    exit /b 1
)
echo V spaCy model installed
echo.

REM Create directories
echo Creating model directories...
if not exist "password_manager\ml_models\dark_web\breach_classifier" mkdir password_manager\ml_models\dark_web\breach_classifier
if not exist "password_manager\ml_models\dark_web\credential_matcher" mkdir password_manager\ml_models\dark_web\credential_matcher
if not exist "password_manager\ml_models\dark_web\pattern_detector" mkdir password_manager\ml_models\dark_web\pattern_detector
echo V Directories created
echo.

REM Run training
echo ======================================================
echo Starting ML Model Training
echo ======================================================
echo.
echo This will take approximately 15-30 minutes...
echo.

cd password_manager
python ml_dark_web\training\train_all_models.py --models all --samples 10000 --epochs 10

if errorlevel 1 (
    echo.
    echo ======================================================
    echo X TRAINING FAILED
    echo ======================================================
    echo Check the logs for errors
    exit /b 1
) else (
    echo.
    echo ======================================================
    echo V ML TRAINING COMPLETE!
    echo ======================================================
    echo.
    echo Models trained and saved to:
    echo   - ml_models\dark_web\breach_classifier\
    echo.
    echo Next steps:
    echo   1. python manage.py runserver
    echo   2. celery -A password_manager worker -l info
)

