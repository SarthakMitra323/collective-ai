# Security Policy

## Supported Versions

Security updates are provided for the `main` branch.

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, report privately by emailing:

- **hello.connectsphere.offical@gmail.com**

Include:
- A description of the vulnerability and impact
- Steps to reproduce (proof-of-concept if possible)
- Affected files/endpoints (e.g., `/api/chat`, `/api/contribute`)
- Any relevant logs, screenshots, or suggested fixes

## Response Timeline

We aim to:
- Acknowledge reports within **72 hours**
- Provide a mitigation plan or status update within **7 days** (depending on severity/complexity)

## Scope Notes (High-level)

This project may involve:
- Authentication (Firebase Auth)
- User/session data (Firestore)
- External API keys (e.g., Groq, Pinecone)

If you believe a credential is exposed, treat it as urgent and report immediately.
