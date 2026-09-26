#!/bin/bash
# Setup script for macOS

set -e

echo "🍎 AI Music Studio v2 - macOS Setup"
echo ""

# Check for Homebrew
if ! command -v brew &> /dev/null; then
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Install Python 3.11
if ! command -v python3.11 &> /dev/null; then
    echo "Installing Python 3.11..."
    brew install python@3.11
else
    echo "✓ Python 3.11 already installed"
fi

# Install FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "Installing FFmpeg..."
    brew install ffmpeg
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
