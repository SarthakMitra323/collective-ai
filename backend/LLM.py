from huggingface_hub import InferenceClient # type:ignore
import sys
import logging
from typing import Optional, List, Dict

try:
    from .config import HF_TOKEN, HF_MODEL, HF_FALLBACK_MODEL, HF_PROVIDER, REQUEST_TIMEOUT, DEBUG_MODE, SUPPRESS_HF_LOGS, MAX_OUTPUT_TOKENS
except ImportError:
    from config import HF_TOKEN, HF_MODEL, HF_FALLBACK_MODEL, HF_PROVIDER, REQUEST_TIMEOUT, DEBUG_MODE, SUPPRESS_HF_LOGS, MAX_OUTPUT_TOKENS

if SUPPRESS_HF_LOGS:
    logging.getLogger("huggingface_hub").setLevel(logging.CRITICAL)
    logging.getLogger("transformers").setLevel(logging.CRITICAL)
    logging.getLogger("sentence_transformers").setLevel(logging.CRITICAL)

logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.WARNING,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CollectiveModel:

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
        self.model = HF_MODEL
        self.fallback_model = HF_FALLBACK_MODEL if HF_FALLBACK_MODEL else None
        self._init_error = None
        self._generation_api_mode: Optional[str] = None
        if not HF_TOKEN:
            self._init_error = "HF_TOKEN not configured"
            logger.error(self._init_error)
            return

    def _init_client(self):
        """Initialize the HF client lazily on first generation."""
        if self.client is not None:
            return self.client

        if self._init_error:
            raise RuntimeError(self._init_error)

        if not HF_TOKEN:
            self._init_error = "HF_TOKEN not configured"
            raise RuntimeError(self._init_error)

        try:
            client_kwargs: Dict[str, object] = {
                "api_key": HF_TOKEN,
                "timeout": REQUEST_TIMEOUT,
            }
            provider = HF_PROVIDER.lower() if HF_PROVIDER else ""
            if provider in {"auto", "featherless-ai"}:
                provider = ""
            if provider:
                client_kwargs["provider"] = HF_PROVIDER

            self.client = InferenceClient(**client_kwargs)
            logger.info("LLM initialized: %s", self._resolved_model())
            return self.client
        except Exception as e:
            self._init_error = str(e)
            logger.exception("Failed to initialize HuggingFace client")
            raise RuntimeError(f"Failed to initialize HuggingFace client: {e}")

    def _resolved_model(self, model: Optional[str] = None) -> str:
        model = model or self.model
        provider = HF_PROVIDER.lower() if HF_PROVIDER else ""
        if provider in {"auto", "featherless-ai"}:
            provider = ""
        if provider:
            return model

        tail = model.rsplit("/", 1)[-1]
        if ":" in tail or "://" in model:
            return model
        return f"{model}:fastest"

    @staticmethod
    def _build_prompt(
        user_input: str,
        context_docs: Optional[List[str]] = None
    ) -> str:
        context_section = ""
        if context_docs and len(context_docs) > 0:
            context_section = "\n\nKnowledge base context:\n"
            for i, doc in enumerate(context_docs[:3], 1):
                doc_preview = doc[:180] + ("..." if len(doc) > 180 else "")
                context_section += f"  {i}. {doc_preview}\n"
        
        prompt = (
            f"Answer clearly and use prior turns for context.{context_section}\n\n"
            f"Question: {user_input}"
        )
        return prompt

    def _build_messages(
        self,
        user_input: str,
        context_docs: Optional[List[str]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, str]]:
        # Build chat-completion messages with short memory window.
        messages: List[Dict[str, str]] = []

        for msg in (chat_history or [])[-6:]:
            role = msg.get("role", "")
            content = msg.get("content", "").strip()
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        messages.append({
            "role": "user",
            "content": self._build_prompt(user_input, context_docs),
        })
        return messages

    def _build_generation_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert role-based messages into a single instruction-style prompt."""
        lines: List[str] = [
            "<s>[INST]",
            "You are Collective AI.",
            "Answer the user clearly and concisely.",
            "Do not output role labels.",
            "Conversation:",
        ]

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "").strip()
            if not content:
                continue
            if role == "assistant":
                lines.append(f"Assistant: {content}")
            else:
                lines.append(f"User: {content}")

        lines.append("")
        lines.append("Now provide the assistant reply to the final user message only.")
        lines.append("[/INST]")
        return "\n".join(lines)

    @staticmethod
    def _estimate_input_tokens(text: str) -> int:
        """Roughly estimate tokens so we can keep requests inside the model window."""
        return max(1, len(text) // 4)

    def _generation_budget(self, prompt: str) -> int:
        """Pick a safe output budget below the model context limit."""
        prompt_tokens = self._estimate_input_tokens(prompt)
        reserved_for_prompt = 48
        remaining = 4096 - prompt_tokens - reserved_for_prompt
        return max(64, min(MAX_OUTPUT_TOKENS, remaining))

    def _infer_preferred_mode(self, client) -> str:
        if self._generation_api_mode in {"text", "chat"}:
            return self._generation_api_mode
        model_lower = self.model.lower()
        has_chat = hasattr(client, "chat_completion")
        has_text = hasattr(client, "text_generation")
        if has_chat and ("instruct" in model_lower or "chat" in model_lower):
            return "chat"
        if has_text:
            return "text"
        if has_chat:
            return "chat"
        return "text"

    def _call_chat_completion(self, client, messages: List[Dict[str, str]], max_output_tokens: int, model: Optional[str] = None) -> str:
        chat_kwargs: Dict[str, object] = {
            "model": self._resolved_model(model),
            "messages": messages,
            "temperature": 0.3,
            "stop": ["\nUser:", "\n### User:"],
            "max_tokens": max_output_tokens,
        }
        out = client.chat_completion(**chat_kwargs)
        return (out.choices[0].message.content or "").strip()

    def _call_text_completion(self, client, prompt: str, max_output_tokens: int, model: Optional[str] = None) -> str:
        generation_kwargs: Dict[str, object] = {
            "model": self._resolved_model(model),
            "prompt": prompt,
            "temperature": 0.3,
            "repetition_penalty": 1.1,
            "return_full_text": False,
            "stop": ["\nUser:", "\n### User:"],
            "max_new_tokens": max_output_tokens,
            "do_sample": False,
        }
        out = client.text_generation(**generation_kwargs)
        return str(out).strip()

    def _call_text_generation(self, messages: List[Dict[str, str]]) -> str:
        """Call HF inference with automatic fallback between text and chat tasks."""
        client = self._init_client()
        prompt = self._build_generation_prompt(messages)
        max_output_tokens = self._generation_budget(prompt)
        preferred_mode = self._infer_preferred_mode(client)
        candidate_models = [self.model]
        if self.fallback_model and self.fallback_model != self.model:
            candidate_models.append(self.fallback_model)

        last_error: Optional[Exception] = None
        for candidate in candidate_models:
            try:
                if preferred_mode == "chat" and hasattr(client, "chat_completion"):
                    response = self._call_chat_completion(client, messages, max_output_tokens, candidate)
                    self._generation_api_mode = "chat"
                    self.model = candidate
                    return response
                if preferred_mode == "text" and hasattr(client, "text_generation"):
                    response = self._call_text_completion(client, prompt, max_output_tokens, candidate)
                    self._generation_api_mode = "text"
                    self.model = candidate
                    return response

                # Secondary fallback if preferred mode is unavailable in current client version.
                if preferred_mode != "chat" and hasattr(client, "chat_completion"):
                    self._generation_api_mode = "chat"
                    response = self._call_chat_completion(client, messages, max_output_tokens, candidate)
                    self.model = candidate
                    return response
                if preferred_mode != "text" and hasattr(client, "text_generation"):
                    self._generation_api_mode = "text"
                    response = self._call_text_completion(client, prompt, max_output_tokens, candidate)
                    self.model = candidate
                    return response
            except ValueError as e:
                last_error = e
                msg = str(e).lower()
                unsupported = "not supported by any provider" in msg or "model_not_supported" in msg
                # Some providers route this model under conversational only.
                if "supported task" in msg and "conversational" in msg and hasattr(client, "chat_completion"):
                    self._generation_api_mode = "chat"
                    try:
                        response = self._call_chat_completion(client, messages, max_output_tokens, candidate)
                        self.model = candidate
                        return response
                    except Exception as inner_e:
                        last_error = inner_e
                if unsupported:
                    logger.warning("Model unsupported on current route: %s", candidate)
                    continue
                raise

        if last_error:
            raise last_error

        raise AttributeError(
            "InferenceClient generation APIs are unavailable. "
            "Upgrade huggingface-hub to a newer version."
        )

    def warmup(self) -> None:
        """Prime the provider/model with a tiny request after deployment."""
        messages = [
            {"role": "system", "content": "You are Collective AI."},
            {"role": "user", "content": "Reply with one word: ready"},
        ]
        response = self._call_text_generation(messages)
        if not response:
            raise RuntimeError("Warmup produced empty response")

    def generate_response(
        self,
        user_input: str,
        context_docs: Optional[List[str]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        show_thinking: bool = True
    ) -> str:
        """Generate response using HuggingFace text-generation API.
        
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
            
            # Clean up any <think> tags from output if present
            response_text = response_text.replace("<think>", "").replace("</think>", "").strip()

            # Remove role-play spillover if provider ignores stop sequences.
            if response_text.startswith("Assistant:"):
                response_text = response_text[len("Assistant:"):].strip()
            if response_text.startswith("User question:"):
                response_text = response_text[len("User question:"):].strip()
            if response_text.startswith("Question:"):
                response_text = response_text[len("Question:"):].strip()
            for marker in ["\nUser:", "\nAssistant:", "\n[INST]", "</s>"]:
                if marker in response_text:
                    response_text = response_text.split(marker, 1)[0].strip()

            response_text = self._remove_repeated_paragraphs(response_text)
            
            # Validate response
            if not response_text or not response_text.strip():
                return "I couldn't generate a response. Try again."
            
            return response_text.strip()
            
        except ValueError as e:
            if show_thinking:
                print("\r" + " " * 30 + "\r", end="", flush=True)
            logger.warning(f"ValueError: {e}")
            lower = str(e).lower()
            if "not supported by any provider you have enabled" in lower:
                return "❌ Provider routing error. Set HF_PROVIDER to a supported provider, or leave it empty to use Hugging Face fastest routing."
            return "❌ Input error. Try again."
        except AttributeError as e:
            if show_thinking:
                print("\r" + " " * 30 + "\r", end="", flush=True)
            logger.error(f"AttributeError: {e}")
            return "❌ Inference client is outdated. Update dependencies and retry."
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
