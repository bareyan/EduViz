@echo off
echo ========================================
echo    EduViz Hackathon Setup Script
echo ========================================
echo.

echo [1/4] Checking Docker installation...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not installed or not running!
    echo Please install Docker Desktop from: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)
echo ✅ Docker found!

echo.
echo [2/4] Checking docker-compose...
docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: docker-compose is not available!
    pause
    exit /b 1
)
echo ✅ docker-compose found!

echo.
echo [3/4] Setting up environment file...
if not exist "backend\.env" (
    if exist "backend\.env.example" (
        copy "backend\.env.example" "backend\.env"
        echo ✅ Created backend/.env from template
        echo.
        echo ⚠️  IMPORTANT: Please edit backend/.env and add your GEMINI_API_KEY!
        echo    Get one from: https://makersuite.google.com/app/apikey
        echo.
        notepad backend\.env
    ) else (
        echo ERROR: backend/.env.example not found!
        pause
        exit /b 1
    )
) else (
    echo ✅ backend/.env already exists
)

echo.
echo [4/4] Starting EduViz...
echo.
echo ========================================
echo    Starting containers...
echo    Frontend: http://localhost:3000
echo    Backend:  http://localhost:8000/docs
echo ========================================
echo.
echo Press Ctrl+C to stop the application
echo.

docker-compose up --build

echo.
echo EduViz stopped. Thanks for testing! 🎉
pause