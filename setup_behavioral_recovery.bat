@echo off
REM Behavioral Recovery Setup Script (Windows)
REM Automated setup for Neuromorphic Behavioral Biometric Recovery System

echo ==========================================
echo  Behavioral Recovery Setup
echo  Phase 1 MVP Installation
echo ==========================================
echo.

REM Step 1: Backend Dependencies
echo [1/6] Installing backend dependencies...
cd password_manager
pip install -r requirements.txt

if %ERRORLEVEL% EQU 0 (
    echo [√] Backend dependencies installed
) else (
    echo [!] Warning: Some dependencies may have failed
)

REM Step 2: Database Migrations
echo.
echo [2/6] Running database migrations...
python manage.py makemigrations behavioral_recovery
python manage.py migrate behavioral_recovery

if %ERRORLEVEL% EQU 0 (
    echo [√] Database migrations completed
) else (
    echo [!] Warning: Migration failed
)

REM Step 3: Frontend Dependencies
echo.
echo [3/6] Installing frontend dependencies...
cd ..\frontend
call npm install

if %ERRORLEVEL% EQU 0 (
    echo [√] Frontend dependencies installed
) else (
    echo [!] Warning: npm install failed
)

REM Step 4: Verify TensorFlow.js
echo.
echo [4/6] Verifying TensorFlow.js installation...
call npm list @tensorflow/tfjs >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [√] TensorFlow.js installed
) else (
    echo [!] TensorFlow.js not found. Installing...
    call npm install @tensorflow/tfjs @tensorflow/tfjs-backend-webgl
)

REM Step 5: Run Tests
echo.
echo [5/6] Running tests...
cd ..\password_manager
python manage.py test tests.behavioral_recovery --verbosity=1

if %ERRORLEVEL% EQU 0 (
    echo [√] All tests passed
) else (
    echo [!] Some tests failed
)

REM Step 6: Verification
echo.
echo [6/6] Verifying installation...
python manage.py shell -c "import behavioral_recovery; print('[√] Behavioral recovery app found')" 2>nul

REM Final Summary
echo.
echo ==========================================
echo  SETUP COMPLETE!
echo ==========================================
echo.
echo Next steps:
echo   1. Start backend:  cd password_manager ^&^& python manage.py runserver
echo   2. Start frontend: cd frontend ^&^& npm run dev
echo   3. Visit: http://localhost:3000/password-recovery
echo   4. Verify: 'Behavioral Recovery' tab visible
echo.
echo Documentation:
echo   - Quick Start: BEHAVIORAL_RECOVERY_QUICK_START.md
echo   - Architecture: BEHAVIORAL_RECOVERY_ARCHITECTURE.md
echo   - API Docs: BEHAVIORAL_RECOVERY_API.md
echo.
echo Happy recovering! 🧬🔐
echo.
pause

