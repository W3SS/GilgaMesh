"""
Docker Adapter - Implements ContainerRuntimePort using Docker SDK
"""

import docker
from docker.errors import NotFound, APIError
import asyncio
import logging
from typing import Optional

from ports.container_runtime import (
    ContainerRuntimePort,
    ContainerState,
    ContainerStats
)


logger = logging.getLogger(__name__)


class DockerAdapter:
    """Docker container runtime adapter"""
    
    def __init__(self, docker_client: Optional[docker.DockerClient] = None):
        """
        Initialize Docker adapter
        
        Args:
            docker_client: Optional docker client (defaults to from_env())
        """
        self.docker_client = docker_client or docker.from_env()
        
    async def start(self, container_name: str) -> bool:
        """Start a Docker container"""
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            container = await loop.run_in_executor(
                None,
                self.docker_client.containers.get,
                container_name
            )
            
            if container.status != "running":
                await loop.run_in_executor(None, container.start)
                logger.info(f"Started container: {container_name}")
            else:
                logger.debug(f"Container already running: {container_name}")
                
            return True
            
        except NotFound:
            logger.error(f"Container not found: {container_name}")
            return False
        except APIError as e:
            logger.error(f"Docker API error starting {container_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error starting {container_name}: {e}")
            return False
    
    async def stop(self, container_name: str, timeout: int = 10) -> bool:
        """Stop a Docker container gracefully"""
        try:
            loop = asyncio.get_event_loop()
            container = await loop.run_in_executor(
                None,
                self.docker_client.containers.get,
                container_name
            )
            
            if container.status == "running":
                await loop.run_in_executor(None, container.stop, timeout)
                logger.info(f"Stopped container: {container_name}")
            else:
                logger.debug(f"Container already stopped: {container_name}")
                
            return True
            
        except NotFound:
            logger.error(f"Container not found: {container_name}")
            return False
        except APIError as e:
            logger.error(f"Docker API error stopping {container_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error stopping {container_name}: {e}")
            return False
    
    async def get_status(self, container_name: str) -> Optional[ContainerState]:
        """Get container status"""
        try:
            loop = asyncio.get_event_loop()
            container = await loop.run_in_executor(
                None,
                self.docker_client.containers.get,
                container_name
            )
            
            # Reload to get latest status
            await loop.run_in_executor(None, container.reload)
            
            return ContainerState(container.status)
            
        except NotFound:
            return None
        except Exception as e:
            logger.error(f"Error getting status for {container_name}: {e}")
            return None
    
    async def get_stats(self, container_name: str) -> Optional[ContainerStats]:
        """Get container resource statistics"""
        try:
            loop = asyncio.get_event_loop()
            container = await loop.run_in_executor(
                None,
                self.docker_client.containers.get,
                container_name
            )
            
            # Get stats (stream=False for single snapshot)
            stats = await loop.run_in_executor(
                None,
                lambda: container.stats(stream=False)
            )
            
            # Calculate CPU percentage
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                       stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                          stats["precpu_stats"]["system_cpu_usage"]
            cpu_percent = (cpu_delta / system_delta) * 100.0 if system_delta > 0 else 0.0
            
            # Calculate memory usage in MB
            memory_mb = stats["memory_stats"]["usage"] / (102 * 1024)
            
            status = ContainerState(container.status)
            
            return ContainerStats(
                cpu_percent=cpu_percent,
                memory_mb=int(memory_mb),
                status=status
            )
            
        except NotFound:
            return None
        except Exception as e:
            logger.error(f"Error getting stats for {container_name}: {e}")
            return None
