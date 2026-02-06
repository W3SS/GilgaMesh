"""
Unit tests for ContextDomainService
"""

import pytest
from domain.context_service import ContextDomainService, VRAMBudget
from domain.models import ContextMode, TaskType


class TestVRAMBudget:
    """Tests for VRAMBudget dataclass"""
    
    def test_usage_percent(self):
        """Test usage percentage calculation"""
        budget = VRAMBudget(total=12000, used=6000, available=5000, can_allocate=True)
        assert budget.usage_percent == 50.0
        
    def test_zero_total_vram(self):
        """Edge case: zero total VRAM"""
        budget = VRAMBudget(total=0, used=0, available=0, can_allocate=False)
        assert budget.usage_percent == 0


class TestContextDomainService:
    """Tests for ContextDomainService"""
    
    @pytest.fixture
    def service(self):
        """Create service with fixed values for testing"""
        return ContextDomainService(vram_total=12000, safety_margin=1000)
    
    def test_calculate_vram_budget(self, service):
        """Test VRAM budget calculation"""
        current_usage = {"ollama": 6000}
        budget = service.calculate_vram_budget(current_usage)
        
        assert budget.total == 12000
        assert budget.used == 6000
        assert budget.available == 5000  # 12000 - 6000 - 1000 margin
        assert budget.can_allocate is True
        
    def test_budget_no_room(self, service):
        """Test when no room available"""
        current_usage = {"ollama": 6000, "comfyui": 5500}
        budget = service.calculate_vram_budget(current_usage)
        
        assert budget.used == 11500
        assert budget.available == 0  # Would be negative, clamped to 0
        assert budget.can_allocate is False
        
    def test_determine_target_mode_text(self, service):
        """Text generation should use TEXT_HEAVY mode"""
        mode = service.determine_target_mode(TaskType.TEXT_GENERATION)
        assert mode == ContextMode.TEXT_HEAVY
        
    def test_determine_target_mode_image(self, service):
        """Image generation should use CREATIVE mode"""
        mode = service.determine_target_mode(TaskType.IMAGE_GENERATION)
        assert mode == ContextMode.CREATIVE
        
    def test_determine_target_mode_audio(self, service):
        """Transcription should use AUDIO_PROCESSING mode"""
        mode = service.determine_target_mode(TaskType.TRANSCRIPTION)
        assert mode == ContextMode.AUDIO_PROCESSING
        
    def test_can_fit_service_true(self, service):
        """Service should fit when VRAM is available"""
        current_usage = {"ollama": 2000}
        can_fit = service.can_fit_service(6000, current_usage)
        assert can_fit is True
        
    def test_can_fit_service_false(self, service):
        """Service should not fit when VRAM is insufficient"""
        current_usage = {"ollama": 8000}
        can_fit = service.can_fit_service(6000, current_usage)
        assert can_fit is False
        
    def test_get_services_to_stop_text_mode(self, service):
        """Switching to TEXT_HEAVY should stop comfyui and whisper"""
        active = ["ollama", "comfyui", "whisper"]
        to_stop = service.get_services_to_stop(ContextMode.TEXT_HEAVY, active)
        
        assert set(to_stop) == {"comfyui", "whisper"}
        
    def test_get_services_to_stop_creative_mode(self, service):
        """Switching to CREATIVE should stop ollama and whisper"""
        active = ["ollama", "comfyui"]
        to_stop = service.get_services_to_stop(ContextMode.CREATIVE, active)
        
        assert set(to_stop) == {"ollama"}
        
    def test_get_services_to_stop_nothing_running(self, service):
        """No services to stop when nothing is running"""
        to_stop = service.get_services_to_stop(ContextMode.TEXT_HEAVY, [])
        assert to_stop == []
