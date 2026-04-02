import os
import asyncio
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

# CORS with origin normalization (avoids mismatch from trailing slashes/spaces)
allowed_origins = [origin.strip().rstrip("/") for origin in ALLOWED_ORIGIN if origin.strip()]
if not allowed_origins:
    allowed_origins = ["https://collective-ai.vercel.app"]

allow_all_origins = "*" in allowed_origins
if allow_all_origins:
    logger.warning("CORS: Allow All Origins (not recommended for production)")
else:
    logger.info(f"CORS: Restricted to {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if not allow_all_origins else ["*"],
    allow_credentials=not allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy-load model and knowledge base
logger.info("Initializing Collective AI Backend...")
ai_engine = None
_knowledge_base = None
_session_histories: dict[str, list[dict[str, str]]] = {}

def get_ai_engine():
    global ai_engine
    if ai_engine is None:
        ai_engine = CollectiveModel()
    return ai_engine

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
            "memory_stats": "GET /api/stats",
            "health": "GET /api/health"
        }
    }

@app.get("/api/health")
async def health_check():
    """Detailed health check for debugging startup issues."""
    import sys
    health = {
        "status": "ok",
        "services": {
            "llm": "⚠️ unchecked",
            "rag": "⚠️ unchecked",
            "pinecone": "⚠️ unchecked",
        },
        "errors": [],
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
    }
    
    # Check LLM
    try:
        engine = get_ai_engine()
        if engine.client or engine._init_error is not None:
            if engine.client:
                health["services"]["llm"] = "✅ ready"
            else:
                llm_error = engine._init_error or "unknown error"
                health["services"]["llm"] = f"❌ {llm_error[:60]}"
                health["errors"].append(f"LLM init failed: {llm_error}"
                )
                health["status"] = "degraded"
        else:
            health["services"]["llm"] = "✅ ready"
    except Exception as e:
        health["services"]["llm"] = f"❌ error: {str(e)[:60]}"
        health["errors"].append(f"LLM error: {e}")
        health["status"] = "degraded"
    
    # Check RAG/Pinecone
    try:
        kb = get_knowledge_base()
        if kb._init_error:
            health["services"]["rag"] = f"❌ {kb._init_error[:60]}"
            health["services"]["pinecone"] = f"❌ {kb._init_error[:60]}"
            health["errors"].append(f"Pinecone init failed: {kb._init_error}")
            health["status"] = "degraded"
        else:
            # Try to query count
            try:
                doc_count = kb.count()
                health["services"]["rag"] = f"✅ ready ({doc_count} docs)"
                health["services"]["pinecone"] = "✅ connected"
            except Exception as e:
                health["services"]["rag"] = f"⚠️ query error: {str(e)[:60]}"
                health["services"]["pinecone"] = f"⚠️ query error: {str(e)[:60]}"
                health["errors"].append(f"RAG query error: {e}")
                health["status"] = "degraded"
    except Exception as e:
        health["services"]["rag"] = f"❌ load error: {str(e)[:60]}"
        health["services"]["pinecone"] = f"❌ load error: {str(e)[:60]}"
        health["errors"].append(f"RAG load error: {e}")
        health["status"] = "degraded"
    
    return health

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
        engine = get_ai_engine()
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
        response_text = await asyncio.wait_for(
            asyncio.to_thread(
                engine.generate_response,
                request.message,
                context_docs,
                chat_history,
                False,
            ),
            timeout=45,
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
    except TimeoutError:
        logger.warning("Chat generation timed out after 45s")
        raise HTTPException(status_code=504, detail="AI response timed out")
    except Exception as e:
        logger.exception(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    port = SERVER_PORT
    logger.info(f"🚀 Starting Collective AI on http://0.0.0.0:{port}")
    if DEBUG_MODE:
        logger.warning("⚠️  DEBUG MODE ENABLED - Not for production!")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
