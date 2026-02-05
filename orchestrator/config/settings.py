"""
Orchestrator Configuration Management
Uses pydantic-settings to load configuration from environment variables with sensible defaults
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict


class VRAMSettings(BaseSettings):
    """VRAM limits for different models (in MB)"""
    model_config = SettingsConfigDict(env_prefix='VRAM_')
    
    # Ollama models
    ollama_llama3_8b: int = 6000
    ollama_llama3_70b: int = 40000
    
    # ComfyUI models
    comfyui_sdxl: int = 8500
    comfyui_flux: int = 10000
    
    # Whisper models
    whisper_large: int = 3000
    whisper_medium: int = 1500
    
    # System limits
    total: int = 12000  # RTX 4070 Super
    safety_margin: int = 1000
    
    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary format matching original VRAM_LIMITS"""
        return {
            "ollama_llama3_8b": self.ollama_llama3_8b,
            "ollama_llama3_70b": self.ollama_llama3_70b,
            "comfyui_sdxl": self.comfyui_sdxl,
            "comfyui_flux": self.comfyui_flux,
            "whisper_large": self.whisper_large,
            "whisper_medium": self.whisper_medium,
        }


class OrchestratorSettings(BaseSettings):
    """Main orchestrator configuration"""
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')
    
    # Service URLs
    ollama_url: str = "http://ollama:11434"
    comfyui_url: str = "http://comfyui:8188"
    whisper_url: str = "http://whisper:9000"
    qdrant_url: str = "http://qdrant:6333"
    notifications_url: str = "http://notifications:9003"
    
    # VRAM Configuration
    vram: VRAMSettings = VRAMSettings()
    
    @property
    def vram_limits(self) -> Dict[str, int]:
        """Legacy property for backward compatibility"""
        return self.vram.to_dict()
    
    @property
    def vram_total(self) -> int:
        """Legacy property for backward compatibility"""
        return self.vram.total
    
    @property
    def vram_safety_margin(self) -> int:
        """Legacy property for backward compatibility"""
        return self.vram.safety_margin


# Global settings instance
settings = OrchestratorSettings()
