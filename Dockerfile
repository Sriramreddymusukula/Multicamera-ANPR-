# Build the React app once, then serve it from FastAPI on the same Render service.
FROM node:22-bookworm-slim AS frontend-build

WORKDIR /src/web/frontend
COPY web/frontend/package.json web/frontend/package-lock.json ./
RUN npm ci
COPY web/frontend/ ./
RUN npm run build


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app:/app/web/backend

WORKDIR /app

# OpenCV video/image support and Tesseract fallback OCR.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libglib2.0-0 \
        libgl1 \
        libgomp1 \
        tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch to avoid pulling CUDA libraries into the image.
COPY web/backend/requirements-docker.txt /tmp/requirements-docker.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install --index-url https://download.pytorch.org/whl/cpu \
        "torch>=2.7.1" "torchvision>=0.22.1" \
    && python -m pip install -r /tmp/requirements-docker.txt

COPY . /app
COPY --from=frontend-build /src/web/frontend/dist /app/web/frontend/dist

# Render supplies PORT. The application must listen on all interfaces.
EXPOSE 10000
CMD ["sh", "-c", "uvicorn app.main:app --app-dir /app/web/backend --host 0.0.0.0 --port ${PORT:-10000}"]
