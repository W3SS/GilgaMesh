"""
Container Runtime Port - Interface for container orchestration
"""

from typing import Protocol, Dict, Any, Optional
from enum import Enum


class ContainerState(str, Enum):
    """Container state enumeration"""
    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    RESTARTING = "restarting"
    DEAD = "dead"
    CREATED = "created"


class ContainerStats:
    """Container statistics"""
    def __init__(self, cpu_percent: float, memory_mb: int, status: ContainerState):
        self.cpu_percent = cpu_percent
        self.memory_mb = memory_mb
        self.status = status


class ContainerRuntimePort(Protocol):
    """Protocol for container runtime operations"""
    
    async def start(self, container_name: str) -> bool:
        """
        Start a container
        
        Args:
            container_name: Name of the container to start
            
        Returns:
            True if started successfully
        """
        ...
    
    async def stop(self, container_name: str, timeout: int = 10) -> bool:
        """
        Stop a container gracefully
        
        Args:
            container_name: Name of the container to stop
            timeout: Timeout in seconds
            
        Returns:
            True if stopped successfully
        """
        ...
    
    async def get_status(self, container_name: str) -> Optional[ContainerState]:
        """
        Get container status
        
        Args:
            container_name: Name of the container
            
        Returns:
            Container state or None if not found
        """
        ...
    
    async def get_stats(self, container_name: str) -> Optional[ContainerStats]:
        """
        Get container resource usage statistics
        
        Args:
            container_name: Name of the container
            
        Returns:
            Container stats or None if not found/not running
        """
        ...
