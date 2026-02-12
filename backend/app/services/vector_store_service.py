import chromadb
import os
import hashlib
from datetime import datetime


class VectorStoreService:
    """Service for storing and retrieving news articles using ChromaDB"""

    def __init__(self):
        persist_dir = os.getenv('CHROMA_PERSIST_DIR', './chroma_data')
        self.client = chromadb.PersistentClient(path=persist_dir)

    def _get_collection(self, symbol):
        """Get or create a collection for a stock symbol"""
        collection_name = f"news_{symbol.lower()}"
        return self.client.get_or_create_collection(
            name=collection_name,
            metadata={"symbol": symbol.upper()}
        )

    def store_articles(self, symbol, articles):
        """Store news articles in ChromaDB for a given stock symbol"""
        if not articles:
            return 0

        collection = self._get_collection(symbol)

        documents = []
        metadatas = []
        ids = []

        for article in articles:
            text = f"{article.get('title', '')}. {article.get('description', '')}"
            if not text.strip() or text.strip() == '.':
                continue

            source_key = article.get('url', '') or article.get('title', '')
            doc_id = hashlib.md5(source_key.encode()).hexdigest()

            documents.append(text)
            metadatas.append({
                'title': article.get('title', ''),
                'url': article.get('url', ''),
                'source': article.get('source', ''),
                'published_date': article.get('published_date', ''),
                'symbol': symbol.upper(),
                'stored_at': datetime.now().isoformat()
            })
            ids.append(doc_id)

        if documents:
            collection.upsert(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )

        return len(documents)

    def query_articles(self, symbol, query_text, n_results=10):
        """Query ChromaDB for articles relevant to a query"""
        collection = self._get_collection(symbol)

        if collection.count() == 0:
            return []

        results = collection.query(
            query_texts=[query_text],
            n_results=min(n_results, collection.count())
        )

        articles = []
        if results and results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                distance = results['distances'][0][i] if results['distances'] else None
                articles.append({
                    'text': doc,
                    'title': metadata.get('title', ''),
                    'url': metadata.get('url', ''),
                    'source': metadata.get('source', ''),
                    'published_date': metadata.get('published_date', ''),
                    'relevance_score': 1.0 - (distance or 0)
                })

        return articles

    def get_all_articles(self, symbol, limit=50):
        """Get all stored articles for a symbol"""
        collection = self._get_collection(symbol)
        if collection.count() == 0:
            return []

        results = collection.get(
            limit=limit,
            include=['documents', 'metadatas']
        )

        articles = []
        if results and results['documents']:
            for i, doc in enumerate(results['documents']):
                metadata = results['metadatas'][i] if results['metadatas'] else {}
                articles.append({
                    'text': doc,
                    'title': metadata.get('title', ''),
                    'url': metadata.get('url', ''),
                    'source': metadata.get('source', ''),
                    'published_date': metadata.get('published_date', ''),
                })

        return articles

    def clear_collection(self, symbol):
        """Clear all articles for a symbol"""
        collection_name = f"news_{symbol.lower()}"
        try:
            self.client.delete_collection(collection_name)
        except Exception:
            pass
