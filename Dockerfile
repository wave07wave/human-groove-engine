FROM node:22-alpine AS frontend-build

WORKDIR /workspace/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app
COPY backend/requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY backend/app ./app
COPY --from=frontend-build /workspace/frontend/dist /app/frontend-dist

ENV HGE_WEB_DIST_DIR=/app/frontend-dist
ENV HGE_DATABASE_PATH=/tmp/human_groove.db
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
