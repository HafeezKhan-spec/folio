FROM node:22-bookworm-slim AS web
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FOLIO_DATABASE_PATH=/data/folio.db
ENV FOLIO_STATIC_DIR=/app/frontend/dist
ENV FOLIO_COOKIE_SECURE=1
COPY backend /app/backend
RUN pip install --no-cache-dir /app/backend
COPY --from=web /src/frontend/dist /app/frontend/dist
EXPOSE 8000
CMD ["uvicorn", "folio.main:app", "--host", "0.0.0.0", "--port", "8000"]
