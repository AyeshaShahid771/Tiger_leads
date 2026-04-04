# ============================================================
# Stage 1 — Builder: install Python dependencies
# ============================================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Install OS-level build deps needed to compile some wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev libssl-dev libpq-dev git curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip first
RUN pip install --upgrade pip

# Copy only dependency manifests first (better layer caching)
COPY requirements.txt pyproject.toml ./

# Install all Python dependencies into a separate prefix so we can
# copy them cleanly into the final stage without dragging in the
# build-time compiler tool-chain.
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ============================================================
# Stage 2 — Production: minimal runtime image
# ============================================================
FROM python:3.12-slim AS production

WORKDIR /app

# Runtime OS deps
# libpq5 — PostgreSQL client library required by psycopg2-binary
# libglib2.0-0, libgl1 — needed by PyMuPDF (fitz)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Copy entire application source
COPY . .

# Add /app to PYTHONPATH so that `from src.app.*` imports work without
# needing an editable pip install. This is simpler and more reliable.
ENV PYTHONPATH=/app

# Cloud Run injects PORT; default to 8080 when running locally
ENV PORT=8080

EXPOSE 8080

# Use exec form so signals are forwarded properly (important for graceful shutdown)
# The shell form `sh -c` is used to expand $PORT at runtime
CMD ["sh", "-c", "exec uvicorn src.app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --loop asyncio"]
