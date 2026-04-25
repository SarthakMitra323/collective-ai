import os
import asyncio
import threading
import hashlib
import re
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request #type:ignore
from fastapi.middleware.cors import CORSMiddleware  #type:ignore
from pydantic import BaseModel, Field
import uvicorn # type:ignore
import logging
from fastapi.responses import StreamingResponse  # type:ignore
from fastapi.responses import JSONResponse  # type:ignore
from starlette.middleware.trustedhost import TrustedHostMiddleware  # type:ignore

try:
    from .LLM import CollectiveModel
    from .config import (
        ALLOWED_ORIGIN,
        ALLOWED_ORIGIN_REGEX,
        SERVER_PORT,
        DEBUG_MODE,
        WARMUP_LLM_ON_STARTUP,
        WARMUP_RAG_ON_STARTUP,
        WARMUP_LLM_TIMEOUT_SECONDS,
        CHAT_TIMEOUT_SECONDS,
        RAG_TIMEOUT_SECONDS,
        ENABLE_RAG,
        MAX_ACTIVE_SESSIONS,
        MAX_HISTORY_TURNS,
        MAX_MESSAGE_CHARS,
        MAX_SESSION_ID_CHARS,
        RATE_LIMIT_WINDOW_SECONDS,
        RATE_LIMIT_MAX_REQUESTS,
        ENFORCE_BROWSER_ORIGIN_CHECK,
        TRUSTED_HOSTS,
    )
except ImportError:
    from LLM import CollectiveModel
    from config import (
        ALLOWED_ORIGIN,
        ALLOWED_ORIGIN_REGEX,
        SERVER_PORT,
        DEBUG_MODE,
        WARMUP_LLM_ON_STARTUP,
        WARMUP_RAG_ON_STARTUP,
        WARMUP_LLM_TIMEOUT_SECONDS,
        CHAT_TIMEOUT_SECONDS,
        RAG_TIMEOUT_SECONDS,
        ENABLE_RAG,
        MAX_ACTIVE_SESSIONS,
        MAX_HISTORY_TURNS,
        MAX_MESSAGE_CHARS,
        MAX_SESSION_ID_CHARS,
        RATE_LIMIT_WINDOW_SECONDS,
        RATE_LIMIT_MAX_REQUESTS,
        ENFORCE_BROWSER_ORIGIN_CHECK,
        TRUSTED_HOSTS,
    )

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Lazy-load model and knowledge base
logger.info("Initializing Collective AI Backend...")
ai_engine = None
_knowledge_base = None
_session_histories: dict[str, list[dict[str, str]]] = {}
_startup_ready = threading.Event()
_startup_error: str | None = None
_rate_limit_hits: dict[str, list[float]] = {}
_rate_limit_lock = threading.Lock()
_SESSION_KEY_PATTERN = re.compile(rf"^[A-Za-z0-9_.:-]{{1,{MAX_SESSION_ID_CHARS}}}$")
_MAX_TRACKED_RATE_LIMIT_CLIENTS = 5000


@asynccontextmanager
async def lifespan(app: FastAPI):
    _startup_ready.clear()
    app.state.startup_task = asyncio.create_task(asyncio.to_thread(_startup_initialize_blocking))
    try:
        yield
    finally:
        startup_task = getattr(app.state, "startup_task", None)
        if startup_task and not startup_task.done():
            startup_task.cancel()


app = FastAPI(
    title="Collective AI Backend",
    description="RAG-powered AI with Groq API",
    docs_url="/docs" if DEBUG_MODE else None,
    lifespan=lifespan,
)

if TRUSTED_HOSTS:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=TRUSTED_HOSTS)

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

try:
    _allowed_origin_regex_pattern = re.compile(ALLOWED_ORIGIN_REGEX) if ALLOWED_ORIGIN_REGEX else None
except re.error:
    logger.warning("Invalid ALLOWED_ORIGIN_REGEX. Regex-based origin checks disabled.")
    _allowed_origin_regex_pattern = None


