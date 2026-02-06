"""
Domain Models for Prometheus Orchestrator
"""

from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pydantic import BaseModel


class TaskType(str, Enum):
    """Types of tasks processed by the orchestrator"""
    TEXT_GENERATION = "text"
    IMAGE_GENERATION = "image"
    AUDIO_GENERATION = "audio"
    VIDEO_GENERATION = "video"
    TRANSCRIPTION = "transcription"
    SYSTEM_COMMAND = "system"


class Priority(int, Enum):
    """Execution priority"""
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


class ContextMode(str, Enum):
    """System operation modes"""
    TEXT_HEAVY = "text_heavy"
    CREATIVE = "creative"
    AUDIO_PROCESSING = "audio"
    HYBRID = "hybrid"


class TaskRequest(BaseModel):
    """Task submission request"""
    type: TaskType
    prompt: str
    priority: Priority = Priority.MEDIUM
    parameters: Dict[str, Any] = {}
    user_id: Optional[str] = None
    timeout: int = 300


class TaskResponse(BaseModel):
    """Task execution response"""
    task_id: str
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float
    vram_used: int


@dataclass
class Task:
    """Internal task representation"""
    id: str
    type: TaskType
    prompt: str
    priority: Priority
    parameters: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    
    def __lt__(self, other):
        """Priority queue ordering"""
        if self.priority != other.priority:
            return self.priority.value < other.priority.value
        return self.created_at < other.created_at
