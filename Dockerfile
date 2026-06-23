FROM python:3.11-slim

WORKDIR /app

# System deps for sqlite + build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (cache)
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -e ".[dev,pdf]" || pip install --no-cache-dir -e .

# Copy source
COPY . /app

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "marketsignal.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]