import os
from dotenv import load_dotenv

load_dotenv()

# ============= SECURITY: NEVER expose tokens in code =============
HF_TOKEN = os.getenv("HF_TOKEN", "")  # Must be set in .env
if not HF_TOKEN:
    import warnings
    warnings.warn("HF_TOKEN not set. AI features will be unavailable.")

HF_MODEL = os.getenv("HF_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")
HF_PROVIDER = os.getenv("HF_PROVIDER", "featherless-ai")
REMOTE_LLM = True

# Production-ready settings
# Mistral-7B-Instruct-v0.2: commonly available via HF Inference Providers
# Uses HuggingFace InferenceClient.text_generation() method
max_response_length_env = os.getenv("MAX_RESPONSE_LENGTH", "").strip()
MAX_RESPONSE_LENGTH = int(max_response_length_env) if max_response_length_env else None

request_timeout_env = os.getenv("REQUEST_TIMEOUT", "").strip()
REQUEST_TIMEOUT = float(request_timeout_env) if request_timeout_env else None
SUPPRESS_HF_LOGS = True  # Hide HuggingFace library spam

# ============= RAG Configuration =============
DB_PATH = os.getenv("DB_PATH", "./collective_memory.db")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Lightweight embeddings
MAX_CONTEXT_DOCS = 3
MAX_DOCUMENT_LENGTH = 5000  # Prevent huge documents
VECTOR_DIMENSION = int(os.getenv("VECTOR_DIMENSION", "384"))

# Pinecone (managed vector DB for production-safe persistence)
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "collective-ai-rag")
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

# ============= Server Configuration =============
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "*").split(",")
SERVER_PORT = int(os.getenv("PORT", 3000))
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"

# ============= Validation =============
assert HF_MODEL, "HF_MODEL must be set"
assert SERVER_PORT > 0 and SERVER_PORT < 65536, "Invalid PORT"
