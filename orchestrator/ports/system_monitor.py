"""
System Monitor Port — Interface for open-port and background-service discovery.

Follows the typing.Protocol pattern established in the project.
Implementations must NOT be imported in domain/.
"""

from typing import Protocol, List, Optional
from dataclasses import dataclass
from enum import Enum


class ConnectionState(str, Enum):
    """TCP connection state"""
    ESTABLISHED = "ESTABLISHED"
    LISTEN = "LISTEN"
    TIME_WAIT = "TIME_WAIT"
    CLOSE_WAIT = "CLOSE_WAIT"
    SYN_SENT = "SYN_SENT"
    SYN_RECV = "SYN_RECV"
    CLOSED = "CLOSED"
    NONE = "NONE"


@dataclass
class NetworkConnection:
    """Represents a single open network connection / listening port."""
    local_port: int
    local_address: str
    remote_address: Optional[str]
    protocol: str          # "tcp" | "udp"
    state: ConnectionState
    pid: Optional[int]
    process_name: Optional[str]
    suspicious: bool       # True if port is in the known-suspicious set


@dataclass
class BackgroundService:
    """Represents a running background process / system service."""
    pid: int
    name: str
    status: str            # psutil process status string
    cpu_percent: float
    memory_mb: float
    username: Optional[str]
    create_time: float     # Unix timestamp


class SystemMonitorPort(Protocol):
    """
    Port for system-level monitoring: open ports and background services.

    Implementations:
      - PsutilSystemAdapter  (cross-platform, primary)
      - WmiSystemAdapter     (Windows-only, richer data, future)
    """

    async def get_open_ports(self) -> List[NetworkConnection]:
        """
        Return all open TCP/UDP ports on the local machine.

        Results are cached for 5 seconds to limit psutil overhead.
        Suspicious ports are flagged with suspicious=True.

        Returns:
            List of NetworkConnection dataclasses, sorted by local_port asc.
        """
        ...

    async def get_background_services(self) -> List[BackgroundService]:
        """
        Return all running background processes with resource usage.

        Results are cached for 10 seconds.

        Returns:
            List of BackgroundService dataclasses, sorted by cpu_percent desc.
        """
        ...

    async def is_port_open(self, port: int) -> bool:
        """
        Check whether a specific local port is open (listening or established).

        Args:
            port: TCP/UDP port number (1-65535)

        Returns:
            True if any connection exists on this port.
        """
        ...
