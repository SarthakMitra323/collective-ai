import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from LLM import CollectiveModel
from rag import KnowledgeBase
 
app = FastAPI(title="Collective AI Backend")
 
# ALLOWED_ORIGIN env var set in Render dashboard / render.yaml
# Defaults to your Vercel domain — update before deploying
origin = os.environ.get("ALLOWED_ORIGIN", "https://collective-ai.vercel.app")
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin, "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
 
print(f"CORS: Allowing requests from {origin}")
 
# ── Initialize Systems ──
print("Booting Neural Core & Memory…")
ai_engine     = CollectiveModel()
knowledge_base = KnowledgeBase()
print("Collective AI Online")
 
# ── Schemas ──
class ChatRequest(BaseModel):
    message:   str
    sessionId: str | None = None
    userId:    str | None = None
 
class ContributionRequest(BaseModel):
    id:       str | None = None
    title:    str | None = None
    category: str | None = None
    content:  str
    tags:     list[str] | None = None
    userId:   str | None = None
    mode:     str | None = None
 
# ── Routes ──
@app.get("/")
def home():
    return {"status": "Collective AI running", "docs": "/docs"}
 
@app.get("/health")
def health():
    """Used by uptime.html to check backend status."""
    return {"status": "ok"}
 
@app.post("/api/contribute")
async def contribute_endpoint(request: ContributionRequest):
    if not request.content:
        raise HTTPException(status_code=400, detail="Content cannot be empty")
 
    print(f"Contribution from user: {request.userId}")
    success = knowledge_base.add_document(
        request.content,
        user_id=request.userId or "anon",
        source=request.title or "contribution"
    )
 
    if success:
        return {"status": "success", "message": "Knowledge added to Collective."}
    raise HTTPException(status_code=400, detail="Content too short or invalid")
 
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    if not request.message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
 
    print(f"Chat: {request.message[:60]}… (session: {request.sessionId})")
 
    try:
        context_docs  = knowledge_base.search(request.message, n_results=2)
        response_text = ai_engine.generate_response(request.message, context_docs)
        return {"reply": response_text}
    except Exception as e:
        print(f"Server error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
 
# ── Local dev only ──
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))   # fixed: was 3000
    print(f"Starting on port {port}…")
    uvicorn.run(app, host="0.0.0.0", port=port)
    
