# Deploying PromoForge on free tiers

| Part | Host | Why |
|---|---|---|
| Backend (FastAPI engine, ~270 MB RAM measured) | Render free web service, Docker (512 MB, no card) | Builds from this public repo using the root `Dockerfile` |
| Frontend (Next.js) | Vercel Hobby (free) | Native Next.js hosting; proxies `/api/*` to the backend, so no CORS setup |

Hugging Face Docker Spaces were the first choice but now need a paid PRO plan on cpu-basic, so they are no longer free.

Free-tier behaviour: Render spins the backend down after 15 minutes without visitors and takes about a minute to wake.
The frontend shows "The engine isn't responding yet ..." until it is up. Approved campaigns live in SQLite under `/tmp`
and reset when the service restarts.

## 1. Backend → Render

1. Sign up at https://render.com (no card needed).
2. **New → Web Service → Public Git Repository**, paste `https://github.com/KoduruChandrasekhar/tcstechday`, Connect.
3. Language **Docker** (detected from the root `Dockerfile`), instance type **Free**, then **Deploy Web Service**.
   Render sets `$PORT`; the Dockerfile already listens on it.
4. Optional: Environment → add `GEMINI_API_KEY` (without it the AI panels show built-in template text). Never commit `.env`.
5. Check `https://<service>.onrender.com/api/meta` returns JSON.

Other hosts: the same root `Dockerfile` runs anywhere that provides ≥ 512 MB RAM and sets `$PORT` (Railway, Koyeb,
Cloud Run, or a paid Hugging Face Space via `deploy/hf_space.sh`). Local test:
`docker build -t promoforge . && docker run -p 7860:7860 promoforge`.

## 2. Frontend → Vercel

1. Import the GitHub repo in Vercel and set **Root Directory** to `frontend` (framework preset: Next.js).
2. Environment variable `API_URL = https://<service>.onrender.com` (no trailing slash).
   It is read at build time (it becomes the `/api/*` rewrite), so redeploy after changing it.
3. Deploy. Every push to the main branch redeploys automatically.

## Before making the link public

- **Gemini quota:** every visitor's AI click uses your key. Responses are cached and the app falls back to template
  text when the quota runs out; use a separate free-tier key for the public demo.
- **`POST /api/admin/reset-demo`** is open: anyone can wipe approved campaigns (harmless for a demo, but know it).
