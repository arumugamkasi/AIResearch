#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}AIResearch - Startup Script${NC}"
echo -e "${BLUE}========================================${NC}"

# Check if backend and frontend folders exist
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo "Error: backend or frontend directory not found"
    exit 1
fi

# Start backend
echo -e "${GREEN}Starting Backend...${NC}"
cd backend

# Check if dedicated venv exists
if [ ! -d "airesearch_env" ]; then
    echo "Creating virtual environment..."
    python3 -m venv airesearch_env
fi

# Activate the dedicated venv and install requirements
source airesearch_env/bin/activate
pip install -q -r requirements.txt

# Start Flask server in background
python run.py &
BACKEND_PID=$!
echo -e "${GREEN}Backend started (PID: $BACKEND_PID)${NC}"

# Return to project root
cd ..

# Wait for backend to start
echo "Waiting for backend to start..."
sleep 3

# Start frontend
echo -e "${GREEN}Starting Frontend...${NC}"
cd frontend

# Install dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install --quiet
fi

# Start React development server
npm start &
FRONTEND_PID=$!
echo -e "${GREEN}Frontend started (PID: $FRONTEND_PID)${NC}"

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✓ Both servers are running!${NC}"
echo -e "${BLUE}Backend: http://localhost:5001${NC}"
echo -e "${BLUE}Frontend: http://localhost:3000${NC}"
echo -e "${BLUE}========================================${NC}"

# Keep script running
wait
