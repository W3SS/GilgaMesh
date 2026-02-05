#!/bin/bash
# PROMETHEUS MESH - Initial Setup Script

echo "🚀 Starting Prometheus Mesh Setup..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found! Please install Docker Desktop first."
    echo "Linux: curl -fsSL https://get.docker.com | sh"
    exit 1
fi

echo "✅ Docker found"

# Check NVIDIA
if lspci | grep -i nvidia > /dev/null; then
    echo "✅ NVIDIA GPU detected"
    # Note: On Windows with Docker Desktop, NVIDIA support is usually automatic if configured
else
    echo "⚠️  No NVIDIA GPU detected. AI services might run slow."
fi

# Create directories (redundant but safe)
echo "📂 Verifying directories..."
mkdir -p data/qdrant_data
mkdir -p data/prometheus_data
mkdir -p data/grafana_data
mkdir -p ai_services/ollama/models
mkdir -p ai_services/comfyui/models/checkpoints
mkdir -p ai_services/comfyui/output

# Download Models
echo "📥 Downloading AI Models (this may take a while)..."
bash scripts/setup/download_models.sh

# Build Containers
echo "🏗️  Building containers..."
docker-compose build

echo "✅ Setup Complete!"
echo "Run 'docker-compose up -d' to start the mesh."
