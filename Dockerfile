# Runs the MVP API server (src/api/server.py). No build step for the
# frontend -- it's a static HTML/JS file, served directly by FastAPI's
# StaticFiles mount (see src/api/server.py).
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Fly.io (see fly.toml) mounts a persistent volume at /data and sets
# CONFIDANT_DB_PATH accordingly -- see src/api/db.py's module docstring
# for why this matters (without it, session history would be wiped on
# every redeploy/restart).
ENV CONFIDANT_DB_PATH=/data/confidant_mvp.db

EXPOSE 8000

CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
