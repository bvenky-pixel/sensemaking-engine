# Runs the API server (src/api/server.py). The real frontend
# (frontend/app/, Svelte + Vite -- see frontend/decisions.md "Build the
# real Confidant frontend") needs a build step to produce dist/, which
# is gitignored and not committed; this stage builds it and the final
# image copies only the compiled output in, so the runtime image never
# carries node_modules.
FROM node:22-slim AS frontend-build

WORKDIR /frontend

COPY frontend/app/package.json frontend/app/package-lock.json ./
RUN npm ci

COPY frontend/app/ .
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend-build /frontend/dist ./frontend/app/dist

# Fly.io (see fly.toml) mounts a persistent volume at /data and sets
# CONFIDANT_DB_PATH accordingly -- see src/api/db.py's module docstring
# for why this matters (without it, session history would be wiped on
# every redeploy/restart).
ENV CONFIDANT_DB_PATH=/data/confidant_mvp.db

EXPOSE 8000

CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
