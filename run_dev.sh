#!/bin/bash

# Run both backend and frontend for development

echo "Starting IG Unfollower Development Environment..."

# Start FastAPI backend
echo "Starting FastAPI backend on port 8000..."
cd "$(dirname "$0")"
uvicorn api.main:app --reload --port 8000 &
BACKEND_PID=$!

# Wait for backend to start
sleep 2

# Start frontend
echo "Starting React frontend on port 5173..."
cd frontend
npm run dev &
FRONTEND_PID=$!

# Trap to cleanup on exit
cleanup() {
    echo "Shutting down..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

echo ""
echo "=========================================="
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "API Docs: http://localhost:8000/docs"
echo "=========================================="
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for both processes
wait
