"""
Service Health Model - Moved to domain
"""

from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


class ServiceState(str, Enum):
    """Possible service states"""
    STOPPED = "stopped"
    STARTING = "starting"
    READY = "ready"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class ServiceHealth:
    """Service health status"""
    name: str
    state: ServiceState
    vram_allocated: int
    last_used: datetime
    error_count: int = 0
    url: Optional[str] = None
