"""
Unit tests for PsutilSystemAdapter and SystemMonitorPort contract.

Tests use unittest.mock to avoid real psutil I/O calls.
"""

import asyncio
import socket
from unittest.mock import MagicMock, patch
import pytest

from adapters.psutil_system_adapter import PsutilSystemAdapter, SUSPICIOUS_PORTS
from ports.system_monitor import ConnectionState, NetworkConnection, BackgroundService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_conn(lport, raddr=None, status="LISTEN", pid=1234, conn_type=None):
    """Build a mock psutil net_connection object."""
    if conn_type is None:
        conn_type = socket.SOCK_STREAM

    conn = MagicMock()
    conn.laddr = MagicMock()
    conn.laddr.port = lport
    conn.laddr.ip = "0.0.0.0"
    conn.raddr = raddr
    conn.status = status
    conn.pid = pid
    conn.type = conn_type
    return conn


def _make_proc(pid, name, status="running", cpu=0.0, mem_rss=1024 * 1024 * 10):
    """Build a mock psutil process info dict."""
    proc = MagicMock()
    mem_info = MagicMock()
    mem_info.rss = mem_rss
    proc.info = {
        "pid": pid,
        "name": name,
        "status": status,
        "cpu_percent": cpu,
        "memory_info": mem_info,
        "username": "testuser",
        "create_time": 1700000000.0,
    }
    return proc


# ---------------------------------------------------------------------------
# Tests: get_open_ports
# ---------------------------------------------------------------------------

class TestGetOpenPorts:

    @pytest.fixture
    def adapter(self):
        return PsutilSystemAdapter(ports_cache_ttl=0.0, services_cache_ttl=0.0)

    @pytest.mark.asyncio
    async def test_returns_listening_port(self, adapter):
        mock_conn = _make_conn(lport=8005, status="LISTEN", pid=100)
        with patch("psutil.net_connections", return_value=[mock_conn]), \
             patch("psutil.process_iter", return_value=[]):
            result = await adapter.get_open_ports()

        assert len(result) == 1
        assert result[0].local_port == 8005
        assert result[0].state == ConnectionState.LISTEN
        assert result[0].protocol == "tcp"
        assert result[0].suspicious is False

    @pytest.mark.asyncio
    async def test_flags_suspicious_port(self, adapter):
        for suspicious_port in [4444, 31337]:
            mock_conn = _make_conn(lport=suspicious_port, status="LISTEN", pid=999)
            with patch("psutil.net_connections", return_value=[mock_conn]), \
                 patch("psutil.process_iter", return_value=[]):
                result = await adapter.get_open_ports()

            assert result[0].suspicious is True, f"Port {suspicious_port} should be flagged"

    @pytest.mark.asyncio
    async def test_normal_port_not_suspicious(self, adapter):
        mock_conn = _make_conn(lport=11434, status="LISTEN", pid=200)  # Ollama
        with patch("psutil.net_connections", return_value=[mock_conn]), \
             patch("psutil.process_iter", return_value=[]):
            result = await adapter.get_open_ports()

        assert result[0].suspicious is False

    @pytest.mark.asyncio
    async def test_sorted_by_port_ascending(self, adapter):
        conns = [
            _make_conn(lport=9000),
            _make_conn(lport=8005),
            _make_conn(lport=11434),
        ]
        with patch("psutil.net_connections", return_value=conns), \
             patch("psutil.process_iter", return_value=[]):
            result = await adapter.get_open_ports()

        ports = [c.local_port for c in result]
        assert ports == sorted(ports)

    @pytest.mark.asyncio
    async def test_access_denied_returns_empty(self, adapter):
        import psutil
        with patch("psutil.net_connections", side_effect=psutil.AccessDenied(0, "")):
            result = await adapter.get_open_ports()

        assert result == []

    @pytest.mark.asyncio
    async def test_is_port_open_true(self, adapter):
        mock_conn = _make_conn(lport=8005)
        with patch("psutil.net_connections", return_value=[mock_conn]), \
             patch("psutil.process_iter", return_value=[]):
            assert await adapter.is_port_open(8005) is True

    @pytest.mark.asyncio
    async def test_is_port_open_false(self, adapter):
        mock_conn = _make_conn(lport=8005)
        with patch("psutil.net_connections", return_value=[mock_conn]), \
             patch("psutil.process_iter", return_value=[]):
            assert await adapter.is_port_open(9999) is False


# ---------------------------------------------------------------------------
# Tests: get_background_services
# ---------------------------------------------------------------------------

class TestGetBackgroundServices:

    @pytest.fixture
    def adapter(self):
        return PsutilSystemAdapter(ports_cache_ttl=0.0, services_cache_ttl=0.0)

    @pytest.mark.asyncio
    async def test_returns_process_list(self, adapter):
        procs = [_make_proc(pid=1, name="ollama", cpu=25.0)]
        with patch("psutil.process_iter", return_value=procs):
            result = await adapter.get_background_services()

        assert len(result) == 1
        assert result[0].name == "ollama"
        assert result[0].cpu_percent == 25.0

    @pytest.mark.asyncio
    async def test_sorted_by_cpu_desc(self, adapter):
        procs = [
            _make_proc(pid=1, name="low", cpu=5.0),
            _make_proc(pid=2, name="high", cpu=80.0),
            _make_proc(pid=3, name="mid", cpu=40.0),
        ]
        with patch("psutil.process_iter", return_value=procs):
            result = await adapter.get_background_services()

        cpu_values = [s.cpu_percent for s in result]
        assert cpu_values == sorted(cpu_values, reverse=True)

    @pytest.mark.asyncio
    async def test_memory_converted_to_mb(self, adapter):
        procs = [_make_proc(pid=1, name="test", mem_rss=1024 * 1024 * 256)]  # 256 MB
        with patch("psutil.process_iter", return_value=procs):
            result = await adapter.get_background_services()

        assert result[0].memory_mb == pytest.approx(256.0, rel=0.01)


# ---------------------------------------------------------------------------
# Tests: suspicious ports constant
# ---------------------------------------------------------------------------

class TestSuspiciousPorts:

    def test_known_dangerous_ports_present(self):
        assert 4444 in SUSPICIOUS_PORTS   # Metasploit
        assert 31337 in SUSPICIOUS_PORTS  # Back Orifice
        assert 3389 in SUSPICIOUS_PORTS   # RDP
        assert 5900 in SUSPICIOUS_PORTS   # VNC

    def test_common_service_ports_absent(self):
        """Gilgamesh's own service ports must NOT be in the suspicious set."""
        gilgamesh_ports = {8005, 8001, 11434, 8188, 9000, 6333, 9093, 3000}
        overlap = gilgamesh_ports & SUSPICIOUS_PORTS
        assert overlap == set(), f"Service ports flagged as suspicious: {overlap}"