def _origin_allowed(origin: str) -> bool:
    normalized_origin = origin.strip().rstrip("/")
    if not normalized_origin:
        return False
    if allow_all_origins:
        return True
    if normalized_origin in allowed_origins:
        return True
    if _allowed_origin_regex_pattern and _allowed_origin_regex_pattern.match(normalized_origin):
        return True
    return False


def _allow_chat_request(client_ip: str) -> bool:
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    with _rate_limit_lock:
        if len(_rate_limit_hits) > _MAX_TRACKED_RATE_LIMIT_CLIENTS:
            stale_clients = [
                key for key, values in _rate_limit_hits.items()
                if not values or values[-1] < cutoff
            ]
            for key in stale_clients[:1500]:
                _rate_limit_hits.pop(key, None)

        hits = _rate_limit_hits.setdefault(client_ip, [])
        fresh_hits = [ts for ts in hits if ts >= cutoff]
        if len(fresh_hits) >= RATE_LIMIT_MAX_REQUESTS:
            _rate_limit_hits[client_ip] = fresh_hits
            return False
        fresh_hits.append(now)
        _rate_limit_hits[client_ip] = fresh_hits
    return True


def _safe_session_key(raw_key: str | None) -> str:
    candidate = (raw_key or "").strip()
    if candidate and len(candidate) <= MAX_SESSION_ID_CHARS and _SESSION_KEY_PATTERN.match(candidate):
        return candidate

    if candidate:
        compact = re.sub(r"[^A-Za-z0-9_.:-]+", "-", candidate)[:MAX_SESSION_ID_CHARS]
        if compact and _SESSION_KEY_PATTERN.match(compact):
            return compact
        digest = hashlib.sha256(candidate.encode("utf-8", errors="ignore")).hexdigest()[:24]
        return f"sess-{digest}"

    return "default"


@app.middleware("http")
async def hardening_middleware(request: Request, call_next):
    path = request.url.path

    if path.startswith("/api/") and request.method != "OPTIONS":
        if ENFORCE_BROWSER_ORIGIN_CHECK:
            request_origin = request.headers.get("origin", "").strip()
            if request_origin and not _origin_allowed(request_origin):
                return JSONResponse(status_code=403, content={"detail": "Origin not allowed"})

        if path == "/api/chat":
            client_ip = request.client.host if request.client and request.client.host else "unknown"
            if not _allow_chat_request(client_ip):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many chat requests. Please slow down."},
                )

    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response

# Explicit OPTIONS handler for CORS preflight
@app.api_route("/api/{path:path}", methods=["OPTIONS"])
async def options_handler(path: str):
    return {"status": "ok"}

def _startup_initialize_blocking():
    global _startup_error
    try:
        logger.info("Starting eager startup initialization...")
        engine = get_ai_engine()
        # Eagerly initialize Groq client so first web request is not cold.
        engine._init_client()
        if WARMUP_LLM_ON_STARTUP:
            ex = threading.Event()
            warmup_error: list[Exception] = []

            def _warmup_call():
                try:
                    engine.warmup()
                except Exception as warm_e:
                    warmup_error.append(warm_e)
                finally:
                    ex.set()

            th = threading.Thread(target=_warmup_call, daemon=True)
            th.start()
            finished = ex.wait(timeout=WARMUP_LLM_TIMEOUT_SECONDS)
            if not finished:
                raise TimeoutError(f"LLM warmup timed out after {WARMUP_LLM_TIMEOUT_SECONDS:.0f}s")
            if warmup_error:
                raise warmup_error[0]
        if ENABLE_RAG and WARMUP_RAG_ON_STARTUP:
            logger.info("Warming RAG embedder and Pinecone connection...")
            kb = get_knowledge_base()
            _ = kb.embedder
            _ = kb.count()
        elif not ENABLE_RAG:
            logger.info("RAG disabled by configuration (ENABLE_RAG=false)")
        else:
            logger.info("Skipping RAG warmup (WARMUP_RAG_ON_STARTUP=false)")
        logger.info("Startup initialization completed")
    except Exception as e:
        _startup_error = str(e)
        logger.warning(f"Startup initialization failed: {e}")
    finally:
        # Keep the service routable even if warmup or external dependencies fail.
        _startup_ready.set()


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


