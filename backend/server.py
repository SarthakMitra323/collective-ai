import os
import asyncio
import threading
from fastapi import FastAPI, HTTPException #type:ignore
from fastapi.middleware.cors import CORSMiddleware  #type:ignore
from pydantic import BaseModel
import uvicorn # type:ignore
import logging
from fastapi.responses import StreamingResponse  # type:ignore

try:
    from .LLM import CollectiveModel
    from .config import (
        ALLOWED_ORIGIN,
        ALLOWED_ORIGIN_REGEX,
        SERVER_PORT,
        DEBUG_MODE,
        WARMUP_LLM_ON_STARTUP,
        WARMUP_LLM_TIMEOUT_SECONDS,
        CHAT_TIMEOUT_SECONDS,
        RAG_TIMEOUT_SECONDS,
    )
except ImportError:
    from LLM import CollectiveModel
    from config import (
        ALLOWED_ORIGIN,
        ALLOWED_ORIGIN_REGEX,
        SERVER_PORT,
        DEBUG_MODE,
        WARMUP_LLM_ON_STARTUP,
        WARMUP_LLM_TIMEOUT_SECONDS,
        CHAT_TIMEOUT_SECONDS,
        RAG_TIMEOUT_SECONDS,
    )

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Collective AI Backend",
    description="RAG-powered AI with Groq API",
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
    logger.info(f"CORS: Restricted to {allowed_origins} (regex={ALLOWED_ORIGIN_REGEX})")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if not allow_all_origins else ["*"],
    allow_origin_regex=None if allow_all_origins else ALLOWED_ORIGIN_REGEX,
    allow_credentials=not allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Explicit OPTIONS handler for CORS preflight
@app.api_route("/api/{path:path}", methods=["OPTIONS"])
async def options_handler(path: str):
    return {"status": "ok"}

# Lazy-load model and knowledge base
logger.info("Initializing Collective AI Backend...")
ai_engine = None
_knowledge_base = None
_session_histories: dict[str, list[dict[str, str]]] = {}
_startup_ready = threading.Event()
_startup_error: str | None = None


def _startup_initialize_blocking():
    global _startup_error
    try:
        logger.info("Starting eager startup initialization...")
        engine = get_ai_engine()
        # Eagerly initialize Groq client so first web request is not cold.
        engine._init_client()
        if WARMUP_LLM_ON_STARTUP:
            engine.warmup()
        logger.info("Warming RAG embedder and Pinecone connection...")
        kb = get_knowledge_base()
        _ = kb.embedder
        _ = kb.count()
        logger.info("Startup initialization completed")
    except Exception as e:
        _startup_error = str(e)
        logger.warning(f"Startup initialization failed: {e}")
    finally:
        # Keep the service routable even if warmup or external dependencies fail.
        _startup_ready.set()


@app.on_event("startup")
async def warmup_on_startup():
    _startup_ready.set()
    app.state.startup_task = asyncio.create_task(asyncio.to_thread(_startup_initialize_blocking))


@app.api_route("/api/ready", methods=["GET", "HEAD"])
async def ready_check():
    if _startup_ready.is_set():
        detail = {"status": "ready"}
        if _startup_error:
            detail["warning"] = _startup_error[:200]
            detail["status"] = "ready_with_warnings"
        return detail
    detail = {"status": "warming"}
    if _startup_error:
        detail["error"] = _startup_error[:200]
    raise HTTPException(status_code=503, detail=detail)

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
    stream: bool = False

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

@app.api_route("/", methods=["GET", "HEAD"])
def home():
    return {
        "status": "Collective AI Server Running",
        "docs_url": "/docs",
        "endpoints": {
            "chat": "POST /api/chat",
            "contribute": "POST /api/contribute",
            "search": "POST /api/search",
            "memory_stats": "GET /api/stats",
            "health": "GET /api/health",
            "healthz": "GET /healthz",
        },
    }


@app.api_route("/healthz", methods=["GET", "HEAD"])
async def healthz_check():
    return await ready_check()


@app.api_route("/api/test", methods=["GET", "HEAD", "OPTIONS"])
async def test_endpoint():
    """Simple connectivity test endpoint (no streaming, no heavy deps)."""
    return {"status": "backend_alive", "timestamp": asyncio.get_running_loop().time()}


@app.api_route("/api/health", methods=["GET", "HEAD"])
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
        # Wrap in timeout to prevent hanging requests
        start_time = asyncio.get_running_loop().time()
        engine = get_ai_engine()
        session_key = (request.sessionId or request.userId or "default").strip()
        if session_key not in _session_histories:
            _session_histories[session_key] = []

        chat_history = _session_histories[session_key]

        # 1. Retrieve relevant context from Knowledge Base with timeout
        try:
            context_docs = await asyncio.wait_for(
                asyncio.to_thread(
                    get_knowledge_base().search,
                    request.message,
                    2,
                ),
                timeout=RAG_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            logger.warning(f"RAG search timed out after {RAG_TIMEOUT_SECONDS}s")
            context_docs = []
        
        after_rag = asyncio.get_running_loop().time()
        if context_docs:
            logger.debug(f"Found {len(context_docs)} context docs")
        else:
            logger.debug("No context docs found or RAG timed out")

        if request.stream:
            def stream_reply():
                response_parts: list[str] = []
                try:
                    for token in engine.stream_response(request.message, context_docs, chat_history):
                        response_parts.append(token)
                        yield token
                finally:
                    response_text = engine._finalize_response_text("".join(response_parts))
                    if response_text:
                        chat_history.append({"role": "user", "content": request.message})
                        chat_history.append({"role": "assistant", "content": response_text})
                        if len(chat_history) > 20:
                            _session_histories[session_key] = chat_history[-20:]
                        else:
                            _session_histories[session_key] = chat_history
                        logger.info(f"Streamed response generated: {len(response_text)} chars")

            return StreamingResponse(stream_reply(), media_type="text/plain; charset=utf-8")

        # 2. Generate response with timeout protection
        try:
            response_text = await asyncio.wait_for(
                asyncio.to_thread(
                    engine.generate_response,
                    request.message,
                    context_docs,
                    chat_history,
                    False,
                ),
                timeout=CHAT_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            logger.error(f"Chat generation timed out after {CHAT_TIMEOUT_SECONDS}s")
            raise HTTPException(status_code=504, detail="Chat generation timeout - please try again")
        
        after_llm = asyncio.get_running_loop().time()
        logger.info(f"Response generated: {len(response_text)} chars")
        logger.info(
            "Timing | rag=%.2fs llm=%.2fs total=%.2fs",
            after_rag - start_time,
            after_llm - after_rag,
            after_llm - start_time,
        )

        chat_history.append({"role": "user", "content": request.message})
        chat_history.append({"role": "assistant", "content": response_text})
        if len(chat_history) > 20:
            _session_histories[session_key] = chat_history[-20:]
        
        return {
            "reply": response_text,
            "context_used": len(context_docs),
            "status": "success"
        }
    except asyncio.TimeoutError:
        logger.error("Chat request exceeded timeout")
        raise HTTPException(status_code=504, detail="Request timeout")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    port = SERVER_PORT
    logger.info(f"🚀 Starting Collective AI on http://0.0.0.0:{port}")
    if DEBUG_MODE:
        logger.warning("⚠️  DEBUG MODE ENABLED - Not for production!")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
