import chromadb 
from chromadb.config import Settings 
from sentence_transformers import SentenceTransformer 
import uuid 

class KnowledgeBase:
    def __init__(self, db_path="./collective_memory"):
        print("📚 Initializing Collective Memory (Vector DB)...")
        
        # 1. Setup ChromaDB (Local Persistence)
        self.client = chromadb.PersistentClient(path=db_path)
        
        # 2. Embedding Model (Fast & Efficient)
        # "all-MiniLM-L6-v2" is a standard, lightweight model for semantic search
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        
        # 3. Create/Get Collection
        self.collection = self.client.get_or_create_collection(name="collective_knowledge")
        print(f"✅ Memory Online. Documents indexed: {self.collection.count()}")

    def add_document(self, text, user_id="anonymous", source="contribution"):
        """
        Adds a text contribution to the vector database.
        """
        if not text or len(text.strip()) < 10:
            return False

        # Generate unique ID
        doc_id = str(uuid.uuid4())
        
        # Create embedding
        embedding = self.embedder.encode(text).tolist()
        
        # Store in DB
        self.collection.add(
            documents=[text],
            embeddings=[embedding],
            metadatas=[{"user_id": user_id, "source": source}],
            ids=[doc_id]
        )
        print(f"📥 Knowledge Added: {doc_id} by {user_id}")
        return True

    def search(self, query, n_results=3):
        """
        Semantic search to find relevant context for a query.
        """
        # Embed query
        query_embedding = self.embedder.encode(query).tolist()
        
        # Retrieve nearest neighbors
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        
        # Flatten results
        documents = results['documents'][0] if results['documents'] else []
        return documents