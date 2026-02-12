# AIResearch - Financial News Analysis Platform

A full-stack application that parses financial news of selected stocks and provides AI-powered summaries and investment recommendations to help you decide whether to invest, reduce size, increase size, or close positions.

## Features

- 📰 **Real-time News Fetching**: Aggregates financial news from multiple sources
- 🧠 **AI-Powered Analysis**: Uses NLP models to analyze sentiment and generate summaries
- 💡 **Smart Recommendations**: Provides actionable investment recommendations based on news sentiment
- 📊 **Sentiment Analysis**: Breaks down positive, neutral, and negative sentiment percentages
- 📈 **Multi-Stock Tracking**: Track and analyze multiple stocks simultaneously
- 🎯 **Key Points Extraction**: Automatically extracts important information from articles

## Project Structure

```
AIResearch/
├── backend/                 # Flask Python API
│   ├── app/
│   │   ├── routes/         # API endpoints
│   │   ├── services/       # Business logic
│   │   └── __init__.py
│   ├── requirements.txt
│   ├── run.py
│   └── .env.example
└── frontend/               # React web application
    ├── src/
    │   ├── components/    # React components
    │   └── App.js
    ├── public/
    └── package.json
```

## Setup Instructions

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a dedicated virtual environment:
```bash
python3 -m venv airesearch_env
```

3. Activate the virtual environment:
```bash
source airesearch_env/bin/activate  # On Windows: airesearch_env\Scripts\activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Create `.env` file (copy from `.env.example`):
```bash
cp .env.example .env
```

6. Add your NewsAPI key to `.env` (optional but recommended):
```
NEWSAPI_KEY=your_api_key_here
```

Get a free API key at [newsapi.org](https://newsapi.org)

7. Run the server using the startup script:
```bash
chmod +x start-backend.sh
./start-backend.sh
```

Or run manually:
```bash
python run.py
```

The backend will start on `http://localhost:5000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm start
```

The frontend will open at `http://localhost:3000`

## API Endpoints

### Stocks
- `GET /api/stocks` - Get all tracked stocks
- `GET /api/stocks/<symbol>` - Get specific stock
- `POST /api/stocks` - Add new stock
- `DELETE /api/stocks/<symbol>` - Remove stock

### News
- `GET /api/news/search?symbol=AAPL&limit=10` - Search news for a stock
- `GET /api/news/trending?limit=20` - Get trending financial news
- `POST /api/news/bulk-search` - Search news for multiple stocks

### Analysis
- `POST /api/analysis/summarize` - Summarize articles
- `POST /api/analysis/sentiment` - Analyze sentiment
- `POST /api/analysis/recommendation` - Get investment recommendation

## Usage

1. **Add a Stock**: Enter a stock symbol (e.g., AAPL, GOOGL, TSLA) in the left sidebar
2. **View News**: The system automatically fetches recent news for the selected stock
3. **Analyze**: Click "Analyze All Articles" to get AI-powered insights
4. **Get Recommendation**: View the recommendation to guide your investment decision

### Recommendation Actions

- 🟢 **BUY** / **BUY_SMALL** - Positive sentiment, consider buying
- 🟢 **INCREASE_SIZE** - Good news for existing long position
- 🟡 **HOLD** / **WAIT** - Neutral or mixed signals
- 🔴 **REDUCE_SIZE** - Some negative signals for long position
- 🔴 **CLOSE_POSITION** - Strong negative sentiment
- 🔴 **AVOID** - Strong negative signals

## Technologies

**Backend:**
- Flask - Web framework
- Transformers (Hugging Face) - NLP models
- BeautifulSoup4 - Web scraping
- NewsAPI - News aggregation
- NLTK - Natural language processing

**Frontend:**
- React 18 - UI framework
- Axios - HTTP client
- CSS3 - Styling
- React Router - Navigation

## Configuration

### Environment Variables

Create a `.env` file in the backend directory:

```
FLASK_ENV=development
FLASK_DEBUG=True
NEWSAPI_KEY=your_newsapi_key
```

## Performance Notes

- News fetching may take 5-10 seconds depending on API response time
- Sentiment analysis uses a pre-trained model, so first analysis may take longer as the model loads
- The application stores stocks in a local `stocks.json` file

## Future Enhancements

- Historical price data integration
- Portfolio tracking and performance metrics
- Custom alert thresholds
- Email notifications
- Advanced filtering and search
- User authentication and accounts
- Machine learning model training on historical data
- Real-time news streaming
- Integration with trading APIs

## Troubleshooting

**CORS errors:** Make sure the Flask backend is running on port 5000

**Module not found:** Ensure all dependencies are installed: `pip install -r requirements.txt`

**News API limits:** The NewsAPI free tier has rate limits. Consider getting a paid API key for production use

**Port already in use:** Change the port in `backend/run.py` or `frontend/package.json` if ports are in use

## License

MIT License - Feel free to use and modify this project

## Support

For issues or questions, check the logs and ensure:
- Backend is running on `localhost:5000`
- Frontend is running on `localhost:3000`
- Python version 3.8+ is installed
- Node.js 14+ is installed
