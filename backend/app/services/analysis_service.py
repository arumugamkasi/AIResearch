import ollama
import os
import json
import re

from app.services.vector_store_service import VectorStoreService


class AnalysisService:
    """Service for analyzing financial news using RAG with Ollama"""

    def __init__(self):
        self.vector_store = VectorStoreService()
        self.ollama_base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        self.model = os.getenv('OLLAMA_MODEL', 'llama3.2')
        self._ollama_client = None

    @property
    def client(self):
        if self._ollama_client is None:
            self._ollama_client = ollama.Client(host=self.ollama_base_url)
        return self._ollama_client

    def _check_ollama_available(self):
        try:
            self.client.list()
            return True
        except Exception as e:
            print(f"Ollama not available: {e}")
            return False

    def _call_ollama(self, prompt, system_prompt=None):
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})

        response = self.client.chat(
            model=self.model,
            messages=messages,
            options={
                'temperature': 0.3,
                'num_predict': 2048,
            }
        )

        # Handle both Pydantic object and dict-style responses
        if hasattr(response, 'message'):
            msg = response.message
            return msg.content if hasattr(msg, 'content') else msg.get('content', '')
        elif isinstance(response, dict):
            return response.get('message', {}).get('content', '')
        return str(response)

    def _build_rag_context(self, symbol, query=None):
        """Retrieve relevant articles from ChromaDB for RAG context"""
        if query:
            articles = self.vector_store.query_articles(symbol, query, n_results=10)
        else:
            articles = self.vector_store.get_all_articles(symbol, limit=10)

        if not articles:
            return "", []

        context_parts = []
        for i, article in enumerate(articles, 1):
            title = article.get('title', 'Untitled')
            text = article.get('text', article.get('description', ''))
            source = article.get('source', 'Unknown')
            date = article.get('published_date', 'Unknown date')
            context_parts.append(
                f"[Article {i}] ({source}, {date})\n"
                f"Title: {title}\n"
                f"Content: {text}\n"
            )

        context = "\n---\n".join(context_parts)
        return context, articles

    def get_recommendation(self, symbol, articles=None, current_position='none'):
        """Get investment recommendation using RAG"""
        # Store any newly-passed articles in ChromaDB
        if articles:
            self.vector_store.store_articles(symbol, articles)

        if not self._check_ollama_available():
            return self._fallback_response(
                symbol, articles or [],
                error="Ollama is not running. Start it with 'ollama serve' and ensure llama3.2 is pulled."
            )

        # Build RAG context from ChromaDB
        query = f"{symbol} stock financial performance outlook sentiment analysis"
        context, retrieved_articles = self._build_rag_context(symbol, query)

        if not context:
            return self._fallback_response(
                symbol, articles or [],
                error="No articles found in the knowledge base. Please fetch news first."
            )

        system_prompt = (
            "You are an expert financial analyst AI. You analyze news articles about stocks "
            "and provide comprehensive investment analysis across sentiment, critical events, "
            "and revenue outlook. You must respond ONLY with valid JSON, no markdown, no extra text. "
            "Always be balanced and note risks. IMPORTANT: always close all JSON braces and brackets."
        )

        user_prompt = f"""Analyze the following news articles about {symbol} stock. Provide a comprehensive analysis covering three areas:
1. SENTIMENT: Overall market sentiment and reasoning
2. CRITICAL EVENTS: Any credit/rating changes, leadership changes, M&A, legal, regulatory, or other company-changing events
3. REVENUE OUTLOOK: Forward-looking revenue direction based on the news

Current position: {current_position}

NEWS ARTICLES:
{context}

Respond with EXACTLY this JSON (no markdown code fences, raw JSON only). IMPORTANT: close all braces.
{{
    "recommendation": "<BUY|BUY_SMALL|HOLD|WAIT|AVOID|SELL|REDUCE_SIZE|INCREASE_SIZE|CLOSE_POSITION>",
    "confidence": <float 0.0-1.0>,
    "sentiment_score": <float -1.0 to 1.0>,
    "sentiment_breakdown": {{"positive": <0-1>, "neutral": <0-1>, "negative": <0-1>}},
    "summary": "<2-3 sentence summary>",
    "key_points": ["<point 1>", "<point 2>", "<point 3>"],
    "reasoning": "<2-4 sentence reasoning for the sentiment and recommendation>",
    "critical_events": [{{"event": "<description>", "impact": "<POSITIVE|NEGATIVE|NEUTRAL>", "category": "<CREDIT_RATING|ANALYST_RATING|LEADERSHIP|M_AND_A|LEGAL|REGULATORY|PRODUCT_LAUNCH|RESTRUCTURING|OTHER>"}}],
    "revenue_outlook": {{"direction": "<GROWTH|STABLE|DECLINE|UNCERTAIN>", "summary": "<2-3 sentence outlook>", "factors": ["<factor 1>", "<factor 2>"]}}
}}"""

        try:
            raw_response = self._call_ollama(user_prompt, system_prompt)
            result = self._parse_analysis_response(raw_response, symbol)
            result['symbol'] = symbol
            return result
        except Exception as e:
            print(f"Error in RAG analysis: {e}")
            return self._fallback_response(
                symbol, articles or [],
                error=f"LLM analysis failed: {str(e)}"
            )

    def analyze_sentiment(self, articles):
        """Analyze sentiment of articles using Ollama"""
        if not self._check_ollama_available():
            return self._fallback_sentiment(articles, error="Ollama is not running.")

        article_texts = []
        for i, article in enumerate(articles[:10], 1):
            title = article.get('title', '')
            desc = article.get('description', '')
            article_texts.append(f"[{i}] {title}. {desc}")

        combined = "\n".join(article_texts)

        system_prompt = (
            "You are a financial sentiment analyzer. "
            "Respond ONLY with valid JSON, no markdown, no extra text."
        )

        user_prompt = f"""Analyze the sentiment of each of these financial news articles.

ARTICLES:
{combined}

Respond with EXACTLY this JSON structure (no markdown code fences):
{{
    "individual_sentiments": [
        {{"title": "<article title>", "sentiment": "<POSITIVE|NEGATIVE|NEUTRAL>", "confidence": <0-1>}}
    ],
    "overall_sentiment": {{
        "positive": <0-1>,
        "neutral": <0-1>,
        "negative": <0-1>
    }},
    "sentiment_score": <float -1 to 1>
}}"""

        try:
            raw_response = self._call_ollama(user_prompt, system_prompt)
            return self._parse_json_response(raw_response)
        except Exception:
            return self._fallback_sentiment(articles)

    def summarize_articles(self, articles, symbol=None):
        """Summarize key points from articles using Ollama"""
        if not self._check_ollama_available():
            return {
                'summary': 'Ollama is not available for summarization.',
                'key_points': [],
                'article_count': len(articles),
                'symbol': symbol
            }

        article_texts = []
        for i, article in enumerate(articles[:10], 1):
            title = article.get('title', '')
            desc = article.get('description', '')
            article_texts.append(f"[{i}] {title}. {desc}")

        combined = "\n".join(article_texts)
        symbol_str = f" about {symbol}" if symbol else ""

        prompt = f"""Summarize these financial news articles{symbol_str} into a concise overview.

ARTICLES:
{combined}

Provide:
1. A 2-3 sentence summary
2. Up to 5 key points

Respond with EXACTLY this JSON (no markdown code fences):
{{
    "summary": "<concise summary>",
    "key_points": ["<point 1>", "<point 2>"]
}}"""

        try:
            raw = self._call_ollama(
                prompt,
                "You are a financial news summarizer. Respond ONLY with valid JSON."
            )
            parsed = self._parse_json_response(raw)
            parsed['article_count'] = len(articles)
            parsed['symbol'] = symbol
            return parsed
        except Exception:
            return {
                'summary': 'Unable to generate summary.',
                'key_points': [],
                'article_count': len(articles),
                'symbol': symbol
            }

    def _parse_analysis_response(self, raw_response, symbol):
        parsed = self._parse_json_response(raw_response)
        return {
            'symbol': symbol,
            'recommendation': parsed.get('recommendation', 'HOLD'),
            'confidence': float(parsed.get('confidence', 0.5)),
            'sentiment_score': float(parsed.get('sentiment_score', 0.0)),
            'sentiment_breakdown': parsed.get('sentiment_breakdown', {
                'positive': 0.33, 'neutral': 0.34, 'negative': 0.33
            }),
            'summary': parsed.get('summary', ''),
            'key_points': parsed.get('key_points', []),
            'reasoning': parsed.get('reasoning', ''),
            'critical_events': parsed.get('critical_events', []),
            'revenue_outlook': parsed.get('revenue_outlook', {
                'direction': 'UNCERTAIN',
                'summary': 'No revenue outlook available.',
                'factors': []
            })
        }

    def _parse_json_response(self, raw_response):
        """Extract and parse JSON from Ollama's response"""
        text = raw_response.strip()

        # Strip markdown code fences if present
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```\s*$', '', text)
        text = text.strip()

        # Try direct parse
        parsed = self._try_parse_json(text)
        if parsed is not None:
            return parsed

        # Try to find JSON object in the text
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            parsed = self._try_parse_json(match.group())
            if parsed is not None:
                return parsed

        # LLMs often omit closing braces — try repairing
        parsed = self._try_repair_json(text)
        if parsed is not None:
            return parsed

        print(f"Failed to parse Ollama response as JSON: {text[:300]}")
        return {}

    def _try_parse_json(self, text):
        """Try to parse JSON, return None on failure"""
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return None

    def _try_repair_json(self, text):
        """Try to repair malformed JSON from LLM output"""
        # Find the start of the JSON object
        start = text.find('{')
        if start == -1:
            return None

        candidate = text[start:]

        # Count braces to find how many are missing
        open_braces = candidate.count('{')
        close_braces = candidate.count('}')
        missing = open_braces - close_braces

        if missing > 0:
            # Truncate any trailing incomplete value
            # Find the last complete key-value pair
            candidate = candidate.rstrip()
            # If it ends mid-string, close the string
            if candidate.count('"') % 2 != 0:
                candidate += '"'
            # If it ends with a trailing comma, remove it
            candidate = candidate.rstrip(',').rstrip()
            # Add missing closing braces
            candidate += '}' * missing

        result = self._try_parse_json(candidate)
        if result is not None:
            return result

        # More aggressive: try adding closing brackets/braces
        for suffix in ['"}', '"]}', '"]}}', '"}]}']:
            result = self._try_parse_json(candidate.rstrip('"}],') + suffix)
            if result is not None:
                return result

        return None

    def _fallback_response(self, symbol, articles, error=None):
        return {
            'symbol': symbol,
            'recommendation': 'HOLD',
            'confidence': 0.0,
            'sentiment_score': 0.0,
            'sentiment_breakdown': {
                'positive': 0.33, 'neutral': 0.34, 'negative': 0.33
            },
            'summary': error or 'Analysis unavailable. Please ensure Ollama is running.',
            'key_points': [
                'LLM-based analysis is currently unavailable',
                f'{len(articles)} articles were found but could not be analyzed',
                'Please start Ollama: run "ollama serve" in a terminal',
                'Then ensure the model is available: run "ollama pull llama3.2"'
            ],
            'reasoning': error or 'Could not connect to the local LLM for analysis.',
            'critical_events': [],
            'revenue_outlook': {
                'direction': 'UNCERTAIN',
                'summary': 'Revenue outlook unavailable.',
                'factors': []
            }
        }

    def _fallback_sentiment(self, articles, error=None):
        return {
            'individual_sentiments': [
                {'title': a.get('title', ''), 'sentiment': 'NEUTRAL', 'confidence': 0.0}
                for a in articles[:10]
            ],
            'overall_sentiment': {'positive': 0.33, 'neutral': 0.34, 'negative': 0.33},
            'sentiment_score': 0.0
        }
