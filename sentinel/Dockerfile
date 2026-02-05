# Sentinel roda NATIVAMENTE no Windows, não em container
# Este Dockerfile é apenas para referência

FROM python:3.11-windowsservercore

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sentinel_service.py .

EXPOSE 9000 9091

CMD ["python", "sentinel_service.py"]
