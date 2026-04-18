# Contributing to Collective AI

Thanks for your interest in contributing!

## Quick Start

1. Fork the repo
2. Create a branch:
   - `git checkout -b feat/my-feature` or `fix/my-bug`
3. Make changes with clear commits (see **Commit Style** below)
4. Open a Pull Request with:
   - what you changed
   - why you changed it
   - how to test it (screenshots welcome for UI changes)

## Development Setup

### Backend (FastAPI)

Install deps:
```bash
pip install -r requirements.txt
```

Create `backend/.env` (see `backend/.env.example` if present). Typical variables:
```env
GROQ_API_KEY=...
PINECONE_API_KEY=...
PORT=3000
ALLOWED_ORIGIN=http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000,http://127.0.0.1:3000
```

Run:
```bash
python -m backend.server
```

### Frontend (static)

From repo root:
```bash
python -m http.server 8000
```

Open:
`http://localhost:8000/frontend/app.html`

## Commit Style

Use **Conventional Commits**:
- `feat: ...`
- `fix: ...`
- `docs: ...`
- `refactor: ...`
- `chore: ...`

## Code Quality Expectations

- Keep changes focused and minimal
- Avoid committing secrets (API keys, Firebase credentials)
- Prefer small PRs that are easy to review
- Update docs if behavior changes
- Add/adjust error handling for network calls and external services

## Reporting Bugs / Requesting Features

- Use GitHub Issues
- Include reproduction steps and expected vs actual behavior
- Include environment details (browser, OS, Python version) when relevant
