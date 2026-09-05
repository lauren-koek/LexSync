# Build the frontend (Vite/React) in a Node stage.
FROM node:22-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.14-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright's Chromium browser with dependencies
RUN playwright install chromium --with-deps

# Copy the full project
COPY . .

# Copy the compiled frontend from the Node build stage. FastAPI serves it
# as static files from frontend/dist (see backend/main.py). Must come after
# `COPY . .` so it isn't overwritten by the local tree (which has no dist).
COPY --from=frontend-build /frontend/dist ./frontend/dist

RUN chmod +x /app/entrypoint.sh

CMD ["/bin/sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
