"""
Unit tests for Domain Models
"""

import pytest
from datetime import datetime
from domain.models import (
    Task, TaskType, Priority, ContextMode,
    TaskRequest, TaskResponse
)


class TestTask:
    """Tests for Task dataclass"""
    
    def test_task_creation(self):
        """Test basic task creation"""
        task = Task(
            id="test-1",
            type=TaskType.TEXT_GENERATION,
            prompt="Hello world",
            priority=Priority.MEDIUM,
            parameters={}
        )
        
        assert task.id == "test-1"
        assert task.type == TaskType.TEXT_GENERATION
        assert task.priority == Priority.MEDIUM
        assert task.result is None
        assert task.error is None
    
    def test_task_priority_ordering(self):
        """Test that tasks are ordered by priority"""
        high_priority = Task(
            id="high",
            type=TaskType.TEXT_GENERATION,
            prompt="urgent",
            priority=Priority.HIGH,
            parameters={}
        )
        
        low_priority = Task(
            id="low",
            type=TaskType.TEXT_GENERATION,
            prompt="not urgent",
            priority=Priority.LOW,
            parameters={}
        )
        
        # Higher priority (lower value) should come first
        assert high_priority < low_priority
        
    def test_task_ordering_same_priority_by_time(self):
        """Tasks with same priority ordered by creation time"""
        task1 = Task(
            id="first",
            type=TaskType.TEXT_GENERATION,
            prompt="first",
            priority=Priority.MEDIUM,
            parameters={},
            created_at=datetime(2024, 1, 1, 10, 0, 0)
        )
        
        task2 = Task(
            id="second",
            type=TaskType.TEXT_GENERATION,
            prompt="second",
            priority=Priority.MEDIUM,
            parameters={},
            created_at=datetime(2024, 1, 1, 11, 0, 0)
        )
        
        assert task1 < task2


class TestTaskRequest:
    """Tests for TaskRequest Pydantic model"""
    
    def test_request_defaults(self):
        """Test default values"""
        request = TaskRequest(
            type=TaskType.IMAGE_GENERATION,
            prompt="a cat"
        )
        
        assert request.priority == Priority.MEDIUM
        assert request.timeout == 300
        assert request.parameters == {}
        
    def test_request_validation(self):
        """Test that invalid data raises error"""
        with pytest.raises(Exception):
            TaskRequest(type="invalid", prompt="test")


class TestEnums:
    """Tests for enum values"""
    
    def test_task_types(self):
        """All task types should be defined"""
        assert TaskType.TEXT_GENERATION.value == "text"
        assert TaskType.IMAGE_GENERATION.value == "image"
        assert TaskType.TRANSCRIPTION.value == "transcription"
        
    def test_context_modes(self):
        """All context modes should be defined"""
        assert ContextMode.TEXT_HEAVY.value == "text_heavy"
        assert ContextMode.CREATIVE.value == "creative"
        assert ContextMode.AUDIO_PROCESSING.value == "audio"
        assert ContextMode.HYBRID.value == "hybrid"
