import uuid
import warnings
from sentence_transformers import SentenceTransformer # type:ignore
try:
    from .config import (
        EMBEDDING_MODEL,
        MAX_CONTEXT_DOCS,
        PINECONE_API_KEY,
        PINECONE_INDEX,
        PINECONE_CLOUD,
        PINECONE_REGION,
        VECTOR_DIMENSION,
    )
except ImportError:
    from config import (
        EMBEDDING_MODEL,
        MAX_CONTEXT_DOCS,
        PINECONE_API_KEY,
        PINECONE_INDEX,
        PINECONE_CLOUD,
        PINECONE_REGION,
        VECTOR_DIMENSION,
    )
import os
from pinecone import Pinecone, ServerlessSpec # type:ignore

# Suppress sentence-transformers logging
os.environ['TRANSFORMERS_VERBOSITY'] = 'critical'
import logging
logging.getLogger("sentence_transformers").setLevel(logging.CRITICAL)
logging.getLogger("transformers").setLevel(logging.CRITICAL)

# Silence the Hugging Face Hub warning about unauthenticated public downloads.
warnings.filterwarnings(
    "ignore",
    message=r"Warning: You are sending unauthenticated requests to the HF Hub.*",
    category=UserWarning,
)


class KnowledgeBase:
    def __init__(self, verbose=False):
        """Initialize Pinecone-backed Knowledge Base (lazy-loads embedder and Pinecone)."""
        self._embedder = None  # Lazy-load on first use
        self._pc = None
        self._index = None
        self._init_error = None  # Store any startup errors
        self.verbose = verbose
        
        if self.verbose:
            print("📚 Initializing Collective Memory (Pinecone)...")
        
        # Lazy init - don't crash startup if Pinecone fails
        # _init_db is called on first RAG operation

    @property
    def embedder(self):
        """Lazy-load the embedding model on first access"""
        if self._embedder is None:
            if self.verbose:
                print("⏳ Loading embedding model (this takes ~30 seconds on first run)...")
            
            # Suppress HuggingFace download output
            import io
            from contextlib import redirect_stdout, redirect_stderr
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self._embedder = SentenceTransformer(EMBEDDING_MODEL)
            
            if self.verbose:
                print("✅ Embedding model loaded")
        return self._embedder

    def _init_db(self):
        """Create/connect Pinecone index (lazy, called on first use)."""
        if self._index is not None:
            return  # Already initialized
        
        if self._init_error:
            raise RuntimeError(f"Pinecone initialization failed: {self._init_error}")
        
        try:
            if not PINECONE_API_KEY:
                self._init_error = "PINECONE_API_KEY is not set"
                raise RuntimeError(self._init_error)

            self._pc = Pinecone(api_key=PINECONE_API_KEY)

            index_list = self._pc.list_indexes()
            if hasattr(index_list, "names"):
                existing_indexes = set(index_list.names())
            else:
                existing_indexes = {
                    idx.get("name")
                    for idx in index_list
                    if isinstance(idx, dict) and idx.get("name")
                }

            if PINECONE_INDEX not in existing_indexes:
                self._pc.create_index(
                    name=PINECONE_INDEX,
                    dimension=VECTOR_DIMENSION,
                    metric="cosine",
                    spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION),
                )

            self._index = self._pc.Index(PINECONE_INDEX)
        except Exception as e:
            self._init_error = str(e)
            raise RuntimeError(f"Pinecone initialization failed: {e}")

    def _require_index(self):
        """Ensure Pinecone is initialized, lazy-init if needed."""
        if self._index is None:
            self._init_db()  # Lazy init on first use, raises if fails
        
        # After _init_db(), _index must be set (or exception was raised)
        if self._index is None:
            raise RuntimeError("Pinecone index initialization did not set _index")
        return self._index

    @staticmethod
    def _extract_matches(response):
        if isinstance(response, dict):
            return response.get("matches", [])
        return getattr(response, "matches", []) or []

    @staticmethod
    def _extract_metadata(match):
        if isinstance(match, dict):
            return match.get("metadata", {}) or {}
        return getattr(match, "metadata", {}) or {}

    @staticmethod
    def _extract_id(match):
        if isinstance(match, dict):
            return match.get("id")
        return getattr(match, "id", None)

    def add_document(self, text, user_id="anonymous", source="contribution"):
        """
        Adds a text contribution to the Pinecone index.
        
        Args:
            text: The document text to add
            user_id: User who contributed (default: anonymous)
            source: Source of the document (default: contribution)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not text or len(text.strip()) < 10:
            print("⚠️  Document too short (min 10 chars)")
            return False

        try:
            doc_id = str(uuid.uuid4())

            # Create embedding and upsert to Pinecone
            embedding = self.embedder.encode(text).tolist()
            index = self._require_index()

            index.upsert(
                vectors=[{
                    "id": doc_id,
                    "values": embedding,
                    "metadata": {
                        "text": text,
                        "user_id": user_id,
                        "source": source,
                    },
                }]
            )
            
            print(f"📥 Knowledge Added: {doc_id} by {user_id}")
            return True
            
        except Exception as e:
            print(f"❌ Error adding document: {e}")
            return False

    def search(self, query, n_results=MAX_CONTEXT_DOCS):
        """
        Semantic search to find relevant context documents.
        
        Args:
            query: Search query text
            n_results: Number of results to return
            
        Returns:
            list: Relevant document texts
        """
        try:
            query_embedding = self.embedder.encode(query).tolist()
            index = self._require_index()

            response = index.query(
                vector=query_embedding,
                top_k=n_results,
                include_metadata=True,
            )

            matches = self._extract_matches(response)
            documents = []
            for match in matches:
                metadata = self._extract_metadata(match)
                text = metadata.get("text")
                if text:
                    documents.append(text)
            return documents
            
        except Exception as e:
            print(f"❌ Error searching: {e}")
            return []

    def count(self):
        """Get total number of documents in the index."""
        try:
            index = self._require_index()
            stats = index.describe_index_stats()
            return int(stats.get("total_vector_count", 0))
        except Exception as e:
            print(f"❌ Error counting documents: {e}")
            return 0

    def list_documents(self, limit=10):
        """List documents (approximate listing from vector metadata)."""
        try:
            index = self._require_index()
            response = index.query(
                vector=[0.0] * VECTOR_DIMENSION,
                top_k=limit,
                include_metadata=True,
            )
            rows = []
            for match in self._extract_matches(response):
                meta = self._extract_metadata(match)
                rows.append((
                    self._extract_id(match),
                    meta.get("text", ""),
                    meta.get("user_id", ""),
                    meta.get("source", ""),
                    None,
                ))
            return rows
        except Exception as e:
            print(f"❌ Error listing documents: {e}")
            return []

    def delete_document(self, doc_id):
        """Delete a document by ID"""
        try:
            index = self._require_index()
            index.delete(ids=[doc_id])
            print(f"🗑️  Document deleted: {doc_id}")
            return True
        except Exception as e:
            print(f"❌ Error deleting document: {e}")
            return False