@echo off
REM Installation script for Hybrid Cryptography Upgrade (Windows)
REM Password Manager - Hybrid Crypto Implementation

echo =========================================
echo  Hybrid Cryptography Upgrade Installer
echo =========================================
echo.

REM Check if we're in the right directory
if not exist "frontend" (
    echo Error: frontend directory not found
    echo Please run this script from the project root directory
    pause
    exit /b 1
)

if not exist "password_manager" (
    echo Error: password_manager directory not found
    echo Please run this script from the project root directory
    pause
    exit /b 1
)

echo Step 1: Installing Frontend Dependencies
echo Installing @noble/curves and @noble/hashes...
cd frontend

REM Check if package.json exists
if not exist "package.json" (
    echo Error: package.json not found in frontend directory
    pause
    exit /b 1
)

REM Install dependencies
call npm install

if %errorlevel% neq 0 (
    echo Failed to install frontend dependencies
    pause
    exit /b 1
)

echo [OK] Frontend dependencies installed successfully
echo.

REM Verify installation
echo Verifying installation...
call npm list @noble/curves @noble/hashes --depth=0

echo.
echo Step 2: Applying Backend Migrations
cd ..\password_manager

REM Check if manage.py exists
if not exist "manage.py" (
    echo Error: manage.py not found in password_manager directory
    pause
    exit /b 1
)

REM Activate virtual environment if it exists
if exist "..\canny\Scripts\activate.bat" (
    echo Activating virtual environment...
    call ..\canny\Scripts\activate.bat
)

REM Apply migration
echo Applying crypto versioning migration...
python manage.py migrate vault 0002_add_crypto_versioning

if %errorlevel% neq 0 (
    echo Failed to apply migrations
    pause
    exit /b 1
)

echo [OK] Database migrations applied successfully
echo.

REM Verify migration
echo Verifying migrations...
python manage.py showmigrations vault

echo.
echo =========================================
echo    Installation Complete!
echo =========================================
echo.
echo Next steps:
echo 1. Start the backend:
echo    cd password_manager
echo    python manage.py runserver
echo.
echo 2. Start the frontend (in another terminal):
echo    cd frontend
echo    npm run dev
echo.
echo 3. Test the upgrade:
echo    - Login with an existing account
echo    - Check console for "Deriving key with Argon2id v2"
echo    - Create a new vault item
echo.
echo For detailed documentation, see:
echo - HYBRID_CRYPTO_QUICK_START.md
echo - HYBRID_CRYPTO_IMPLEMENTATION_SUMMARY.md
echo.
pause

