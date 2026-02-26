# API + Web Quickstart

## Backend (FastAPI)
1. `uv sync`
2. `uv run python main_api.py`

API endpoints:
- `GET /api/health`
- `POST /api/parse`
- `POST /api/parse/batch`
- `GET /api/outputs`

## Frontend (Vite)
1. `cd web`
2. `npm install`
3. `npm run dev`

The UI expects the API at `http://127.0.0.1:8000` by default. You can override by
setting `VITE_API_BASE` in `web/.env`.

## Production build
1. `cd web`
2. `npm run build`
3. `uv run python main_api.py`

If `web/dist` exists, FastAPI serves it at `/`.

## Environment
See `.env.example` for API variables:
- `XHSNOTE_API_HOST`
- `XHSNOTE_API_PORT`
- `XHSNOTE_API_RELOAD`
- `XHSNOTE_API_CORS_ORIGINS`
