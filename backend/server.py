import os
from fastapi import FastAPI, HTTPException #type:ignore
from fastapi.middleware.cors import CORSMiddleware  #type:ignore
from pydantic import BaseModel
import uvicorn # type:ignore
import logging

try:
    from .LLM import CollectiveModel
    from .config import ALLOWED_ORIGIN, SERVER_PORT, DEBUG_MODE
except ImportError:
    from LLM import CollectiveModel
    from config import ALLOWED_ORIGIN, SERVER_PORT, DEBUG_MODE

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Collective AI Backend",
    description="RAG-powered AI with HuggingFace Inference API",
    docs_url="/docs" if DEBUG_MODE else None
)

# CORS with proper validation
allowed_origins = [origin.strip() for origin in ALLOWED_ORIGIN if origin.strip()]
if "*" not in allowed_origins:
    # Production: specific origins only
    logger.info(f"CORS: Restricted to {allowed_origins}")
else:
    logger.warning("CORS: Allow All Origins (not recommended for production)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Initialize LLM
logger.info("Initializing Collective AI Backend...")
ai_engine = CollectiveModel()
logger.info("✅ Backend Ready - RAG loads on first request")

# Lazy-load knowledge base
_knowledge_base = None
_session_histories: dict[str, list[dict[str, str]]] = {}

def get_knowledge_base():
    global _knowledge_base
    if _knowledge_base is None:
        try:
            from .rag import KnowledgeBase
        except ImportError:
            from rag import KnowledgeBase
        _knowledge_base = KnowledgeBase()
    return _knowledge_base

# --- Schemas ---
class ChatRequest(BaseModel):
    message: str
    sessionId: str | None = None
    userId: str | None = None

class ContributionRequest(BaseModel):
    content: str | None = None  # From HTML form
    text: str | None = None      # Alternative field name
    title: str | None = None     # Optional: contribution title
    userId: str | None = None
    
    def get_text(self):
        """Get text from either 'content' or 'text' field"""
        return (self.content or self.text or "").strip()

class SearchRequest(BaseModel):
    query: str
    n_results: int = 3

# --- Endpoints ---

@app.get("/")
def home():
    return {
        "status": "Collective AI Server Running",
        "docs_url": "/docs",
        "endpoints": {
            "chat": "POST /api/chat",
            "contribute": "POST /api/contribute",
            "search": "POST /api/search",
            "memory_stats": "GET /api/stats"
        }
    }

@app.get("/api/stats")
async def memory_stats():
    """Get knowledge base statistics"""
    return {
        "total_documents": get_knowledge_base().count(),
        "embedding_model": "all-MiniLM-L6-v2",
        "backend": "Pinecone"
    }

@app.post("/api/contribute")
async def contribute_endpoint(request: ContributionRequest):
    """Add knowledge to the collective memory (from HTML form or API)"""
    text = request.get_text()
    if not text:
        raise HTTPException(status_code=400, detail="Content cannot be empty")
    
    logger.info(f"Contribution from: {request.userId or 'anonymous'} | Title: {request.title or 'Untitled'}")
    
    # Add to RAG knowledge base
    success = get_knowledge_base().add_document(
        text, 
        user_id=request.userId or "anonymous",
        source="contribution_form"
    )
    
    if success:
        return {
            "status": "success",
            "message": "Knowledge assimilated into the Collective.",
            "total_documents": get_knowledge_base().count()
        }
    else:
        raise HTTPException(status_code=400, detail="Content too short or invalid (min 10 chars)")

@app.post("/api/search")
async def search_endpoint(request: SearchRequest):
    """Search the knowledge base"""
    if not request.query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    results = get_knowledge_base().search(request.query, n_results=request.n_results)
    
    return {
        "query": request.query,
        "results": results,
        "count": len(results)
    }

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """Chat with Collective AI using RAG"""
    if not request.message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    logger.debug(f"Chat request from session: {request.sessionId}")
    
    try:
        session_key = (request.sessionId or request.userId or "default").strip()
        if session_key not in _session_histories:
            _session_histories[session_key] = []

        chat_history = _session_histories[session_key]

        # 1. Retrieve relevant context from Knowledge Base
        context_docs = get_knowledge_base().search(request.message, n_results=2)
        if context_docs:
            logger.debug(f"Found {len(context_docs)} context docs")
        else:
            logger.debug("No context docs found")

        # 2. Generate response with RAG context
        response_text = ai_engine.generate_response(
            request.message,
            context_docs,
            chat_history=chat_history,
            show_thinking=False,
        )
        logger.info(f"Response generated: {len(response_text)} chars")

        chat_history.append({"role": "user", "content": request.message})
        chat_history.append({"role": "assistant", "content": response_text})
        if len(chat_history) > 20:
            _session_histories[session_key] = chat_history[-20:]
        
        return {
            "reply": response_text,
            "context_used": len(context_docs),
            "status": "success"
        }
    except Exception as e:
        logger.exception(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    port = SERVER_PORT
    logger.info(f"🚀 Starting Collective AI on http://0.0.0.0:{port}")
    if DEBUG_MODE:
        logger.warning("⚠️  DEBUG MODE ENABLED - Not for production!")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
