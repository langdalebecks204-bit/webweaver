# ---- build stage ----
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- runtime ----
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    WEAVER_DB_URL=sqlite:////data/weaver.db \
    WEAVER_UPLOAD_DIR=/data/uploads \
    WEAVER_ENABLE_SCHEDULER=true
WORKDIR /app
COPY --from=frontend-build /build/dist /app/frontend/dist
COPY backend/app ./backend/app
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt
WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]