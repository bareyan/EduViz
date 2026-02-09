#!/bin/bash

echo "========================================"
echo "    EduViz Hackathon Setup Script"
echo "========================================"
echo

echo "[1/4] Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed!"
    echo "Please install Docker from: https://docs.docker.com/get-docker/"
    exit 1
fi
echo "✅ Docker found!"

echo
echo "[2/4] Checking docker-compose..."
if ! command -v docker-compose &> /dev/null; then
    echo "ERROR: docker-compose is not available!"
    echo "Please install docker-compose"
    exit 1
fi
echo "✅ docker-compose found!"

echo
echo "[3/4] Setting up environment file..."
if [ ! -f "backend/.env" ]; then
    if [ -f "backend/.env.example" ]; then
        cp "backend/.env.example" "backend/.env"
        echo "✅ Created backend/.env from template"
        echo
        echo "⚠️  IMPORTANT: Please edit backend/.env and add your GEMINI_API_KEY!"
        echo "   Get one from: https://makersuite.google.com/app/apikey"
        echo
        if command -v nano &> /dev/null; then
            nano backend/.env
        elif command -v vim &> /dev/null; then
            vim backend/.env
        else
            echo "Please edit backend/.env manually"
        fi
    else
        echo "ERROR: backend/.env.example not found!"
        exit 1
    fi
else
    echo "✅ backend/.env already exists"
fi

echo
echo "[4/4] Starting EduViz..."
echo
echo "========================================"
echo "    Starting containers..."
echo "    Frontend: http://localhost:3000"
echo "    Backend:  http://localhost:8000/docs"
echo "========================================"
echo
echo "Press Ctrl+C to stop the application"
echo

docker-compose up --build

echo
echo "EduViz stopped. Thanks for testing! 🎉"