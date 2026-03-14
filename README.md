<div align="center">

<img src="images/Logo-favicon.png" alt="Collective AI Logo" width="72" height="72" />

# Collective AI

**A community-powered AI assistant that grows smarter with every contribution.**

[![License: MIT](https://img.shields.io/badge/License-MIT-6366f1.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Firebase](https://img.shields.io/badge/Firebase-Auth%20%26%20Firestore-FFCA28?logo=firebase&logoColor=black)](https://firebase.google.com/)
[![Deploy on Render](https://img.shields.io/badge/Backend-Render-46e3b7?logo=render&logoColor=white)](https://render.com/)

[Live Demo](https://your-app.vercel.app) · [Report a Bug](https://github.com/your-username/collective-ai/issues) · [Request a Feature](https://github.com/your-username/collective-ai/issues)

</div>

---

## Overview

Collective AI is an open-source, community-driven AI chat platform. Unlike static AI assistants, Collective AI improves over time as users contribute domain knowledge through a structured contribution system. Every piece of submitted knowledge is stored in a vector database and retrieved at query time via **Retrieval-Augmented Generation (RAG)**, grounding the AI's responses in real community expertise.

The platform is designed to be self-hostable and easy to extend. If you want a private AI assistant that your team or community can collectively train — this is for you.

```
User asks a question
        │
        ▼
  FastAPI backend
        │
        ├──▶ Retrieve relevant chunks from ChromaDB (RAG)
        │
        ├──▶ Construct prompt with context
        │
        └──▶ LLM generates grounded response
                    │
                    ▼
          Answer sent back to user
          + saved to Firestore
```

---

## Features

- **🧠 RAG pipeline** — community knowledge is embedded with `sentence-transformers` and retrieved via ChromaDB at query time
- **💬 Chat interface** — Claude-inspired dark UI with conversation history, session switching, and search
- **✍️ Knowledge contributions** — users can submit, tag, and rate knowledge entries; top contributors appear on a leaderboard
- **🔐 Firebase Auth** — Google sign-in; per-user Firestore data isolation enforced via security rules
- **📱 Responsive** — works on mobile and desktop; collapsible sidebar, touch-friendly inputs
- **⚡ Fast** — instant session switching, real-time Firestore listeners, smooth animations
- **🔓 Open source** — MIT licensed; self-hostable backend on any Python host

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Vanilla HTML/CSS/JS · Sora + JetBrains Mono fonts |
| **Backend** | Python · FastAPI · Uvicorn |
| **AI / NLP** | sentence-transformers (embeddings) · TinyLlama (optional fine-tuning) |
| **Vector DB** | ChromaDB (persistent, local) |
| **Auth** | Firebase Authentication (Google OAuth) |
| **Database** | Cloud Firestore (sessions, messages, contributions) |
| **Hosting** | Vercel (frontend) · Render (backend) |

---

## Project Structure

```
collective-ai/
├── server.py               # FastAPI app — /api/chat, /api/contribute endpoints
├── LLM.py                  # Optional TinyLlama fine-tuning pipeline
├── requirements.txt        # Python dependencies
├── render.yaml             # Render deployment config (backend)
├── vercel.json             # Vercel deployment config (frontend)
│
├── index.html              # Landing / home page
├── app.html                # Sign-in / sign-up (Firebase Auth)
├── dashboard.html          # Main chat interface
├── contribution.html       # Knowledge submission form
├── leaderboard.html        # Top contributors
├── terms.html              # Terms of Service
├── privacy.html            # Privacy Policy
│
└── images/
    └── Logo-favicon.png
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js (optional, for local frontend serving)
- A [Firebase project](https://console.firebase.google.com/) with **Authentication** and **Firestore** enabled

### 1. Clone the repository

```bash
git clone https://github.com/your-username/collective-ai.git
cd collective-ai
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

> **Note:** `torch` and `transformers` can be large. If you don't need fine-tuning, you can skip those and remove `LLM.py` imports from `server.py`.

### 3. Configure Firebase

1. Go to [Firebase Console](https://console.firebase.google.com/) → your project → Project Settings → Web app
2. Copy your Firebase config object
3. In `dashboard.html`, `app.html`, and `contribution.html`, replace the placeholder config:

```js
const firebaseConfig = {
  apiKey: "YOUR_API_KEY",
  authDomain: "your-app.firebaseapp.com",
  projectId: "your-app",
  storageBucket: "your-app.firebasestorage.app",
  messagingSenderId: "YOUR_SENDER_ID",
  appId: "YOUR_APP_ID"
};
```

### 4. Set Firestore Security Rules

In the Firebase Console → Firestore Database → **Rules**, paste the following:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    match /users/{userId} {
      allow read, write: if request.auth != null
                         && request.auth.uid == userId;

      match /sessions/{sessionId} {
        allow read, write: if request.auth != null
                           && request.auth.uid == userId;

        match /messages/{messageId} {
          allow read, write: if request.auth != null
                             && request.auth.uid == userId;
        }
      }
    }

    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

### 5. Run the backend

```bash
python server.py
```

The API will be available at `http://localhost:8000`. Check `http://localhost:8000/docs` for the auto-generated Swagger UI.

### 6. Serve the frontend

Open `dashboard.html` directly in a browser, or use a simple local server:

```bash
# Python
python -m http.server 3000

# Node.js
npx serve .
```

---

## API Reference

### `POST /api/chat`

Send a message and receive an AI-generated response grounded in community knowledge.

**Request body:**
```json
{
  "message": "How does RAG work?",
  "sessionId": "abc123",
  "userId": "uid_xyz"
}
```

**Response:**
```json
{
  "reply": "RAG (Retrieval-Augmented Generation) works by..."
}
```

---

### `POST /api/contribute`

Submit a new knowledge entry to the vector database.

**Request body:**
```json
{
  "content": "Your knowledge text here",
  "category": "technology",
  "userId": "uid_xyz"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Contribution added successfully"
}
```

---

## Deployment

### Backend → Render

1. Push your code to GitHub
2. Create a new **Web Service** on [Render](https://render.com/)
3. Set the build command: `pip install -r requirements.txt`
4. Set the start command: `python server.py`
5. Copy your Render URL (e.g. `https://collective-ai-backend.onrender.com`)
6. In `dashboard.html` and `contribution.html`, update the `BACKEND` constant:

```js
const BACKEND = window.location.hostname === 'localhost'
  ? 'http://localhost:8000'
  : 'https://collective-ai-backend.onrender.com'; // ← your Render URL
```

### Frontend → Vercel

1. Connect your GitHub repo to [Vercel](https://vercel.com/)
2. Set the output directory to the repo root (no build step needed)
3. Deploy — Vercel will serve your HTML files statically

---

## How the RAG Pipeline Works

When a user submits a knowledge contribution, the text is:

1. **Chunked** into passages
2. **Embedded** using `sentence-transformers/all-MiniLM-L6-v2`
3. **Stored** in a persistent ChromaDB collection

When a user asks a question:

1. The question is **embedded** with the same model
2. The **top-k most similar** knowledge chunks are retrieved from ChromaDB
3. The chunks are **injected into the prompt** as context
4. The LLM generates a response **grounded in the retrieved knowledge**

This means the AI's answers improve as more knowledge is contributed — without retraining.

---

## Optional: Fine-tuning with TinyLlama

`LLM.py` contains an optional fine-tuning pipeline using TinyLlama and Hugging Face `transformers`. This is experimental and intended for GPU environments — running it on Render's free tier (CPU) will be very slow.

To fine-tune:

```bash
python LLM.py
```

> For most use cases, **RAG alone is sufficient** and much faster. Fine-tuning is only recommended if you have a large corpus of domain-specific Q&A pairs and GPU access.

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
