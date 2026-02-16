# OmniAI Deployment Guide

## Frontend: GitHub Pages

### Step 1: Enable GitHub Pages
1. Go to your GitHub repository
2. Navigate to **Settings** → **Pages**
3. Under "Build and deployment":
   - Source: Select **Deploy from a branch**
   - Branch: Select **gh-pages** (will appear after first deploy)
   - Folder: Select **/ (root)**

### Step 2: Add API Base URL Secret
1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Add a new repository variable:
   - Name: `API_BASE_URL`
   - Value: Your production backend URL (see below)

### Step 3: Push to Main Branch
```bash
git add .
git commit -m "Add GitHub Actions workflow"
git push origin main
```

The workflow will automatically build and deploy to GitHub Pages.

---

## Backend: Always Online

### Option A: Railway (Recommended - Free Tier)

1. Go to [Railway.app](https://railway.app) and sign up
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your repository
4. Railway will auto-detect the Dockerfile
5. In Railway dashboard, go to **Variables** and add:
   - `NGROK_AUTHTOKEN` = your ngrok token (if using ngrok)
6. Railway provides a persistent URL like `https://your-app.railway.app`

**Update GitHub Secrets:**
- Set `API_BASE_URL` = `https://your-app.railway.app`

### Option B: Keep Using ngrok (Free but Ephemeral)

Your current ngrok URL changes each time the tunnel restarts:
```
https://rossie-chargeful-plentifully.ngrok-free.dev
```

To use this:
1. Update `API_BASE_URL` in GitHub secrets to your current ngrok URL
2. Note: This URL will change if ngrok restarts

### Option C: Cloudflare Tunnel (More Stable)

1. Install Cloudflare tunnel on your server
2. Create a persistent tunnel to your backend
3. Use that stable URL in GitHub secrets

---

## Current Status

| Component | URL |
|-----------|-----|
| Local Backend | http://localhost:8000 |
| ngrok Tunnel | https://rossie-chargeful-plentifully.ngrok-free.dev |
| GitHub Pages | (Configure after push) |

---

## Troubleshooting

### CORS Issues
If you see CORS errors after deployment:
1. Make sure `OMNI_CORS_ORIGINS` in the backend includes your GitHub Pages URL
2. The format should be: `https://yourusername.github.io`

### Build Fails
Check the Actions tab in your repository for error logs.

### Backend Not Connecting
- Verify the `API_BASE_URL` is set correctly in GitHub secrets
- Ensure the backend is running and accessible
