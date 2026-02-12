# AIResearch Backend - Quick Reference

## Current Status
✓ Backend is **running on http://localhost:5001**
✓ Virtual environment: `airesearch_env/` is active and ready
✓ All dependencies installed and verified

## Start Backend

### macOS/Linux
```bash
cd backend
./start-backend.sh
```

### Windows
```bash
cd backend
start-backend.bat
```

### Manual (any OS)
```bash
cd backend
source airesearch_env/bin/activate  # Windows: airesearch_env\Scripts\activate
python run.py
```

## Start Frontend
```bash
cd frontend
npm start
```

Opens at: http://localhost:3000

## Key Paths
- Project: `/Users/arukasi/PROJECTS/AIResearch/`
- Backend: `./backend/`
- Frontend: `./frontend/`
- Venv: `./backend/airesearch_env/`

## Environment Info
- Python: 3.9.16
- Flask: 3.0.0
- Port: 5001 (configurable via FLASK_PORT in .env)
- Debug: Enabled (development mode)

## API Test
```bash
curl http://localhost:5001/api/stocks
```

## Config File
Create `backend/.env`:
```
FLASK_ENV=development
FLASK_DEBUG=True
NEWSAPI_KEY=your_api_key_here
FLASK_PORT=5001
```

## Docs
- `BACKEND_SETUP.md` - Complete setup guide
- `README.md` - Full project documentation
- `QUICKSTART.md` - Getting started
