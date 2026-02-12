#!/bin/bash

# AIResearch Backend Startup Script

echo "=========================================="
echo "AIResearch Backend Server"
echo "=========================================="

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the script directory
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "airesearch_env" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run: python3 -m venv airesearch_env"
    exit 1
fi

# Activate the virtual environment
source "airesearch_env/bin/activate"

# Check if .env file exists, create from example if not
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "Creating .env from .env.example..."
        cp ".env.example" ".env"
        echo "⚠️  Please update .env with your API keys if needed"
    fi
fi

echo ""
echo "✓ Virtual environment activated"
echo "✓ Starting Flask server on http://localhost:5001"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=========================================="
echo ""

# Run the Flask app
python run.py
