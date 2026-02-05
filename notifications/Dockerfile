FROM python:3.11-slim

WORKDIR /app

# Dependências do sistema (curl para healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:9003/health || exit 1

CMD ["uvicorn", "notification_service:app", "--host", "0.0.0.0", "--port", "9003"]
