from groq import Groq  # type:ignore
import sys
import logging
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import re

SYSTEM_PROMPT = "You are Collective AI. Answer clearly and concisely using only the necessary context."

try:
    from .config import GROQ_API_KEY, GROQ_MODEL, GROQ_FALLBACK_MODEL, REQUEST_TIMEOUT, DEBUG_MODE, SUPPRESS_HF_LOGS
except ImportError:
    from config import GROQ_API_KEY, GROQ_MODEL, GROQ_FALLBACK_MODEL, REQUEST_TIMEOUT, DEBUG_MODE, SUPPRESS_HF_LOGS

if SUPPRESS_HF_LOGS:
    logging.getLogger("groq").setLevel(logging.CRITICAL)
    logging.getLogger("transformers").setLevel(logging.CRITICAL)
    logging.getLogger("sentence_transformers").setLevel(logging.CRITICAL)

logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.WARNING,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CollectiveModel:

    @staticmethod
    def _inference_timeout_seconds() -> Optional[float]:
        try:
            return float(REQUEST_TIMEOUT) if REQUEST_TIMEOUT else None
        except Exception:
            return None

    def _run_with_timeout(self, fn, *args):
        timeout_s = self._inference_timeout_seconds()
        if timeout_s is None:
            return fn(*args)
        ex = ThreadPoolExecutor(max_workers=1)
        future = ex.submit(fn, *args)
        try:
            return future.result(timeout=timeout_s)
        except FuturesTimeoutError as e:
            future.cancel()
            raise TimeoutError(f"Inference timed out after {timeout_s:.0f}s") from e
        finally:
            ex.shutdown(wait=False, cancel_futures=True)

    @staticmethod
    def _extract_message_text(message_obj) -> str:
        """Best-effort extraction for provider-specific chat payload shapes."""
        if message_obj is None:
            return ""

        content = getattr(message_obj, "content", None)
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, str) and item.strip():
                    parts.append(item.strip())
                elif isinstance(item, dict):
                    txt = str(item.get("text", "")).strip()
                    if txt:
                        parts.append(txt)
            if parts:
                return "\n".join(parts)

        # Never surface reasoning fields to users; use final answer content only.
        for attr in ("text",):
            val = getattr(message_obj, attr, None)
            if isinstance(val, str) and val.strip():
                return val.strip()

        return ""

    @staticmethod
    def _remove_repeated_paragraphs(text: str) -> str:
        """Remove duplicate paragraphs while preserving order."""
        parts = [p.strip() for p in text.split("\n\n") if p.strip()]
        seen = set()
        unique_parts: List[str] = []
        for part in parts:
            key = " ".join(part.lower().split())
            if key in seen:
                continue
            seen.add(key)
            unique_parts.append(part)
        return "\n\n".join(unique_parts) if unique_parts else text.strip()

    def __init__(self):
        self.client = None
        self.primary_model = GROQ_MODEL
        self.model = GROQ_MODEL
        self.fallback_model = GROQ_FALLBACK_MODEL if GROQ_FALLBACK_MODEL else None
        self._init_error = None
        if not GROQ_API_KEY:
            self._init_error = "GROQ_API_KEY not configured"
            logger.error(self._init_error)
            return

    def _init_client(self):
        """Initialize the Groq client lazily on first generation."""
        if self.client is not None:
            return self.client

        if self._init_error:
            raise RuntimeError(self._init_error)

        if not GROQ_API_KEY:
            self._init_error = "GROQ_API_KEY not configured"
            raise RuntimeError(self._init_error)

        try:
            self.client = Groq(api_key=GROQ_API_KEY, timeout=REQUEST_TIMEOUT)
            logger.info("LLM initialized: %s", self._resolved_model(self.primary_model))
            return self.client
        except Exception as e:
            self._init_error = str(e)
            logger.exception("Failed to initialize Groq client")
            raise RuntimeError(f"Failed to initialize Groq client: {e}")

    def _resolved_model(self, model: Optional[str] = None) -> str:
        return model or self.model

    @staticmethod
    def _build_prompt(
        user_input: str,
        context_docs: Optional[List[str]] = None
    ) -> str:
        context_section = ""
        if context_docs and len(context_docs) > 0:
            context_section = "\nContext:\n"
            for i, doc in enumerate(context_docs[:2], 1):
                doc_preview = doc[:120] + ("..." if len(doc) > 120 else "")
                context_section += f"{i}. {doc_preview}\n"
        
        prompt = f"{context_section}Question: {user_input}"
        return prompt

    def _build_messages(
        self,
        user_input: str,
        context_docs: Optional[List[str]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, str]]:
        # Build chat-completion messages with short memory window.
        messages: List[Dict[str, str]] = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            }
        ]

        for msg in (chat_history or [])[-4:]:
            role = msg.get("role", "")
            content = msg.get("content", "").strip()
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        messages.append({
            "role": "user",
            "content": self._build_prompt(user_input, context_docs),
        })
        return messages



    def _call_chat_completion(
        self,
        client,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
    ) -> str:
        chat_kwargs: Dict[str, object] = {
            "model": self._resolved_model(model),
            "messages": messages,
            "temperature": 0.3,
        }
        out = client.chat.completions.create(**chat_kwargs)
        choices = getattr(out, "choices", None) or []
        if not choices:
            return ""
        message_obj = getattr(choices[0], "message", None)
        extracted = self._extract_message_text(message_obj)
        if extracted:
            return extracted
        return ""

    def _stream_chat_completion(
        self,
        client,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
    ):
        chat_kwargs: Dict[str, object] = {
            "model": self._resolved_model(model),
            "messages": messages,
            "temperature": 0.3,
            "stream": True,
        }

        stream = client.chat.completions.create(**chat_kwargs)
        for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            text = getattr(delta, "content", None)
            if isinstance(text, str) and text:
                yield text

    def _call_text_generation(self, messages: List[Dict[str, str]]) -> str:
        """Call Groq chat completion with model fallback."""
        client = self._init_client()
        candidate_models = [self.primary_model]
        if self.fallback_model and self.fallback_model != self.primary_model:
            candidate_models.append(self.fallback_model)

        last_error: Optional[Exception] = None
        for candidate in candidate_models:
            try:
                return self._run_with_timeout(
                    self._call_chat_completion,
                    client,
                    messages,
                    candidate,
                )
            except Exception as e:
                last_error = e
                logger.warning("Model call failed for '%s': %s", candidate, e)
                continue

        if last_error:
            raise last_error

        raise RuntimeError("No Groq model could produce a response.")

    def warmup(self) -> None:
        """Prime the provider/model with a tiny request after deployment."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Reply with one word: ready"},
        ]
        response = self._call_text_generation(messages)
        if not response:
            raise RuntimeError("Warmup produced empty response")

    def stream_response(
        self,
        user_input: str,
        context_docs: Optional[List[str]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ):
        """Yield streamed response tokens from Groq."""
        if not isinstance(user_input, str) or not user_input.strip():
            raise ValueError("Please provide a valid question.")

        user_input = user_input.strip()
        context_docs = context_docs or []
        messages = self._build_messages(user_input, context_docs, chat_history)
        client = self._init_client()

        candidate_models = [self.primary_model]
        if self.fallback_model and self.fallback_model != self.primary_model:
            candidate_models.append(self.fallback_model)

        last_error: Optional[Exception] = None
        for candidate in candidate_models:
            try:
                for token in self._stream_chat_completion(client, messages, candidate):
                    yield token
                return
            except Exception as e:
                last_error = e
                logger.warning("Streaming model call failed for '%s': %s", candidate, e)
                continue

        if last_error:
            raise last_error

        raise RuntimeError("No Groq model could produce a streamed response.")

    @staticmethod
    def _finalize_response_text(response_text: str) -> str:
        original = (response_text or "").strip()
        response_text = original.replace("<think>", "").replace("</think>", "").strip()

        # If provider returns Thought/Answer style text, keep only the final answer.
        answer_match = re.search(r"(?:^|\n)\s*(?:final\s+answer|answer)\s*:\s*(.+)$", response_text, re.IGNORECASE | re.DOTALL)
        if answer_match:
            response_text = answer_match.group(1).strip()

        if response_text.startswith("Assistant:"):
            response_text = response_text[len("Assistant:"):].strip()
        if response_text.startswith("User question:"):
            response_text = response_text[len("User question:"):].strip()
        if response_text.startswith("Question:"):
            response_text = response_text[len("Question:"):].strip()
        for marker in ["\nUser:", "\nAssistant:", "\n[INST]", "</s>"]:
            if marker in response_text:
                response_text = response_text.split(marker, 1)[0].strip()

        cleaned = CollectiveModel._remove_repeated_paragraphs(response_text)
        return cleaned or response_text.strip() or original

    def generate_response(
        self,
        user_input: str,
        context_docs: Optional[List[str]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        show_thinking: bool = True
    ) -> str:
        """Generate response using Groq chat completions.
        
        Args:
            user_input: User query
            context_docs: Optional RAG context
            show_thinking: Whether to print thinking indicators
            
        Returns:
            str: Generated response
        """
        try:
            # Validate input
            if not isinstance(user_input, str) or not user_input.strip():
                return "❌ Please provide a valid question."
            
            user_input = user_input.strip()
            context_docs = context_docs or []
            
            # Activity indicators for production feel
            if show_thinking:
                print("   🤔 Thinking...", end="", flush=True)
            
            # Format chat messages with context + history memory
            messages = self._build_messages(user_input, context_docs, chat_history)
            
            if show_thinking:
                print("\r✍️  Generating response...", end="", flush=True)
            
            response_text = self._call_text_generation(messages)
            
            # Clear thinking indicator
            if show_thinking:
                print("\r" + " " * 30 + "\r", end="", flush=True)
            
            response_text = self._finalize_response_text(response_text)

            # Safety retry: if cleanup produced empty text, regenerate once with no RAG/history.
            if not response_text:
                retry_messages = self._build_messages(user_input, [], [])
                retry_text = self._finalize_response_text(self._call_text_generation(retry_messages))
                if retry_text:
                    response_text = retry_text
            
            # Validate response
            if not response_text or not response_text.strip():
                return "I couldn't generate a response. Try again."
            
            return response_text.strip()
            
        except ValueError as e:
            if show_thinking:
                print("\r" + " " * 30 + "\r", end="", flush=True)
            logger.warning(f"ValueError: {e}")
            return "❌ Input error. Try again."
        except AttributeError as e:
            if show_thinking:
                print("\r" + " " * 30 + "\r", end="", flush=True)
            logger.error(f"AttributeError: {e}")
            return "❌ Groq client error. Update dependencies and retry."
        except TimeoutError as e:
            if show_thinking:
                print("\r" + " " * 30 + "\r", end="", flush=True)
            return "⏱️ Request timed out. Try again."
        except Exception as e:
            if show_thinking:
                print("\r" + " " * 30 + "\r", end="", flush=True)
            error_msg = str(e).lower()
            logger.error(f"Error: {type(e).__name__}: {e}")
            
            # Safe error messages
            if "rate_limit" in error_msg:
                return "⚠️ Rate limited. Wait a moment."
            elif "unauthorized" in error_msg:
                return "❌ Authentication failed."
            else:
                return "❌ Service error. Try again."


# --- Production Chatbot CLI ---
def interactive_chat(rag_system=None):
    """Production-ready interactive chatbot with clean output."""
    model = CollectiveModel()
    try:
        model._init_client()
    except Exception as e:
        print(f"❌ Cannot start chat: LLM not initialized ({e})")
        return
    
    # Lazy-load RAG silently
    def get_rag_system():
        nonlocal rag_system
        if rag_system is None:
            # Suppress all output during initialization
            import io
            from contextlib import redirect_stdout, redirect_stderr
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                from rag import KnowledgeBase
                rag_system = KnowledgeBase()
        return rag_system
    
    # Clean welcome
    print("\n" + "="*70)
    print("  💬 COLLECTIVE AI - CHAT")
    print("="*70)
    print("  Type 'help' for commands, 'exit' to quit\n")

    # Session memory: stores recent user/assistant turns.
    chat_history: List[Dict[str, str]] = []
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            # Commands
            if user_input.lower() == "help":
                print("\nAvailable commands:")
                print("  add <text>      - Save knowledge for future reference")
                print("  search <query>  - Search your knowledge base")
                print("  list            - Show recent knowledge")
                print("  exit            - Exit chat\n")
                continue
            
            if user_input.lower() in ["exit", "quit"]:
                print("\n👋 Goodbye!\n")
                break
            
            # RAG add command
            if user_input.startswith("add "):
                text = user_input[4:].strip()
                if len(text) < 10:
                    print("❌ Text too short (min 10 characters)\n")
                    continue
                print("   💾 Saving...", end="", flush=True)
                get_rag_system().add_document(text, user_id="cli_user")
                print("\r✅ Saved to knowledge base\n", flush=True)
                continue
            
            # RAG search command
            if user_input.startswith("search "):
                query = user_input[7:].strip()
                print("   🔍 Searching...", end="", flush=True)
                results = get_rag_system().search(query, n_results=3)
                print("\r" + " " * 30 + "\r", end="", flush=True)
                if results:
                    print(f"\nFound {len(results)} result{'s' if len(results) > 1 else ''}:")
                    for i, doc in enumerate(results, 1):
                        preview = doc[:100] + "..." if len(doc) > 100 else doc
                        print(f"  {i}. {preview}")
                else:
                    print("No results found.")
                print()
                continue
            
            # RAG list command
            if user_input == "list":
                docs = get_rag_system().list_documents(limit=5)
                if docs:
                    print(f"\nRecent knowledge ({len(docs)} items):")
                    for i, (doc_id, text, user_id, source, _) in enumerate(docs, 1):
                        preview = text[:60] + "..." if len(text) > 60 else text
                        print(f"  {i}. {preview}")
                else:
                    print("No knowledge saved yet.")
                print()
                continue
            
            # Regular chat with RAG context
            print()  # Newline before response
            context = get_rag_system().search(user_input, n_results=2)
            response = model.generate_response(
                user_input,
                context,
                chat_history=chat_history,
                show_thinking=True,
            )
            print(f"AI: {response}\n")

            chat_history.append({"role": "user", "content": user_input})
            chat_history.append({"role": "assistant", "content": response})
            if len(chat_history) > 20:
                chat_history = chat_history[-20:]
                
        except KeyboardInterrupt:
            print("\n\n👋 Chat interrupted.\n")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}\n")


# --- CLI for RAG Management ---
def rag_cli():
    """CLI for managing RAG knowledge base - production version."""
    # Suppress all output during RAG initialization
    import io
    from contextlib import redirect_stdout, redirect_stderr
    
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        from rag import KnowledgeBase
        kb = KnowledgeBase()
    
    print("\n" + "="*70)
    print("  📚 COLLECTIVE AI - KNOWLEDGE BASE")
    print("="*70)
    print("  Manage your knowledge base\n")
    
    while True:
        try:
            print("Options: 1=Add  2=Search  3=List  4=Delete  5=Chat  6=Exit")
            choice = input("Choose: ").strip()
            
            if choice == "1":
                print("  Enter document text:")
                text = input("  > ").strip()
                if len(text) < 10:
                    print("  ❌ Too short (min 10 chars)\n")
                    continue
                user_id = input("  User ID (or Enter for anonymous): ").strip() or "anonymous"
                print("  💾 Saving...", end="", flush=True)
                kb.add_document(text, user_id=user_id, source="cli")
                print("\r  ✅ Saved!\n", flush=True)
                
            elif choice == "2":
                query = input("  Search query: ").strip()
                print("  🔍 Searching...", end="", flush=True)
                results = kb.search(query, n_results=3)
                print("\r" + " " * 30 + "\r", end="", flush=True)
                if results:
                    print(f"  Found {len(results)} result{'s' if len(results) > 1 else ''}:")
                    for i, doc in enumerate(results, 1):
                        print(f"    {i}. {doc[:100]}...")
                else:
                    print("  No results found.")
                print()
                
            elif choice == "3":
                docs = kb.list_documents(limit=5)
                if docs:
                    print(f"  Recent knowledge ({kb.count()} total):")
                    for i, (doc_id, text, user_id, source, _) in enumerate(docs, 1):
                        preview = text[:70] + "..." if len(text) > 70 else text
                        print(f"    {i}. {preview}")
                else:
                    print("  No knowledge saved yet.")
                print()
                
            elif choice == "4":
                doc_id = input("  Document ID: ").strip()
                kb.delete_document(doc_id)
                print()
                
            elif choice == "5":
                print()
                interactive_chat(kb)
                print()
                
            elif choice == "6":
                print("\n  👋 Goodbye!\n")
                break
            else:
                print("  ❌ Invalid option\n")
                
        except KeyboardInterrupt:
            print("\n\n  👋 Interrupted.\n")
            break
        except Exception as e:
            print(f"❌ Error: {e}\n")


if __name__ == "__main__":
    print("🤖 Collective AI - Startup Mode")
    print("\nSelect mode:")
    print("1. RAG Management CLI (add/search documents)")
    print("2. Interactive Chat")
    print("3. Run via API server (execute server.py instead)\n")
    
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    else:
        mode = input("Choose mode (1, 2, or 3): ").strip()
    
    if mode == "1":
        rag_cli()
    elif mode == "2":
        # Chat starts immediately, RAG loads only when needed
        interactive_chat()
    elif mode == "3":
        print("Please run 'python server.py' instead.")
    else:
        print("Invalid selection.")
