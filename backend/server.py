from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from LLM import CollectiveModel
from rag import KnowledgeBase

app = FastAPI(title="Collective AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Initialize Systems ---
print("⏳ Booting up Neural Core & Memory...")
ai_engine = CollectiveModel()
knowledge_base = KnowledgeBase() # Loads Vector DB
print("✅ Collective AI Online")

# --- Schemas ---
class ChatRequest(BaseModel):
    message: str
    sessionId: str | None = None
    userId: str | None = None

class ContributionRequest(BaseModel):
    text: str
    userId: str | None = None

@app.get("/")
def home():
    return {"status": "Collective AI Server Running"}

# --- Endpoint: Contribution (Add to Vector DB) ---
@app.post("/api/contribute")
async def contribute_endpoint(request: ContributionRequest):
    if not request.text:
        raise HTTPException(status_code=400, detail="Content cannot be empty")
    
    success = knowledge_base.add_document(request.text, user_id=request.userId or "anon")
    
    if success:
        return {"status": "success", "message": "Knowledge assimilated into the Collective."}
    else:
        raise HTTPException(status_code=400, detail="Content too short or invalid")

# --- Endpoint: Chat (RAG Workflow) ---
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    if not request.message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    print(f"📩 Received: {request.message}")
    
    try:
        # 1. Retrieve relevant context from Vector DB
        context_docs = knowledge_base.search(request.message, n_results=2)
        if context_docs:
            print(f"📚 Retrieved {len(context_docs)} context fragments.")

        # 2. Generate response with context
        response_text = ai_engine.generate_response(request.message, context_docs)
        
        return {"reply": response_text}
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail="Internal AI Error")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)