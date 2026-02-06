"""
AI Provider Port - Interface for AI generation services
"""

from typing import Protocol, Any, Dict


class AIProviderPort(Protocol):
    """Protocol for AI generation providers"""
    
    async def generate_text(self, prompt: str, parameters: Dict[str, Any]) -> str:
        """
        Generate text response
        
        Args:
            prompt: Input text prompt
            parameters: Generation parameters (model, temperature, etc)
            
        Returns:
            Generated text content
        """
        ...
    
    async def generate_image(self, prompt: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate image(s)
        
        Args:
            prompt: Input prompt or workflow
            parameters: Generation parameters (timeout, sizes, etc)
            
        Returns:
            Dictionary with generation results (e.g. {"image_path": "..."})
        """
        ...
