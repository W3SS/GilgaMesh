FROM python:3.11-slim

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY rag_memory_service.py .
COPY seed_knowledge.json .

EXPOSE 9001 9092

CMD ["python", "rag_memory_service.py"]
