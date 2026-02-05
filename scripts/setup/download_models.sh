#!/bin/bash
# PROMETHEUS MESH - Model Downloader

# Delegate to service-specific scripts
bash ai_services/ollama/scripts/setup.sh
bash ai_services/comfyui/scripts/setup.sh

echo "✅ Global model setup complete."
