# Support

## Where to get help

- **GitHub Issues**: For bugs, feature requests, and questions about running the project.
- **Security issues**: See `SECURITY.md` (please report privately).

## Before opening an issue

Please include:
- What you expected to happen vs what happened
- Steps to reproduce
- Relevant logs (browser console + backend logs)
- Your environment (OS, browser, Python version)

## Common troubleshooting

- Verify backend is running and reachable at `http://localhost:3000` (local)
- Confirm environment variables are set (`GROQ_API_KEY`, `PINECONE_API_KEY`)
- Check CORS/ALLOWED_ORIGIN if frontend can’t call backend
- Confirm Vercel/Render rewrites if production API calls fail
