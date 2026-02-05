#!/bin/bash
echo "📥 [Ollama] Checking models..."

# Ensure we have the base image
docker pull ollama/ollama:latest

# Define model list
MODELS=("llama3.1:8b-instruct-q4_K_M" "nomic-embed-text")

for model in "${MODELS[@]}"; do
    echo "   Running pull for $model..."
    # Run ephemeral container to pull model to shared volume
    docker run --rm -v $(pwd)/ai_services/ollama/models:/root/.ollama ollama/ollama pull $model
done

echo "✅ [Ollama] Models ready."
