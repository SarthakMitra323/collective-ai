# Deployment Guide

This guide covers deploying the Collective AI application to Vercel (Frontend) and Render (Backend).

## Table of Contents
1. [Backend Deployment (Render)](#backend-deployment-render)
2. [Frontend Deployment (Vercel)](#frontend-deployment-vercel)
3. [Environment Variables](#environment-variables)
4. [Post-Deployment](#post-deployment)

---

## Backend Deployment (Render)

### Prerequisites
- GitHub account with the repository
- Render account (https://render.com)

### Steps

1. **Connect Repository to Render**
   - Log in to [Render Dashboard](https://dashboard.render.com)
   - Click "New +" and select "Web Service"
   - Connect your GitHub repository
   - Select the branch: `main` (or your preferred branch)

2. **Configure Service**
   - **Name**: `collective-ai-backend`
   - **Runtime**: `Python 3.11`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn backend.server:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Standard (or higher based on requirements)

3. **Set Environment Variables**
   Add these in Render dashboard:
   ```
   PYTHONUNBUFFERED=true
   PYTHON_VERSION=3.11
   ```

4. **Deploy**
   - Click "Create Web Service"
   - Wait for deployment to complete
   - Note your service URL (e.g., `https://collective-ai-backend.onrender.com`)

5. **Update Frontend**
   - Update `BACKEND_URL` with your Render service URL

---

## Frontend Deployment (Vercel)

### Prerequisites
- GitHub account with the repository
- Vercel account (https://vercel.com)
- Backend URL from Render deployment

### Steps

1. **Connect Repository to Vercel**
   - Go to [Vercel Dashboard](https://vercel.com/dashboard)
   - Click "Add New..." → "Project"
   - Import your GitHub repository
   - Select the root directory (important!)

2. **Configure Project**
   - **Framework**: `Static Site`
   - **Build Command**: Leave empty (no build needed)
   - **Output Directory**: `./frontend`
   - **Install Command**: Leave empty

3. **Set Environment Variables**
   In Vercel project settings, add:
   ```
   BACKEND_URL=https://your-render-backend-url.onrender.com
   ```

4. **Deploy**
   - Click "Deploy"
   - Vercel will automatically deploy from main branch
   - Get your Vercel URL (e.g., `https://collective-ai.vercel.app`)

---

## Environment Variables

### Backend (.env file in root)
```
PYTHONUNBUFFERED=true
PYTHON_VERSION=3.11
CHROMA_DB_PATH=./data/chroma_db
```

### Frontend (in Vercel Environment Variables)
```
BACKEND_URL=https://collective-ai-backend.onrender.com
```

### Cross-Origin Configuration
Update `backend/server.py` CORS settings:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-vercel-domain.vercel.app",
        "http://localhost:3000"  # for local development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Post-Deployment

### Health Checks
- Backend: `https://collective-ai-backend.onrender.com/`
- Frontend: `https://collective-ai.vercel.app/`

### Update API Endpoints
- Update all frontend API calls to use the Render backend URL
- Test all endpoints (chat, contribute, etc.)

### Monitoring
- **Render**: Check logs in Render dashboard
- **Vercel**: Check logs and analytics in Vercel dashboard

### Troubleshooting

**Backend won't start:**
- Check Python version compatibility
- Verify all dependencies in `requirements.txt`
- Check Render logs for error messages

**Frontend can't reach backend:**
- Verify backend URL in environment variables
- Check CORS settings in backend
- Ensure backend is running and healthy

**Slow deployment:**
- Large ML models may take time to deploy
- Consider using a higher Render plan
- Pre-download and cache models if possible

---

## CI/CD

Both Render and Vercel support automatic deployments:
- **Render**: Auto-deploys on push to main branch
- **Vercel**: Auto-deploys on every push
- Configure branch protection rules in GitHub to ensure code quality

---

## Scaling & Performance

### Backend (Render)
- Upgrade plan for higher performance
- Monitor CPU/Memory usage
- Consider Redis for caching (add via Render add-ons)

### Frontend (Vercel)
- Vercel automatically scales globally
- Use Vercel Analytics for performance insights
- Enable image optimization

---

For more help:
- [Render Documentation](https://render.com/docs)
- [Vercel Documentation](https://vercel.com/docs)
