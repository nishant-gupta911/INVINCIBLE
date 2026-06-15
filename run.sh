#!/bin/bash

# Run the entire INVINCIBLE RAG project in one command
# This script starts both the FastAPI backend and React frontend

echo "Starting INVINCIBLE RAG Project..."
echo ""

# Activate virtual environment and start Backend (FastAPI)
echo "Starting Backend API on port 8000..."
source .venv/bin/activate && uvicorn api:app --host 0.0.0.0 --port 8000 &

# Give backend a moment to start
sleep 2

# Start Frontend (React/Vite)
echo "Starting Frontend on port 5173..."
cd frontend && npm run dev &

# Wait for both processes
wait

echo ""
echo "============================================"
echo "Backend API: http://localhost:8000"
echo "Frontend:    http://localhost:5173"
echo "============================================"
