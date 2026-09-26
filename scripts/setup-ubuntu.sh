#!/bin/bash
# Setup script for Ubuntu/Debian

set -e

echo "🐧 AI Music Studio v2 - Ubuntu/Debian Setup"
echo ""

# Update package manager
echo "Updating package manager..."
sudo apt-get update

# Install Python 3.11
if ! command -v python3.11 &> /dev/null; then
    echo "Installing Python 3.11..."
    sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
else
    echo "✓ Python 3.11 already installed"
fi

# Install FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "Installing FFmpeg..."
    sudo apt-get install -y ffmpeg
else
    echo "✓ FFmpeg already installed"
fi

# Create virtual environment
echo "Creating virtual environment..."
python3.11 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "✓ Setup complete!"
echo ""
echo "To start the server:"
echo "  source venv/bin/activate"
echo "  python app.py"
echo ""
echo "To enable MusicGen (optional):"
echo "  pip install -r requirements-ai.txt"
echo "  export MUSICGEN_DEVICE=cpu  # or 'cuda' if you have GPU"
echo "  python app.py"
