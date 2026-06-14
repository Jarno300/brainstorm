@echo off
echo ============================================
echo   Brainstorm - AI Chat Platform
echo ============================================
echo.
echo Choose how to run:
echo.
echo   1. Docker Compose (full stack - recommended)
echo      docker-compose up --build
echo.
echo   2. Local development (requires PostgreSQL + Redis)
echo      Start Redis: docker-compose up -d redis
echo      Start API:   cd backend ^&^& python run.py
echo      Start Celery: cd backend ^&^& python run_celery.py
echo      Start UI:    cd frontend ^&^& npx vite
echo.
echo ============================================
echo.
echo Starting with Docker Compose...
echo.

docker-compose up --build

echo.
echo Services:
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo.
pause
