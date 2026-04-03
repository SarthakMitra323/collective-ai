import os
from dotenv import load_dotenv

load_dotenv()

# ============= SECURITY: NEVER expose tokens in code =============
HF_TOKEN = os.getenv("HF_TOKEN", "")  
if not HF_TOKEN:
    import warnings
    warnings.warn("HF_TOKEN not set. AI features will be unavailable.")

HF_MODEL = os.getenv("HF_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")
HF_PROVIDER = os.getenv("HF_PROVIDER", "").strip()
REMOTE_LLM = True

max_response_length_env = os.getenv("MAX_RESPONSE_LENGTH", "").strip()
MAX_RESPONSE_LENGTH = int(max_response_length_env) if max_response_length_env else None

request_timeout_env = os.getenv("REQUEST_TIMEOUT", "").strip()
REQUEST_TIMEOUT = float(request_timeout_env) if request_timeout_env else None
chat_timeout_env = os.getenv("CHAT_TIMEOUT_SECONDS", "").strip()
CHAT_TIMEOUT_SECONDS = float(chat_timeout_env) if chat_timeout_env else 80.0
rag_timeout_env = os.getenv("RAG_TIMEOUT_SECONDS", "").strip()
RAG_TIMEOUT_SECONDS = float(rag_timeout_env) if rag_timeout_env else 12.0
max_output_tokens_env = os.getenv("MAX_OUTPUT_TOKENS", "").strip()
MAX_OUTPUT_TOKENS = int(max_output_tokens_env) if max_output_tokens_env else 224
SUPPRESS_HF_LOGS = True  

# ============= RAG Configuration =============
DB_PATH = os.getenv("DB_PATH", "./collective_memory.db")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  
MAX_CONTEXT_DOCS = 3
MAX_DOCUMENT_LENGTH = 10000  
VECTOR_DIMENSION = int(os.getenv("VECTOR_DIMENSION", "384"))

# Pinecone (managed vector DB for production-safe persistence)
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "collective-ai-rag")
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

# ============= Server Configuration =============
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "https://collective-ai.vercel.app").split(",")
ALLOWED_ORIGIN_REGEX = os.getenv(
    "ALLOWED_ORIGIN_REGEX",
    r"^https://([a-z0-9-]+\.)*vercel\.app$",
)
SERVER_PORT = int(os.getenv("PORT", 3000))
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"

# ============= Validation =============
assert HF_MODEL, "HF_MODEL must be set"
assert SERVER_PORT > 0 and SERVER_PORT < 65536, "Invalid PORT"
