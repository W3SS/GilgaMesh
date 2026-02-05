#!/bin/bash
echo "📥 [ComfyUI] Checking models..."

CHECKPOINT_DIR="ai_services/comfyui/models/checkpoints"
mkdir -p $CHECKPOINT_DIR

# Define models to download (Name -> URL)
declare -A MODELS
MODELS=(
    ["sd_xl_base_1.0.safetensors"]="https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors"
    ["sd_xl_refiner_1.0.safetensors"]="https://huggingface.co/stabilityai/stable-diffusion-xl-refiner-1.0/resolve/main/sd_xl_refiner_1.0.safetensors"
)

for file in "${!MODELS[@]}"; do
    if [ ! -f "$CHECKPOINT_DIR/$file" ]; then
        echo "   Downloading $file..."
        curl -L -o "$CHECKPOINT_DIR/$file" "${MODELS[$file]}"
    else
        echo "   ✅ $file exists"
    fi
done

echo "✅ [ComfyUI] Models ready."
