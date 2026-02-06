"""
Context Domain Service - Pure business logic for context management
No I/O dependencies - testable in isolation
"""

from typing import Dict, Optional, List
from dataclasses import dataclass
from domain.models import ContextMode, TaskType
from config.settings import settings


@dataclass
class VRAMBudget:
    """VRAM allocation result"""
    total: int
    used: int
    available: int
    can_allocate: bool
    
    @property
    def usage_percent(self) -> float:
        return (self.used / self.total) * 100 if self.total > 0 else 0


class ContextDomainService:
    """
    Pure domain logic for context switching decisions.
    No I/O, no external dependencies - only business rules.
    """
    
    def __init__(self, vram_total: int = None, safety_margin: int = None):
        self.vram_total = vram_total or settings.vram.total
        self.safety_margin = safety_margin or settings.vram.safety_margin
        
    def calculate_vram_budget(self, current_usage: Dict[str, int]) -> VRAMBudget:
        """
        Calculate available VRAM budget
        
        Args:
            current_usage: Dict mapping service names to VRAM usage in MB
            
        Returns:
            VRAMBudget with allocation details
        """
        used = sum(current_usage.values())
        available = self.vram_total - used - self.safety_margin
        
        return VRAMBudget(
            total=self.vram_total,
            used=used,
            available=max(0, available),
            can_allocate=available > 0
        )
    
    def determine_target_mode(self, task_type: TaskType) -> ContextMode:
        """
        Determine which context mode is needed for a task type
        
        Args:
            task_type: The type of task to execute
            
        Returns:
            The ContextMode required for this task
        """
        mode_mapping = {
            TaskType.TEXT_GENERATION: ContextMode.TEXT_HEAVY,
            TaskType.IMAGE_GENERATION: ContextMode.CREATIVE,
            TaskType.AUDIO_GENERATION: ContextMode.AUDIO_PROCESSING,
            TaskType.VIDEO_GENERATION: ContextMode.CREATIVE,
            TaskType.TRANSCRIPTION: ContextMode.AUDIO_PROCESSING,
            TaskType.SYSTEM_COMMAND: ContextMode.TEXT_HEAVY,  # Default
        }
        return mode_mapping.get(task_type, ContextMode.TEXT_HEAVY)
    
    def can_fit_service(self, service_vram: int, current_usage: Dict[str, int]) -> bool:
        """
        Check if a service can fit in available VRAM
        
        Args:
            service_vram: VRAM required by the service in MB
            current_usage: Current VRAM usage by other services
            
        Returns:
            True if service can be loaded
        """
        budget = self.calculate_vram_budget(current_usage)
        return service_vram <= budget.available
    
    def get_services_to_stop(
        self,
        target_mode: ContextMode,
        active_services: List[str]
    ) -> List[str]:
        """
        Determine which services to stop for a mode transition
        
        Args:
            target_mode: The mode we're transitioning to
            active_services: Currently active service names
            
        Returns:
            List of service names that should be stopped
        """
        # Services needed for each mode
        mode_services = {
            ContextMode.TEXT_HEAVY: {"ollama"},
            ContextMode.CREATIVE: {"comfyui"},
            ContextMode.AUDIO_PROCESSING: {"whisper"},
            ContextMode.HYBRID: {"ollama", "comfyui"},
        }
        
        needed = mode_services.get(target_mode, set())
        active_set = set(active_services)
        
        # Stop everything not needed
        return list(active_set - needed)
