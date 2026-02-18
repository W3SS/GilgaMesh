"""
PsutilSystemAdapter — Cross-platform implementation of SystemMonitorPort.

Uses psutil for process and network enumeration.
Results are cached with a configurable TTL to minimize CPU overhead.
"""

import asyncio
import logging
import time
from typing import List, Optional
from functools import lru_cache

import psutil

from ports.system_monitor import (
    SystemMonitorPort,
    NetworkConnection,
    BackgroundService,
    ConnectionState,
)

logger = logging.getLogger(__name__)

# Ports considered suspicious regardless of context.
# Source: SentinelConfig.SUSPICIOUS_PORTS in sentinel_service.py
SUSPICIOUS_PORTS: frozenset[int] = frozenset({
    22,    # SSH (unexpected on workstation)
    23,    # Telnet
    3389,  # RDP
    4444,  # Metasploit default
    5900,  # VNC
    6667,  # IRC (often malware C2)
    31337, # Back Orifice
})

# Cache TTL values (seconds)
_PORTS_CACHE_TTL = 5.0
_SERVICES_CACHE_TTL = 10.0


class PsutilSystemAdapter:
    """
    Implements SystemMonitorPort using psutil (cross-platform).

    Thread-safe via asyncio.to_thread for blocking psutil calls.
    """

    def __init__(
        self,
        ports_cache_ttl: float = _PORTS_CACHE_TTL,
        services_cache_ttl: float = _SERVICES_CACHE_TTL,
    ) -> None:
        self._ports_cache_ttl = ports_cache_ttl
        self._services_cache_ttl = services_cache_ttl

        self._ports_cache: List[NetworkConnection] = []
        self._ports_cache_at: float = 0.0

        self._services_cache: List[BackgroundService] = []
        self._services_cache_at: float = 0.0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def get_open_ports(self) -> List[NetworkConnection]:
        """Return all open TCP/UDP ports, with suspicious-flag annotation."""
        now = time.monotonic()
        if now - self._ports_cache_at < self._ports_cache_ttl:
            return self._ports_cache

        connections = await asyncio.to_thread(self._scan_connections)
        self._ports_cache = connections
        self._ports_cache_at = now
        return connections

    async def get_background_services(self) -> List[BackgroundService]:
        """Return running background processes sorted by CPU usage."""
        now = time.monotonic()
        if now - self._services_cache_at < self._services_cache_ttl:
            return self._services_cache

        services = await asyncio.to_thread(self._scan_processes)
        self._services_cache = services
        self._services_cache_at = now
        return services

    async def is_port_open(self, port: int) -> bool:
        """Check if a specific local port has any connection."""
        connections = await self.get_open_ports()
        return any(c.local_port == port for c in connections)

    # ------------------------------------------------------------------
    # Blocking helpers (run via asyncio.to_thread)
    # ------------------------------------------------------------------

    def _scan_connections(self) -> List[NetworkConnection]:
        """Enumerate all TCP and UDP connections using psutil."""
        results: List[NetworkConnection] = []

        try:
            # kind="inet" covers IPv4 + IPv6 TCP and UDP
            raw = psutil.net_connections(kind="inet")
        except psutil.AccessDenied:
            logger.warning("psutil.net_connections: AccessDenied — running without admin privileges")
            return results
        except Exception as exc:
            logger.error("psutil.net_connections failed: %s", exc)
            return results

        pid_name_map = self._build_pid_name_map()

        for conn in raw:
            if not conn.laddr:
                continue

            local_port = conn.laddr.port
            local_addr = conn.laddr.ip

            remote_addr: Optional[str] = None
            if conn.raddr:
                remote_addr = f"{conn.raddr.ip}:{conn.raddr.port}"

            state_str = (conn.status or "NONE").upper()
            try:
                state = ConnectionState(state_str)
            except ValueError:
                state = ConnectionState.NONE

            pid = conn.pid
            process_name = pid_name_map.get(pid) if pid else None

            # Derive protocol from psutil type (SOCK_STREAM=TCP, SOCK_DGRAM=UDP)
            import socket
            if conn.type == socket.SOCK_STREAM:
                protocol = "tcp"
            elif conn.type == socket.SOCK_DGRAM:
                protocol = "udp"
            else:
                protocol = "unknown"

            results.append(
                NetworkConnection(
                    local_port=local_port,
                    local_address=local_addr,
                    remote_address=remote_addr,
                    protocol=protocol,
                    state=state,
                    pid=pid,
                    process_name=process_name,
                    suspicious=local_port in SUSPICIOUS_PORTS,
                )
            )

        results.sort(key=lambda c: c.local_port)
        return results

    def _scan_processes(self) -> List[BackgroundService]:
        """Enumerate running processes with resource usage."""
        results: List[BackgroundService] = []

        for proc in psutil.process_iter(
            attrs=["pid", "name", "status", "cpu_percent", "memory_info", "username", "create_time"]
        ):
            try:
                info = proc.info
                memory_mb = (
                    info["memory_info"].rss / (1024 * 1024)
                    if info.get("memory_info")
                    else 0.0
                )
                results.append(
                    BackgroundService(
                        pid=info["pid"],
                        name=info.get("name") or "unknown",
                        status=info.get("status") or "unknown",
                        cpu_percent=info.get("cpu_percent") or 0.0,
                        memory_mb=round(memory_mb, 2),
                        username=info.get("username"),
                        create_time=info.get("create_time") or 0.0,
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        results.sort(key=lambda s: s.cpu_percent, reverse=True)
        return results

    @staticmethod
    def _build_pid_name_map() -> dict[int, str]:
        """Build a PID→name mapping in a single psutil pass."""
        mapping: dict[int, str] = {}
        for proc in psutil.process_iter(attrs=["pid", "name"]):
            try:
                mapping[proc.info["pid"]] = proc.info.get("name") or "unknown"
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return mapping
