# Imagen única: el backend sirve la API, el WebSocket y la SPA compilada.

# 1) Build del frontend (Node solo existe en esta etapa)
FROM node:20-alpine AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# 2) Runtime
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CONFIG_PATH=/app/config.yaml \
    STATIC_DIR=/app/static

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/app ./app
COPY --from=frontend /src/dist ./static

RUN useradd --system --uid 1000 dashboard
USER dashboard

CMD ["python", "-m", "app.main"]
