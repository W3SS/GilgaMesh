FROM python:3.11-slim

WORKDIR /app

# Instala dependências
COPY orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia código do Orchestrator
COPY orchestrator/main.py .

# Copia AI Services (Template Workflows)
COPY ai_services /ai_services

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')"

EXPOSE 8000 9090

CMD ["python", "main.py"]
