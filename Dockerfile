# Road To E — image for the SHARED READ-ONLY copy (Render free web service).
# Two stages: build the Vite SPA with Node, then run FastAPI + the committed
# SQLite snapshot on python:slim. SHARE_MODE defaults to 1 here on purpose: a
# public copy of this app must never be writable (see app/core/share.py).
# Never used locally — start.bat is the local launcher.

FROM node:24-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# `npm run build` = tsc -b && vite build → /web/dist
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SHARE_MODE=1
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
# app code + the committed DB (backend/data/tabletennis.db, last_sync.txt);
# .dockerignore keeps the venv, backups and retired ML artefacts out.
COPY backend/ backend/
COPY --from=web /web/dist frontend/dist
EXPOSE 8000
# Render injects $PORT; default 8000 for a plain `docker run`.
CMD ["sh", "-c", "python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8000}"]
