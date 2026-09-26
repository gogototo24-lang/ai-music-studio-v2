# Setup script for Windows PowerShell

Write-Host "Windows AI Music Studio v2 - Setup" -ForegroundColor Green
Write-Host ""

# Check for Python
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "⚠ Python not found in PATH"
    Write-Host "Please install Python 3.11 from https://www.python.org/downloads/"
    Write-Host "Make sure to check 'Add Python to PATH' during installation"
    exit 1
}

# Check for FFmpeg
if (!(Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "⚠ FFmpeg not found in PATH"
    Write-Host "Please install FFmpeg:"
    Write-Host "  1. Using Chocolatey: choco install ffmpeg"
    Write-Host "  2. Or Windows Package Manager: winget install ffmpeg"
    Write-Host "  3. Or download from https://ffmpeg.org/download.html"
    exit 1
}

Write-Host "✓ Python and FFmpeg found"
Write-Host ""

# Create virtual environment
Write-Host "Creating virtual environment..."
python -m venv venv
& .\venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

Write-Host ""
Write-Host "✓ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "To start the server:"
Write-Host "  .\venv\Scripts\Activate.ps1"
Write-Host "  python app.py"
Write-Host ""
Write-Host "To enable MusicGen (optional):"
Write-Host "  pip install -r requirements-ai.txt"
Write-Host "  # Then run: python app.py"
