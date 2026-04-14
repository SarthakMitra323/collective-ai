<div align="center">

<img src="frontend/images/Logo.png" alt="Collective AI Logo" width="120" />

# Collective AI

Community-powered AI chat platform that improves through shared knowledge.

[![License: MIT](https://img.shields.io/badge/License-MIT-111827.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Firebase](https://img.shields.io/badge/Firebase-Auth%20%26%20Data-FFCA28?logo=firebase&logoColor=black)](https://firebase.google.com/)
[![Render](https://img.shields.io/badge/Backend-Render-46E3B7?logo=render&logoColor=111827)](https://render.com/)
[![Vercel](https://img.shields.io/badge/Frontend-Vercel-000000?logo=vercel&logoColor=white)](https://vercel.com/)

[Live App](https://collective-ai.vercel.app)

</div>

---

## What is Collective AI?

Collective AI is a full-stack web application where users can chat with an AI assistant and contribute knowledge that improves future responses.

It combines:

- a clean chat interface
- Firebase authentication and user session storage
- a FastAPI backend
- retrieval-augmented generation (RAG) with vector search
- production deployment via Vercel + Render

---

## Key Features

- Chat interface with persistent user sessions
- Contribution workflow for adding community knowledge
- RAG-backed responses grounded in stored context
- Firebase Auth integration (email/password + Google)
- Public pages: terms, privacy, leaderboard, contribution
- Health and diagnostics endpoints for production reliability

---

## Architecture

- Frontend: static HTML/CSS/JavaScript pages in `frontend/`
- Backend: FastAPI app in `backend/server.py`
- LLM Layer: Groq-backed inference via `backend/LLM.py`
- Retrieval Layer: embeddings + Pinecone-backed vector search via `backend/rag.py`
- Auth/Data: Firebase Authentication + Firestore

---

## Quick Start (Local)

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure backend environment

Create `backend/.env` (you can use `backend/.env.example` as a template).

Minimum required variables:

```env
GROQ_API_KEY=your_groq_key
PINECONE_API_KEY=your_pinecone_key
```

Optional development-friendly defaults:

```env
PORT=3000
ALLOWED_ORIGIN=http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000,http://127.0.0.1:3000
```

### 3. Start backend

```bash
python -m backend.server
```

Backend runs on `http://localhost:3000` by default.

### 4. Serve frontend

From project root:

```bash
python -m http.server 8000
```

Then open:

`http://localhost:8000/frontend/app.html`

---

## API Endpoints

- `GET /api/test` - lightweight connectivity check
- `GET /api/ready` - readiness endpoint
- `GET /api/health` - detailed service health
- `POST /api/chat` - chat completion endpoint
- `POST /api/contribute` - contribute knowledge
- `POST /api/search` - retrieve relevant context

Sample chat request:

```json
{
  "message": "Explain how Collective AI learns",
  "sessionId": "session_123",
  "userId": "user_123",
  "stream": false
}
```

---

## Deployment

### Frontend (Vercel)

- Static frontend is deployed on Vercel.
- API calls can use Vercel rewrites to proxy `/api/*` to Render backend.

### Backend (Render)

- Backend is deployed as a Python web service.
- Uses `gunicorn` + `uvicorn.workers.UvicornWorker`.
- Health check path: `/api/ready`.

---

## Security and Reliability Notes

- CORS configuration supports production and localhost development origins.
- Request timeouts and retry behavior are implemented on both frontend and backend.
- Session expiry guard is enforced in the dashboard.
- Chat requests include trace IDs for debugging end-to-end request flow.

---

## Project Structure

```text
frontend/            # UI pages and client logic
backend/             # FastAPI server, LLM and RAG logic
render.yaml          # Render service config
vercel.json          # Vercel rewrites/headers
requirements.txt     # Python dependencies
CHANGELOG.md         # Public change history
```

---

## Contributing

Contributions are welcome.

- Open an issue for bugs or feature requests
- Submit a PR with clear scope and test notes

---

## License

This project is licensed under the MIT License. See `LICENSE` for details.

---


## Contributing

Contributions are welcome! Here's how to get involved:

1. **Fork** the repository
2. **Create a branch** for your feature: `git checkout -b feature/my-feature`
3. **Commit** your changes: `git commit -m "feat: add my feature"`
4. **Push** to your branch: `git push origin feature/my-feature`
5. **Open a pull request**

Please follow [Conventional Commits](https://www.conventionalcommits.org/) for commit messages and open an issue before starting large changes.

### Areas where help is welcome

- Streaming AI responses (Server-Sent Events)
- File upload support for knowledge contributions
- Better markdown rendering in chat
- Rate limiting and abuse protection on the backend
- Unit and integration tests
- Docker / docker-compose setup

---

## Known Issues & Roadmap

| Status | Item |
|---|---|
| ✅ Done | Firebase Auth, Firestore sessions, RAG pipeline, contribution system |
| ✅ Done | Responsive dashboard, dark theme, leaderboard |
| 🔧 In progress | Streaming responses |
| 📋 Planned | File uploads for contributions |
| 📋 Planned | Admin moderation panel for contributions |
| 📋 Planned | Docker support |
| 📋 Planned | Rate limiting |

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## Acknowledgements

- [FastAPI](https://fastapi.tiangolo.com/) for the clean Python API framework
- [ChromaDB](https://www.trychroma.com/) for the easy-to-use vector store
- [sentence-transformers](https://www.sbert.net/) for embedding models
- [Firebase](https://firebase.google.com/) for auth and real-time database
- [Sora](https://fonts.google.com/specimen/Sora) & [JetBrains Mono](https://www.jetbrains.com/lp/mono/) for the typefaces

---

<div align="center">

Built with ❤️ by the community, for the community.

[⬆ Back to top](#collective-ai)

</div>
