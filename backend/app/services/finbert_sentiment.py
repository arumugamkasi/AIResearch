"""
FinBERT Sentiment Analysis
Finance-specific BERT model for accurate sentiment classification
Model: ProsusAI/finbert
"""

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import numpy as np
from typing import Dict, List
import hashlib


class FinBERTSentimentAnalyzer:
    """Advanced sentiment analysis using FinBERT model"""

    def __init__(self):
        self.model_name = "ProsusAI/finbert"
        self.device = self._get_device()
        self.model = None
        self.tokenizer = None
        self._cache = {}       # url/text hash → sentiment result
        self.batch_size = 16   # Articles per forward pass
        self.max_length = 128  # Titles+short desc don't need 512 tokens
        self._load_model()

    def _get_device(self):
        """Determine best available device"""
        if torch.cuda.is_available():
            return torch.device('cuda')
        elif torch.backends.mps.is_available():
            return torch.device('mps')  # Apple Silicon
        else:
            return torch.device('cpu')

    def _load_model(self):
        """Load FinBERT model and tokenizer"""
        try:
            print(f"📥 Loading FinBERT model on {self.device}...")

            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.model_name
            )
            self.model.to(self.device)
            self.model.eval()

            print("✅ FinBERT model loaded successfully")

        except Exception as e:
            print(f"❌ Failed to load FinBERT: {e}")
            print("   Falling back to keyword-based sentiment")
            self.model = None
            self.tokenizer = None

    def is_available(self) -> bool:
        """Check if FinBERT is loaded"""
        return self.model is not None and self.tokenizer is not None

    def _probs_to_result(self, probs_row) -> Dict:
        """Convert a probability row [positive, negative, neutral] to result dict"""
        positive = float(probs_row[0])
        negative = float(probs_row[1])
        neutral  = float(probs_row[2])
        max_idx  = int(np.argmax(probs_row))
        label    = ['positive', 'negative', 'neutral'][max_idx]
        return {
            'label':      label,
            'positive':   positive,
            'negative':   negative,
            'neutral':    neutral,
            'score':      positive - negative,
            'confidence': float(probs_row[max_idx]),
            'model':      'finbert'
        }

    def _neutral_result(self, reason='unavailable') -> Dict:
        return {
            'label': 'neutral', 'positive': 0.33,
            'negative': 0.33, 'neutral': 0.34,
            'score': 0.0, 'confidence': 0.34, 'model': reason
        }

    def analyze_text(self, text: str) -> Dict:
        """Analyze a single text (uses cache)"""
        if not self.is_available():
            return self._neutral_result()

        key = hashlib.md5(text.encode()).hexdigest()
        if key in self._cache:
            return self._cache[key]

        try:
            inputs = self.tokenizer(
                text, return_tensors="pt", truncation=True,
                max_length=self.max_length, padding=True
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            with torch.no_grad():
                logits = self.model(**inputs).logits
                probs  = torch.nn.functional.softmax(logits, dim=-1).cpu().numpy()[0]

            result = self._probs_to_result(probs)
            self._cache[key] = result
            return result

        except Exception as e:
            print(f"❌ FinBERT error: {e}")
            return self._neutral_result('error')

    def _run_batch(self, texts: List[str]) -> List[Dict]:
        """Run a single batched forward pass over a list of texts"""
        inputs = self.tokenizer(
            texts, return_tensors="pt", truncation=True,
            max_length=self.max_length, padding=True
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            logits = self.model(**inputs).logits
            probs  = torch.nn.functional.softmax(logits, dim=-1).cpu().numpy()

        return [self._probs_to_result(row) for row in probs]

    def analyze_articles(self, articles: List[Dict]) -> List[Dict]:
        """
        Analyze sentiment for a list of articles using batched inference.
        Already-cached articles are skipped.
        """
        if not self.is_available():
            print("⚠️  FinBERT not available, skipping sentiment analysis")
            return articles

        # Separate cached vs. articles that need inference
        texts_needed, indices_needed = [], []
        for i, article in enumerate(articles):
            if 'finbert_sentiment' in article:
                continue   # Already analyzed (e.g. from MongoDB cache)
            text = f"{article.get('title', '')} {article.get('description', '')}"
            key  = hashlib.md5(text.encode()).hexdigest()
            if key in self._cache:
                article['finbert_sentiment'] = self._cache[key]
            else:
                texts_needed.append(text)
                indices_needed.append(i)

        if not texts_needed:
            print("✅ All articles already cached — no FinBERT inference needed")
            return articles

        print(f"🔍 Running FinBERT on {len(texts_needed)} articles "
              f"(batch_size={self.batch_size})...")

        results = []
        for start in range(0, len(texts_needed), self.batch_size):
            batch_texts = texts_needed[start:start + self.batch_size]
            batch_results = self._run_batch(batch_texts)
            results.extend(batch_results)

        # Write results back and populate cache
        for article_idx, text, result in zip(indices_needed, texts_needed, results):
            articles[article_idx]['finbert_sentiment'] = result
            self._cache[hashlib.md5(text.encode()).hexdigest()] = result

        print(f"✅ Sentiment analysis complete")
        return articles

    def aggregate_sentiment(self, articles: List[Dict]) -> Dict:
        """
        Aggregate sentiment across multiple articles

        Args:
            articles: List of articles with 'finbert_sentiment'

        Returns:
            Aggregated sentiment statistics
        """
        if not articles:
            return {
                'overall_score': 0.0,
                'overall_label': 'neutral',
                'positive_ratio': 0.33,
                'negative_ratio': 0.33,
                'neutral_ratio': 0.34,
                'avg_confidence': 0.0,
                'article_count': 0
            }

        scores = []
        labels = []
        confidences = []

        for article in articles:
            sentiment = article.get('finbert_sentiment', {})
            if sentiment.get('model') == 'finbert':
                scores.append(sentiment['score'])
                labels.append(sentiment['label'])
                confidences.append(sentiment['confidence'])

        if not scores:
            return {
                'overall_score': 0.0,
                'overall_label': 'neutral',
                'positive_ratio': 0.33,
                'negative_ratio': 0.33,
                'neutral_ratio': 0.34,
                'avg_confidence': 0.0,
                'article_count': len(articles)
            }

        # Calculate statistics
        overall_score = float(np.mean(scores))
        avg_confidence = float(np.mean(confidences))

        # Count labels
        label_counts = {
            'positive': labels.count('positive'),
            'negative': labels.count('negative'),
            'neutral': labels.count('neutral')
        }

        total = len(labels)
        positive_ratio = label_counts['positive'] / total
        negative_ratio = label_counts['negative'] / total
        neutral_ratio = label_counts['neutral'] / total

        # Overall label
        if overall_score > 0.2:
            overall_label = 'positive'
        elif overall_score < -0.2:
            overall_label = 'negative'
        else:
            overall_label = 'neutral'

        return {
            'overall_score': overall_score,
            'overall_label': overall_label,
            'positive_ratio': positive_ratio,
            'negative_ratio': negative_ratio,
            'neutral_ratio': neutral_ratio,
            'avg_confidence': avg_confidence,
            'article_count': total
        }
