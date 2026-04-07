"""
Tavily Service - AI-optimised news search (MCP-compatible)
Free tier: 1000 searches/month
Designed specifically for AI applications — better quality than DuckDuckGo
"""

import os
from datetime import datetime
from typing import List, Dict


class TavilyService:
    """Service for fetching financial news via Tavily AI Search"""

    def __init__(self):
        self.api_key = os.getenv('TAVILY_API_KEY', '')
        self.enabled = bool(self.api_key and self.api_key != 'your_tavily_key_here')

        if self.enabled:
            try:
                from tavily import TavilyClient
                self.client = TavilyClient(api_key=self.api_key)
                print("✅ Tavily AI Search configured")
            except Exception as e:
                print(f"⚠️  Tavily initialization error: {e}")
                self.client = None
                self.enabled = False
        else:
            self.client = None
            print("⚠️  Tavily API key not configured")

    def is_available(self) -> bool:
        return self.enabled and self.client is not None

    def fetch_company_news(self, symbol: str, company_name: str = None, limit: int = 10) -> List[Dict]:
        """
        Fetch company news using Tavily AI search.

        Args:
            symbol: Stock ticker (e.g. 'AAPL')
            company_name: Full company name for better results (e.g. 'Apple Inc')
            limit: Max articles to return (max 10 per search call)

        Returns:
            List of articles with credibility_score: 0.80
        """
        if not self.is_available():
            return []

        # Use company name if available for better search quality
        query_name = company_name if company_name else symbol
        query = f"{query_name} {symbol} stock news today"

        try:
            response = self.client.search(
                query=query,
                search_depth="basic",   # "basic" = 1 API credit, "advanced" = 2
                topic="news",
                days=2,                 # Only last 2 days (today + yesterday)
                max_results=limit,
                include_answer=False,
                include_raw_content=False
            )

            articles = []
            for result in response.get('results', []):
                pub_date = result.get('published_date')
                if pub_date:
                    try:
                        # Tavily returns ISO format dates
                        parsed_date = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                        date_str = parsed_date.replace(tzinfo=None).isoformat()
                    except (ValueError, TypeError):
                        date_str = datetime.now().isoformat()
                else:
                    date_str = datetime.now().isoformat()

                articles.append({
                    'title': result.get('title', ''),
                    'description': result.get('content', '')[:500],  # Truncate long content
                    'url': result.get('url', ''),
                    'source': result.get('source', 'Tavily'),
                    'published_date': date_str,
                    'image': '',
                    'source_type': 'tavily',
                    'credibility_score': 0.80,  # High quality AI-curated sources
                    'tavily_score': result.get('score', 0),  # Tavily's own relevance score
                })

            print(f"📰 Tavily: Fetched {len(articles)} articles for {symbol}")
            return articles

        except Exception as e:
            print(f"❌ Tavily error for {symbol}: {e}")
            return []
