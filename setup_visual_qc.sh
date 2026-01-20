#!/bin/bash
# Setup script for Visual QC with Ollama

echo "=========================================="
echo "Visual QC Setup Script"
echo "=========================================="
echo ""

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama is not installed"
    echo "Installing Ollama..."
    curl -fsSL https://ollama.ai/install.sh | sh
else
    echo "✅ Ollama is already installed"
fi

echo ""

# Check if Ollama service is running
if systemctl is-active --quiet ollama; then
    echo "✅ Ollama service is running"
else
    echo "⚠️  Ollama service is not running"
    echo "Starting Ollama service..."
    sudo systemctl start ollama
fi

echo ""

# Install Python ollama package
echo "Installing Python ollama package in micromamba environment..."
micromamba run -n manim pip install ollama

echo ""

# Pull vision model
echo "=========================================="
echo "Pulling Vision Model"
echo "=========================================="
echo ""
echo "This will download ~8GB of data (llama3.2-vision)"
echo "Options:"
echo "  1) llama3.2-vision (~8GB) - Balanced (RECOMMENDED)"
echo "  2) moondream (~2GB) - Fastest, less capable"
echo "  3) llava:13b (~8GB) - More capable"
echo "  4) Skip for now"
echo ""
read -p "Select option [1-4]: " choice

case $choice in
    1)
        echo "Pulling llama3.2-vision..."
        ollama pull llama3.2-vision
        ;;
    2)
        echo "Pulling moondream..."
        ollama pull moondream
        ;;
    3)
        echo "Pulling llava:13b..."
        ollama pull llava:13b
        ;;
    4)
        echo "Skipped. You can pull a model later with:"
        echo "  ollama pull llama3.2-vision"
        ;;
    *)
        echo "Invalid option. Run the script again to choose."
        ;;
esac

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "To test Visual QC, run:"
echo "  python test_visual_qc.py"
echo ""
echo "To start the server with micromamba:"
echo "  micromamba run -n manim uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "Visual QC will run automatically during video generation."
echo ""
