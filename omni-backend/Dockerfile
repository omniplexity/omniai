FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (including curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Copy source first
COPY omni_backend ./omni_backend
COPY pyproject.toml ./

# Install pip and the package
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Create directories for data and artifacts
RUN mkdir -p /app/.omni_artifacts /app/.omni_uploads /app/.data

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "omni_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
