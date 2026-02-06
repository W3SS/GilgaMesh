"""
ComfyUI Adapter - Implements AIProviderPort for image generation
"""

import httpx
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any

from ports.ai_provider import AIProviderPort
from config.settings import settings


logger = logging.getLogger(__name__)


class ComfyUIAdapter:
    """ComfyUI provider adapter"""
    
    def __init__(self, base_url: str = settings.comfyui_url, http_client: httpx.AsyncClient = None):
        self.base_url = base_url
        self.http_client = http_client or httpx.AsyncClient(timeout=30.0)
        
    async def generate_text(self, prompt: str, parameters: Dict[str, Any]) -> str:
        """Not supported by ComfyUI"""
        raise NotImplementedError("ComfyUI does not support text generation")
            
    async def generate_image(self, prompt: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate image using ComfyUI workflow
        
        Args:
            prompt: JSON string or dict representing the workflow
            parameters: timeout, etc.
        """
        try:
            # Parse prompt if string, though ComfyUI expects dict usually in 'prompt' field
            # Assuming 'prompt' arg here IS the workflow object (dict)
            workflow = prompt
            
            response = await self.http_client.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow},
                timeout=parameters.get("timeout", 10.0) # Timeout for the queuing request, not generation
            )
            response.raise_for_status()
            
            prompt_id = response.json()["prompt_id"]
            
            # Wait for completion (polling)
            max_wait = parameters.get("timeout", 300)
            image_path = await self._wait_for_result(prompt_id, max_wait)
            
            return {
                "prompt_id": prompt_id,
                "image_path": image_path,
                "workflow": workflow
            }
            
        except httpx.HTTPError as e:
            logger.error(f"ComfyUI request failed: {e}")
            raise

    async def _wait_for_result(self, prompt_id: str, max_wait: int) -> str:
        """Wait for ComfyUI to finish processing"""
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < max_wait:
            try:
                response = await self.http_client.get(f"{self.base_url}/history/{prompt_id}")
                history = response.json()
                
                if prompt_id in history:
                    outputs = history[prompt_id].get("outputs", {})
                    # Find first generated image
                    for node_id, node_output in outputs.items():
                        if "images" in node_output:
                            image_info = node_output["images"][0]
                            return f"/output/{image_info['filename']}"
                
                await asyncio.sleep(2)  # Poll every 2s
            
            except Exception as e:
                logger.warning(f"Error polling ComfyUI: {e}")
                await asyncio.sleep(2)
        
        raise TimeoutError(f"ComfyUI did not complete in {max_wait}s")
