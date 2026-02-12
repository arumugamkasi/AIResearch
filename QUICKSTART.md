# Getting Started with AIResearch

## Quick Start (5 minutes)

### 1. Install Backend Environment

```bash
cd backend
python3 -m venv airesearch_env
source airesearch_env/bin/activate  # or `airesearch_env\Scripts\activate` on Windows
pip install -r requirements.txt
```

**Note:** The virtual environment `airesearch_env` is created only once. It's automatically activated by the startup scripts.

### 2. Install Frontend Dependencies

```bash
cd frontend
npm install
```

### 3. Start the Servers

**Option A: Automated Start (Recommended)**

Terminal 1 - Backend:
```bash
cd backend
chmod +x start-backend.sh
./start-backend.sh
```

Terminal 2 - Frontend:
```bash
cd frontend
npm start
```

**Option B: Manual Start**

Terminal 1 - Backend:
```bash
cd backend
source airesearch_env/bin/activate
python run.py
```

Terminal 2 - Frontend:
```bash
cd frontend
npm start
```

### 3. Open in Browser

Navigate to `http://localhost:3000`

## First Steps

1. **Add a Stock**: Enter a stock symbol like `AAPL`, `GOOGL`, or `TSLA`
2. **View News**: The system fetches recent news automatically
3. **Analyze**: Click "Analyze All Articles"
4. **Get Insight**: View the recommendation and sentiment breakdown

## Common Issues

| Issue | Solution |
|-------|----------|
| Port 5000/3000 in use | Kill the process using the port or change port in code |
| ModuleNotFoundError | Ensure virtual environment is activated and requirements installed |
| npm: command not found | Install Node.js from nodejs.org |
| Python: command not found | Install Python 3.8+ from python.org |

## Optional: API Keys

For better news coverage, get a free NewsAPI key:
1. Visit [newsapi.org](https://newsapi.org)
2. Sign up for free account
3. Copy your API key
4. Create `backend/.env` and add: `NEWSAPI_KEY=your_key_here`

## Architecture Overview

```
User Interface (React)
        ↓
    HTTP/JSON
        ↓
Flask Backend API
        ↓
[News Services] [Analysis Services] [Stock Services]
        ↓
[External APIs, NLP Models, Local Storage]
```

## Next Steps

- Customize sentiment thresholds in `backend/app/services/analysis_service.py`
- Add more news sources in `backend/app/services/news_service.py`
- Enhance the UI in `frontend/src/components/`
- Deploy to production (see DEPLOYMENT.md)