def _search_knowledge_base(query_text: str, n_results: int):
    """Run KB initialization + search off the event loop thread."""
    return get_knowledge_base().search(query_text, n_results)

# --- Schemas ---
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    sessionId: str | None = Field(default=None, max_length=MAX_SESSION_ID_CHARS)
    userId: str | None = Field(default=None, max_length=MAX_SESSION_ID_CHARS)
    stream: bool = False

class ContributionRequest(BaseModel):
    content: str | None = Field(default=None, max_length=50000)  # From HTML form
    text: str | None = Field(default=None, max_length=50000)      # Alternative field name
    title: str | None = Field(default=None, max_length=160)     # Optional: contribution title
    userId: str | None = Field(default=None, max_length=MAX_SESSION_ID_CHARS)
    
    def get_text(self):
        """Get text from either 'content' or 'text' field"""
        return (self.content or self.text or "").strip()

class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    n_results: int = Field(default=3, ge=1, le=8)

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
    if not ENABLE_RAG:
        return {
            "total_documents": 0,
            "embedding_model": "disabled",
            "backend": "disabled",
            "status": "rag_disabled",
        }
    return {
        "total_documents": get_knowledge_base().count(),
        "embedding_model": "all-MiniLM-L6-v2",
        "backend": "Pinecone"
    }

@app.post("/api/contribute")
async def contribute_endpoint(request: ContributionRequest):
    """Add knowledge to the collective memory (from HTML form or API)"""
    if not ENABLE_RAG:
        raise HTTPException(status_code=503, detail="Knowledge contributions are temporarily disabled")
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
    if not ENABLE_RAG:
        return {
            "query": request.query,
            "results": [],
            "count": 0,
            "status": "rag_disabled",
        }
    if not request.query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    results = get_knowledge_base().search(request.query, n_results=request.n_results)
    
    return {
        "query": request.query,
        "results": results,
        "count": len(results)
    }

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest, http_request: Request):
    """Chat with Collective AI using RAG"""
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    client_request_id = http_request.headers.get("x-client-request-id", "")
    request_origin = http_request.headers.get("origin", "")
    if client_request_id:
        logger.info(
            "Chat request trace_id=%s session=%s origin=%s",
            client_request_id,
            request.sessionId,
            request_origin or "(none)",
        )
    else:
        logger.info(
            "Chat request session=%s origin=%s",
            request.sessionId,
            request_origin or "(none)",
        )
    
    try:
        # Wrap in timeout to prevent hanging requests
        start_time = asyncio.get_running_loop().time()
        engine = get_ai_engine()
        session_key = _safe_session_key(request.sessionId or request.userId)
        if session_key not in _session_histories:
            if len(_session_histories) >= MAX_ACTIVE_SESSIONS:
                # Evict oldest session to avoid unbounded memory growth.
                oldest_key = next(iter(_session_histories))
                _session_histories.pop(oldest_key, None)
            _session_histories[session_key] = []

        chat_history = _session_histories[session_key]

        # 1. Retrieve relevant context from Knowledge Base with timeout
        if ENABLE_RAG:
            try:
                context_docs = await asyncio.wait_for(
                    asyncio.to_thread(
                        _search_knowledge_base,
                        request.message,
                        2,
                    ),
                    timeout=RAG_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                logger.warning(f"RAG search timed out after {RAG_TIMEOUT_SECONDS}s")
                context_docs = []
            except Exception as rag_error:
                logger.warning(f"RAG unavailable for this request: {rag_error}")
                context_docs = []
        else:
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
                        _session_histories[session_key] = chat_history[-MAX_HISTORY_TURNS:]
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
        _session_histories[session_key] = chat_history[-MAX_HISTORY_TURNS:]
        
        return {
            "reply": response_text,
            "context_used": len(context_docs),
            "status": "success",
            "request_id": client_request_id,
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