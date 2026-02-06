"""
Ollama Adapter - Implements AIProviderPort for text generation
"""

import httpx
import logging
from typing import Dict, Any

from ports.ai_provider import AIProviderPort
from config.settings import settings


logger = logging.getLogger(__name__)


class OllamaAdapter:
    """Ollama AI provider adapter"""
    
    def __init__(self, base_url: str = settings.ollama_url, http_client: httpx.AsyncClient = None):
        self.base_url = base_url
        self.http_client = http_client or httpx.AsyncClient(timeout=60.0)
        
    async def generate_text(self, prompt: str, parameters: Dict[str, Any]) -> str:
        """Generate text using Ollama API"""
        model = parameters.get("model", "llama3:8b")
        
        try:
            response = await self.http_client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": parameters.get("temperature", 0.7)
                    }
                },
                timeout=parameters.get("timeout", 60)
            )
            response.raise_for_status()
            
            return response.json()["response"]
            
        except httpx.HTTPError as e:
            logger.error(f"Ollama request failed: {e}")
            raise
            
    async def generate_image(self, prompt: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Not supported by Ollama"""
        raise NotImplementedError("Ollama does not support image generation")
