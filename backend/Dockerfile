FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

# libgl/libglib are needed once OpenCV (severity segmentation) is added in Phase 5.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./
# CPU-only wheels keep the image small; inference targets CPU (ARCH §2, NFR-P-005).
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# Build context is the repository root (docker build -f backend/Dockerfile .)
COPY backend/app ./app
# Baked-in so the image is self-sufficient while artifacts are not yet
# promoted to the Supabase model registry (Phase 5 → Phase 8, ADR-0008).
# When MODEL_REGISTRY_URI is set, the registry sync path overrides these.
COPY ml/artifacts/models ./ml/artifacts/models
COPY ml/knowledge_base ./ml/knowledge_base

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/v1/health || exit 1

# One worker: PyTorch + SHAP must fit the free-tier RAM budget (ARCH §11.3).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
