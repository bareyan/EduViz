#!/bin/bash
# Quick start script for ManimagAin with Visual QC

cd "$(dirname "$0")/backend"

echo "=========================================="
echo "Starting ManimagAin Server"
echo "=========================================="
echo ""
echo "Visual QC Status:"

# Check if Ollama is running
if pgrep -x "ollama" > /dev/null; then
    echo "  ✅ Ollama service is running"
    
    # Check if model is available
    if ollama list | grep -q "moondream"; then
        echo "  ✅ Vision model (moondream) is available"
        echo "  ✅ Visual QC is ENABLED"
    else
        echo "  ⚠️  No vision model found"
        echo "  ℹ️  Run: ollama pull moondream"
        echo "  ⚠️  Visual QC will be DISABLED"
    fi
else
    echo "  ⚠️  Ollama service not running"
    echo "  ℹ️  Visual QC will be DISABLED"
    echo "  ℹ️  To enable: sudo systemctl start ollama"
fi

echo ""
echo "Starting server on http://0.0.0.0:8000"
echo "API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo "=========================================="
echo ""

# Start the server
micromamba run -n manim uvicorn app.main:app --host 0.0.0.0 --port 8000
