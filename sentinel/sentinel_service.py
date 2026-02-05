"""
PROMETHEUS SENTINEL - Windows Security & Monitoring Agent
Monitora sistema operacional, rede, processos e expõe API para o Orchestrator
"""

import os
import sys
import json
import logging
import asyncio
import hashlib
import subprocess
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import defaultdict

import psutil
import GPUtil
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
import httpx
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Windows-specific imports
if sys.platform == "win32":
    import win32evtlog
    import win32evtlogutil
    import win32security
    import win32con
    import wmi

# ============================================================================
# CONFIGURAÇÃO E LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("sentinel.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("SentinelService")

# Métricas Prometheus
SECURITY_EVENTS = Counter('sentinel_security_events_total', 'Total de eventos de segurança', ['type', 'severity'])
PROCESS_KILLS = Counter('sentinel_process_kills_total', 'Processos encerrados', ['reason'])
CPU_USAGE = Gauge('sentinel_cpu_percent', 'Uso de CPU')
RAM_USAGE = Gauge('sentinel_ram_percent', 'Uso de RAM')
VRAM_USAGE = Gauge('sentinel_vram_mb', 'Uso de VRAM', ['gpu_id'])
DISK_USAGE = Gauge('sentinel_disk_percent', 'Uso de disco', ['drive'])
NETWORK_ANOMALIES = Counter('sentinel_network_anomalies_total', 'Anomalias de rede detectadas', ['type'])
SCAN_DURATION = Histogram('sentinel_scan_duration_seconds', 'Duração de scans', ['scan_type'])

# ============================================================================
# CONFIGURAÇÕES DE SEGURANÇA
# ============================================================================

class SentinelConfig:
    """Configurações do Sentinel (Dinâmicas)"""
    
    _instance = None
    _config_file = "sentinel_config.json"
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SentinelConfig, cls).__new__(cls)
            cls._instance.load()
        return cls._instance
    
    def __init__(self):
        # Default values if load fails
        if not hasattr(self, "initialized"):
            self.API_KEY = os.getenv("SENTINEL_API_KEY", "prometheus-secure-key-change-me")
            self.PROTECTED_PROCESSES = {
                "csrss.exe", "winlogon.exe", "services.exe", "lsass.exe",
                "smss.exe", "wininit.exe", "dwm.exe", "explorer.exe",
                "System", "Registry", "svchost.exe"
            }
            self.KILLABLE_PROCESSES = {
                "chrome.exe", "firefox.exe", "msedge.exe",
                "discord.exe", "spotify.exe", "steam.exe",
                "notepad.exe", "calc.exe"
            }
            self.SUSPICIOUS_NAMES = {
                "mimikatz", "psexec", "procdump", "netcat",
                "nmap", "wireshark", "tcpdump"
            }
            self.SUSPICIOUS_PORTS = {22, 23, 3389, 4444, 5900, 6667, 31337}
            
            self.CPU_THRESHOLD = 95
            self.RAM_THRESHOLD = 90
            self.VRAM_THRESHOLD = 11000
            self.DISK_THRESHOLD = 90
            self.MAX_CONNECTIONS_PER_PROCESS = 100
            
            self.CRITICAL_PATHS = [
                r"C:\Windows\System32",
                r"C:\Windows\SysWOW64",
                r"C:\Program Files",
                r"C:\Users\*\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup"
            ]
            self.CRITICAL_EVENT_IDS = {
                1074: "Sistema sendo desligado",
                4624: "Logon bem-sucedido",
                4625: "Logon falhou",
                4648: "Tentativa de logon com credenciais explícitas",
                4720: "Conta de usuário criada",
                4732: "Membro adicionado a grupo de segurança",
                4756: "Membro adicionado a grupo universal de segurança",
                7045: "Novo serviço instalado",
                41: "Sistema reiniciado sem shutdown apropriado"
            }
            self.initialized = True

    def load(self):
        """Carrega configurações do disco"""
        if os.path.exists(self._config_file):
            try:
                with open(self._config_file, "r") as f:
                    data = json.load(f)
                    self.PROTECTED_PROCESSES = set(data.get("protected", [])) | self.PROTECTED_PROCESSES
                    self.KILLABLE_PROCESSES = set(data.get("killable", [])) | self.KILLABLE_PROCESSES
                    self.SUSPICIOUS_NAMES = set(data.get("suspicious", [])) | self.SUSPICIOUS_NAMES
                    logger.info("Configuration loaded from disk")
            except Exception as e:
                logger.error(f"Error loading config: {e}")

    def save(self):
        """Salva configurações no disco"""
        data = {
            "protected": list(self.PROTECTED_PROCESSES),
            "killable": list(self.KILLABLE_PROCESSES),
            "suspicious": list(self.SUSPICIOUS_NAMES)
        }
        try:
            with open(self._config_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.info("Configuration saved to disk")
        except Exception as e:
            logger.error(f"Error saving config: {e}")

# Global config instance
config = SentinelConfig()

# ============================================================================
# MODELOS DE DADOS
# ============================================================================

class SystemStats(BaseModel):
    """Estatísticas do sistema"""
    cpu_percent: float
    ram_percent: float
    ram_available_gb: float
    vram_usage: List[Dict[str, Any]]
    disk_usage: Dict[str, float]
    gpu_temperature: List[float]
    timestamp: datetime = Field(default_factory=datetime.now)

class ProcessInfo(BaseModel):
    """Informações de processo"""
    pid: int
    name: str
    username: Optional[str]
    cpu_percent: float
    memory_mb: float
    status: str
    create_time: float
    num_threads: int
    connections: int = 0

class NetworkConnection(BaseModel):
    """Conexão de rede"""
    pid: int
    process_name: str
    local_addr: str
    local_port: int
    remote_addr: str
    remote_port: int
    status: str

class SecurityEvent(BaseModel):
    """Evento de segurança do Windows"""
    event_id: int
    source: str
    message: str
    timestamp: datetime
    severity: str

class ThreatAssessment(BaseModel):
    """Avaliação de ameaça"""
    level: str  # low, medium, high, critical
    score: int  # 0-100
    indicators: List[str]
    recommended_actions: List[str]

class ActionRequest(BaseModel):
    """Requisição de ação"""
    action: str
    target: Optional[str] = None
    parameters: Dict[str, Any] = {}
    approved_by_user: bool = False

# ============================================================================
# SENTINEL CORE
# ============================================================================

class SentinelCore:
    """
    Núcleo do Sentinel - Monitoramento e Segurança
    """
    
    def __init__(self):
        self.wmi_client = wmi.WMI() if sys.platform == "win32" else None
        self.baseline_hashes: Dict[str, str] = {}
        self.network_baseline: Dict[int, int] = defaultdict(int)  # PID -> num connections
        self.threat_history: List[Dict] = []
        self.killed_processes: List[Dict] = []
        
        # Cache de processos para detecção de anomalias
        self.process_history: Dict[int, List[float]] = defaultdict(list)  # PID -> [CPU samples]
        
        # Integração com Qdrant (para memória de decisões)
        self.qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.http_client = httpx.AsyncClient(timeout=10.0)
        
        logger.info("🛡️  Sentinel Core initialized")
        
        self.is_running = False
        self.monitoring_task = None
    
    async def start_monitoring(self):
        """Inicia loop de monitoramento ativo"""
        self.is_running = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("👀 Active monitoring loop started")

    async def _monitoring_loop(self):
        """Loop principal de vigilância"""
        loop_count = 0
        while self.is_running:
            try:
                # 1. Coleta e Analisa Processos
                processes = await self.get_processes()
                threats = await self.analyze_process_threats(processes)
                
                # Se ameaça crítica, toma ação
                if threats.level == "critical":
                    logger.warning(f"🚨 CRITICAL THREAT DETECTED: Score {threats.score}")
                    # Aqui poderia ter lógica de auto-kill se configurado
                    
                # 2. Verifica Anomalias de Recursos
                stats = await self.get_system_stats()
                resource_anomalies = await self.check_resource_anomalies(stats)
                if resource_anomalies:
                    for anomaly in resource_anomalies:
                        logger.warning(f"⚠️ {anomaly}")
                
                # 3. Verifica Rede (A cada 60s - loop_count % 6 == 0)
                if loop_count % 6 == 0:
                    network_anomalies = await self.get_network_connections(suspicious_only=True)
                    # O método já loga avisos se encontrar portas suspeitas
                
                loop_count += 1
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
            
            await asyncio.sleep(10) # Intervalo de scan
    
    # ========================================================================
    # MONITORAMENTO DE HARDWARE
    # ========================================================================
    
    async def get_system_stats(self) -> SystemStats:
        """Coleta estatísticas do sistema"""
        
        # CPU e RAM
        cpu_percent = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        
        CPU_USAGE.set(cpu_percent)
        RAM_USAGE.set(ram.percent)
        
        # GPU (NVIDIA via GPUtil)
        vram_usage = []
        gpu_temps = []
        
        try:
            gpus = GPUtil.getGPUs()
            for gpu in gpus:
                vram_usage.append({
                    "gpu_id": gpu.id,
                    "name": gpu.name,
                    "vram_used_mb": gpu.memoryUsed,
                    "vram_total_mb": gpu.memoryTotal,
                    "vram_percent": (gpu.memoryUsed / gpu.memoryTotal) * 100,
                    "temperature": gpu.temperature,
                    "load_percent": gpu.load * 100
                })
                gpu_temps.append(gpu.temperature)
                
                VRAM_USAGE.labels(gpu_id=str(gpu.id)).set(gpu.memoryUsed)
        except Exception as e:
            logger.warning(f"Could not get GPU stats: {e}")
        
        # Discos
        disk_usage = {}
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disk_usage[partition.device] = usage.percent
                DISK_USAGE.labels(drive=partition.device).set(usage.percent)
            except PermissionError:
                pass
        
        return SystemStats(
            cpu_percent=cpu_percent,
            ram_percent=ram.percent,
            ram_available_gb=ram.available / (1024**3),
            vram_usage=vram_usage,
            disk_usage=disk_usage,
            gpu_temperature=gpu_temps
        )
    
    async def check_resource_anomalies(self, stats: SystemStats) -> List[str]:
        """Detecta anomalias de recursos"""
        anomalies = []
        
        if stats.cpu_percent > config.CPU_THRESHOLD:
            anomalies.append(f"CPU usage critical: {stats.cpu_percent:.1f}%")
            SECURITY_EVENTS.labels(type="resource", severity="warning").inc()
        
        if stats.ram_percent > config.RAM_THRESHOLD:
            anomalies.append(f"RAM usage critical: {stats.ram_percent:.1f}%")
            SECURITY_EVENTS.labels(type="resource", severity="warning").inc()
        
        for vram in stats.vram_usage:
            if vram["vram_used_mb"] > config.VRAM_THRESHOLD:
                anomalies.append(f"VRAM usage high on GPU {vram['gpu_id']}: {vram['vram_used_mb']}MB")
        
        for drive, usage in stats.disk_usage.items():
            if usage > config.DISK_THRESHOLD:
                anomalies.append(f"Disk {drive} almost full: {usage:.1f}%")
        
        return anomalies
    
    # ========================================================================
    # MONITORAMENTO DE PROCESSOS
    # ========================================================================
    
    async def get_processes(self, 
                           top_n: Optional[int] = None,
                           sort_by: str = "cpu") -> List[ProcessInfo]:
        """Lista processos do sistema"""
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 
                                         'memory_info', 'status', 'create_time', 
                                         'num_threads']):
            try:
                info = proc.info
                
                # Conta conexões de rede
                connections = 0
                try:
                    connections = len(proc.connections())
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
                
                processes.append(ProcessInfo(
                    pid=info['pid'],
                    name=info['name'],
                    username=info.get('username'),
                    cpu_percent=info['cpu_percent'] or 0,
                    memory_mb=info['memory_info'].rss / (1024 * 1024) if info.get('memory_info') else 0,
                    status=info['status'],
                    create_time=info['create_time'],
                    num_threads=info['num_threads'],
                    connections=connections
                ))
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Ordena
        if sort_by == "cpu":
            processes.sort(key=lambda p: p.cpu_percent, reverse=True)
        elif sort_by == "memory":
            processes.sort(key=lambda p: p.memory_mb, reverse=True)
        
        if top_n:
            processes = processes[:top_n]
        
        return processes
    
    async def analyze_process_threats(self, processes: List[ProcessInfo]) -> ThreatAssessment:
        """Analisa processos em busca de ameaças"""
        indicators = []
        score = 0
        
        for proc in processes:
            # Nome suspeito
            if any(sus in proc.name.lower() for sus in config.SUSPICIOUS_NAMES):
                indicators.append(f"Suspicious process name: {proc.name} (PID {proc.pid})")
                score += 30
                SECURITY_EVENTS.labels(type="suspicious_process", severity="high").inc()
            
            # CPU muito alto por muito tempo
            self.process_history[proc.pid].append(proc.cpu_percent)
            if len(self.process_history[proc.pid]) > 10:
                self.process_history[proc.pid].pop(0)
                
                avg_cpu = sum(self.process_history[proc.pid]) / len(self.process_history[proc.pid])
                if avg_cpu > 80:
                    indicators.append(f"Sustained high CPU: {proc.name} (PID {proc.pid}) - {avg_cpu:.1f}%")
                    score += 15
            
            # Muitas conexões de rede
            if proc.connections > config.MAX_CONNECTIONS_PER_PROCESS:
                indicators.append(f"Excessive network connections: {proc.name} ({proc.connections} connections)")
                score += 20
                NETWORK_ANOMALIES.labels(type="excessive_connections").inc()
            
            # Processo sem username (possível rootkit)
            if not proc.username and proc.name not in config.PROTECTED_PROCESSES:
                indicators.append(f"Process without username: {proc.name} (PID {proc.pid})")
                score += 25
        
        # Determina nível
        if score >= 70:
            level = "critical"
        elif score >= 40:
            level = "high"
        elif score >= 20:
            level = "medium"
        else:
            level = "low"
        
        # Recomendações
        recommendations = []
        if score > 40:
            recommendations.append("Review suspicious processes immediately")
            recommendations.append("Check network connections for unusual activity")
        if score > 70:
            recommendations.append("Consider isolating system from network")
            recommendations.append("Run full antimalware scan")
        
        return ThreatAssessment(
            level=level,
            score=min(score, 100),
            indicators=indicators,
            recommended_actions=recommendations
        )
    
    async def kill_process(self, pid: int, reason: str = "user_request") -> Dict[str, Any]:
        """Encerra um processo"""
        try:
            proc = psutil.Process(pid)
            proc_name = proc.name()
            
            # Verifica proteção
            if proc_name in config.PROTECTED_PROCESSES:
                raise ValueError(f"Cannot kill protected process: {proc_name}")
            
            # Termina processo
            proc.terminate()
            
            # Aguarda até 5 segundos
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                # Força kill
                proc.kill()
            
            # Registra
            kill_record = {
                "pid": pid,
                "name": proc_name,
                "reason": reason,
                "timestamp": datetime.now().isoformat()
            }
            self.killed_processes.append(kill_record)
            
            PROCESS_KILLS.labels(reason=reason).inc()
            logger.info(f"✅ Killed process: {proc_name} (PID {pid}) - Reason: {reason}")
            
            # Salva decisão no Qdrant (para aprendizado)
            await self._store_decision("kill_process", {
                "target": proc_name,
                "reason": reason,
                "success": True
            })
            
            return {
                "status": "killed",
                "pid": pid,
                "name": proc_name,
                "reason": reason
            }
        
        except psutil.NoSuchProcess:
            raise HTTPException(status_code=404, detail=f"Process {pid} not found")
        
        except psutil.AccessDenied:
            raise HTTPException(status_code=403, detail=f"Access denied to kill process {pid}")
        
        except ValueError as e:
            raise HTTPException(status_code=403, detail=str(e))
    
    # ========================================================================
    # MONITORAMENTO DE REDE
    # ========================================================================
    
    async def get_network_connections(self, 
                                     suspicious_only: bool = False) -> List[NetworkConnection]:
        """Lista conexões de rede ativas"""
        connections = []
        
        for conn in psutil.net_connections(kind='inet'):
            if conn.status != 'ESTABLISHED':
                continue
            
            try:
                proc = psutil.Process(conn.pid) if conn.pid else None
                proc_name = proc.name() if proc else "Unknown"
                
                # Filtra suspeitos se requisitado
                if suspicious_only:
                    if conn.raddr and conn.raddr.port not in config.SUSPICIOUS_PORTS:
                        continue
                
                connections.append(NetworkConnection(
                    pid=conn.pid or 0,
                    process_name=proc_name,
                    local_addr=conn.laddr.ip if conn.laddr else "",
                    local_port=conn.laddr.port if conn.laddr else 0,
                    remote_addr=conn.raddr.ip if conn.raddr else "",
                    remote_port=conn.raddr.port if conn.raddr else 0,
                    status=conn.status
                ))
                
                # Alerta portas suspeitas
                if conn.raddr and conn.raddr.port in config.SUSPICIOUS_PORTS:
                    logger.warning(f"⚠️  Suspicious port detected: {proc_name} -> {conn.raddr.ip}:{conn.raddr.port}")
                    NETWORK_ANOMALIES.labels(type="suspicious_port").inc()
            
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        return connections
    
    # ========================================================================
    # WINDOWS EVENT LOG
    # ========================================================================
    
    async def get_security_events(self, 
                                  last_minutes: int = 60,
                                  critical_only: bool = True) -> List[SecurityEvent]:
        """Lê eventos do Windows Event Log"""
        if sys.platform != "win32":
            return []
        
        events = []
        
        try:
            hand = win32evtlog.OpenEventLog(None, "Security")
            flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
            
            cutoff_time = datetime.now() - timedelta(minutes=last_minutes)
            
            while True:
                event_records = win32evtlog.ReadEventLog(hand, flags, 0)
                if not event_records:
                    break
                
                for event in event_records:
                    event_time = datetime.fromtimestamp(int(event.TimeGenerated))
                    
                    if event_time < cutoff_time:
                        break
                    
                    event_id = event.EventID & 0xFFFF
                    
                    # Filtra apenas críticos se requisitado
                    if critical_only and event_id not in config.CRITICAL_EVENT_IDS:
                        continue
                    
                    severity = "high" if event_id in [4625, 4648, 7045] else "medium"
                    
                    events.append(SecurityEvent(
                        event_id=event_id,
                        source=event.SourceName,
                        message=config.CRITICAL_EVENT_IDS.get(event_id, "Event logged"),
                        timestamp=event_time,
                        severity=severity
                    ))
                    
                    SECURITY_EVENTS.labels(type="windows_event", severity=severity).inc()
            
            win32evtlog.CloseEventLog(hand)
        
        except Exception as e:
            logger.error(f"Error reading event log: {e}")
        
        return events[:50]  # Limita a 50 eventos
    
    # ========================================================================
    # ANTIMALWARE
    # ========================================================================
    
    async def run_defender_scan(self, scan_type: str = "quick") -> Dict[str, Any]:
        """Executa scan do Windows Defender"""
        if sys.platform != "win32":
            return {"error": "Windows Defender only available on Windows"}
        
        scan_types = {
            "quick": "1",
            "full": "2",
            "custom": "3"
        }
        
        if scan_type not in scan_types:
            raise ValueError(f"Invalid scan type. Use: {', '.join(scan_types.keys())}")
        
        defender_path = r"C:\Program Files\Windows Defender\MpCmdRun.exe"
        
        if not os.path.exists(defender_path):
            return {"error": "Windows Defender not found"}
        
        logger.info(f"🔍 Starting {scan_type} scan...")
        
        with SCAN_DURATION.labels(scan_type=scan_type).time():
            try:
                # Executa scan em background (não bloqueante)
                process = await asyncio.create_subprocess_exec(
                    defender_path,
                    "-Scan",
                    "-ScanType", scan_types[scan_type],
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                output = stdout.decode('utf-8', errors='ignore')
                
                # Parse resultado
                threats_found = "threats were detected" in output.lower()
                
                result = {
                    "scan_type": scan_type,
                    "status": "completed",
                    "threats_found": threats_found,
                    "output": output,
                    "timestamp": datetime.now().isoformat()
                }
                
                if threats_found:
                    logger.warning("⚠️  Threats detected by Windows Defender!")
                    SECURITY_EVENTS.labels(type="malware_detected", severity="critical").inc()
                else:
                    logger.info("✅ Scan completed - No threats found")
                
                return result
            
            except Exception as e:
                logger.error(f"Scan failed: {e}")
                return {
                    "scan_type": scan_type,
                    "status": "failed",
                    "error": str(e)
                }
    
    async def update_defender_signatures(self) -> Dict[str, Any]:
        """Atualiza assinaturas do Windows Defender"""
        if sys.platform != "win32":
            return {"error": "Windows only"}
        
        defender_path = r"C:\Program Files\Windows Defender\MpCmdRun.exe"
        
        logger.info("📥 Updating Defender signatures...")
        
        try:
            result = subprocess.run(
                [defender_path, "-SignatureUpdate"],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            return {
                "status": "completed" if result.returncode == 0 else "failed",
                "output": result.stdout
            }
        
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "error": "Update took too long"}
        
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    # ========================================================================
    # FILE INTEGRITY MONITORING
    # ========================================================================
    
    async def create_file_baseline(self, paths: List[str] = None) -> Dict[str, int]:
        """Cria baseline de hashes de arquivos críticos"""
        if paths is None:
            paths = config.CRITICAL_PATHS
        
        logger.info("📸 Creating file integrity baseline...")
        
        baseline = {}
        
        for path_pattern in paths:
            # Expande wildcards
            path_obj = Path(path_pattern.replace("*", ""))
            
            if not path_obj.exists():
                continue
            
            try:
                for file in path_obj.rglob("*.exe"):
                    if file.is_file():
                        file_hash = await self._hash_file(file)
                        baseline[str(file)] = file_hash
                        self.baseline_hashes[str(file)] = file_hash
            
            except PermissionError:
                logger.warning(f"Permission denied: {path_pattern}")
        
        logger.info(f"✅ Baseline created: {len(baseline)} files")
        return {"files_hashed": len(baseline)}
    
    async def check_file_integrity(self) -> List[str]:
        """Verifica integridade de arquivos contra baseline"""
        if not self.baseline_hashes:
            return ["No baseline exists. Run create_file_baseline first."]
        
        logger.info("🔍 Checking file integrity...")
        
        anomalies = []
        
        for file_path, baseline_hash in self.baseline_hashes.items():
            if not os.path.exists(file_path):
                anomalies.append(f"File deleted: {file_path}")
                SECURITY_EVENTS.labels(type="file_deleted", severity="high").inc()
                continue
            
            current_hash = await self._hash_file(Path(file_path))
            
            if current_hash != baseline_hash:
                anomalies.append(f"File modified: {file_path}")
                SECURITY_EVENTS.labels(type="file_modified", severity="high").inc()
                logger.warning(f"⚠️  File integrity violation: {file_path}")
        
        return anomalies
    
    async def _hash_file(self, file_path: Path) -> str:
        """Calcula SHA256 de um arquivo"""
        sha256 = hashlib.sha256()
        
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            logger.error(f"Error hashing {file_path}: {e}")
            return ""
    
    # ========================================================================
    # INTEGRAÇÃO COM QDRANT (Memória de Decisões)
    # ========================================================================
    
    async def _store_decision(self, action_type: str, data: Dict[str, Any]):
        """Armazena decisão no Qdrant para aprendizado"""
        try:
            # Cria embedding simples (em produção, usar modelo de embedding real)
            text = f"{action_type} {json.dumps(data)}"
            
            # Mock de embedding (substituir por modelo real)
            embedding = [hash(text[i:i+10]) % 100 / 100 for i in range(0, min(len(text), 1536), 10)]
            embedding = embedding + [0.0] * (1536 - len(embedding))  # Pad to 1536 dims
            
            payload = {
                "action_type": action_type,
                "data": data,
                "timestamp": datetime.now().isoformat(),
                "approved": True
            }
            
            await self.http_client.put(
                f"{self.qdrant_url}/collections/sentinel_decisions/points",
                json={
                    "points": [{
                        "id": hash(text) % (2**31),
                        "vector": embedding,
                        "payload": payload
                    }]
                }
            )
        
        except Exception as e:
            logger.warning(f"Could not store decision in Qdrant: {e}")
    
    async def query_similar_decisions(self, action_type: str, context: Dict) -> List[Dict]:
        """Busca decisões similares no histórico"""
        try:
            text = f"{action_type} {json.dumps(context)}"
            
            # Mock embedding
            embedding = [hash(text[i:i+10]) % 100 / 100 for i in range(0, min(len(text), 1536), 10)]
            embedding = embedding + [0.0] * (1536 - len(embedding))
            
            response = await self.http_client.post(
                f"{self.qdrant_url}/collections/sentinel_decisions/points/search",
                json={
                    "vector": embedding,
                    "limit": 5,
                    "with_payload": True
                }
            )
            
            results = response.json()
            return results.get("result", [])
        
        except Exception as e:
            logger.warning(f"Could not query Qdrant: {e}")
            return []

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Prometheus Sentinel API",
    description="Security & Monitoring Service for Windows",
    version="2.0.0"
)

sentinel = SentinelCore()

# Security
api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Depends(api_key_header)):
    """Verifica API key"""
    if api_key != config.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.on_event("startup")
async def startup():
    """Inicializa Sentinel"""
    # Inicia métricas Prometheus
    start_http_server(9091)
    
    # Cria baseline de arquivos
    asyncio.create_task(sentinel.create_file_baseline())
    
    logger.info("🛡️  Sentinel Service started")
    
    # Inicia loop de monitoramento
    await sentinel.start_monitoring()

@app.get("/config/whitelist")
async def get_whitelist(api_key: str = Depends(verify_api_key)):
    """Retorna lista de processos protegidos"""
    return {"protected": list(config.PROTECTED_PROCESSES)}

@app.post("/config/whitelist")
async def add_whitelist(process_name: str, api_key: str = Depends(verify_api_key)):
    """Adiciona processo à whitelist"""
    config.PROTECTED_PROCESSES.add(process_name)
    config.save()
    return {"status": "added", "process": process_name}

@app.get("/config/blacklist")
async def get_blacklist(api_key: str = Depends(verify_api_key)):
    """Retorna lista de processos bloqueados/killable"""
    return {"killable": list(config.KILLABLE_PROCESSES)}

@app.post("/config/blacklist")
async def add_blacklist(process_name: str, api_key: str = Depends(verify_api_key)):
    """Adiciona processo à blacklist"""
    config.KILLABLE_PROCESSES.add(process_name)
    config.save()
    return {"status": "added", "process": process_name}

@app.get("/health")
async def health():
    """Healthcheck"""
    return {"status": "healthy", "service": "sentinel", "timestamp": datetime.now()}

@app.get("/system/stats", response_model=SystemStats)
async def get_stats(_: str = Depends(verify_api_key)):
    """Retorna estatísticas do sistema"""
    return await sentinel.get_system_stats()

@app.get("/system/processes")
async def get_processes(
    top_n: Optional[int] = 20,
    sort_by: str = "cpu",
    _: str = Depends(verify_api_key)
):
    """Lista processos"""
    processes = await sentinel.get_processes(top_n=top_n, sort_by=sort_by)
    return {"processes": [p.dict() for p in processes]}

@app.get("/security/threat-assessment")
async def threat_assessment(_: str = Depends(verify_api_key)):
    """Avalia ameaças do sistema"""
    processes = await sentinel.get_processes()
    assessment = await sentinel.analyze_process_threats(processes)
    
    stats = await sentinel.get_system_stats()
    resource_anomalies = await sentinel.check_resource_anomalies(stats)
    
    return {
        "threat_assessment": assessment.dict(),
        "resource_anomalies": resource_anomalies
    }

@app.post("/action/kill-process")
async def kill_process(
    request: ActionRequest,
    _: str = Depends(verify_api_key)
):
    """Encerra um processo"""
    if "pid" not in request.parameters:
        raise HTTPException(status_code=400, detail="PID required")
    
    pid = request.parameters["pid"]
    reason = request.parameters.get("reason", "user_request")
    
    # Verifica se precisa aprovação
    proc = psutil.Process(pid)
    if proc.name() not in SentinelConfig.KILLABLE_PROCESSES and not request.approved_by_user:
        return {
            "status": "approval_required",
            "process": proc.name(),
            "pid": pid,
            "message": "This process requires explicit user approval to kill"
        }
    
    return await sentinel.kill_process(pid, reason)

@app.get("/network/connections")
async def network_connections(
    suspicious_only: bool = False,
    _: str = Depends(verify_api_key)
):
    """Lista conexões de rede"""
    connections = await sentinel.get_network_connections(suspicious_only=suspicious_only)
    return {"connections": [c.dict() for c in connections]}

@app.get("/security/events")
async def security_events(
    last_minutes: int = 60,
    critical_only: bool = True,
    _: str = Depends(verify_api_key)
):
    """Lê eventos de segurança do Windows"""
    events = await sentinel.get_security_events(last_minutes, critical_only)
    return {"events": [e.dict() for e in events]}

@app.post("/security/scan")
async def defender_scan(
    background_tasks: BackgroundTasks,
    scan_type: str = "quick",
    _: str = Depends(verify_api_key)
):
    """Executa scan do Windows Defender"""
    # Roda em background para não bloquear
    background_tasks.add_task(sentinel.run_defender_scan, scan_type)
    
    return {
        "status": "started",
        "scan_type": scan_type,
        "message": "Scan started in background. Check logs for results."
    }

@app.post("/security/update-signatures")
async def update_signatures(_: str = Depends(verify_api_key)):
    """Atualiza assinaturas do Defender"""
    return await sentinel.update_defender_signatures()

@app.get("/integrity/check")
async def check_integrity(_: str = Depends(verify_api_key)):
    """Verifica integridade de arquivos"""
    anomalies = await sentinel.check_file_integrity()
    return {
        "anomalies": anomalies,
        "status": "clean" if not anomalies else "violations_detected"
    }

@app.post("/integrity/create-baseline")
async def create_baseline(_: str = Depends(verify_api_key)):
    """Cria baseline de integridade"""
    result = await sentinel.create_file_baseline()
    return result

@app.get("/history/kills")
async def kill_history(_: str = Depends(verify_api_key)):
    """Histórico de processos encerrados"""
    return {"kills": sentinel.killed_processes[-50:]}  # Últimos 50

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    logger.info("🚀 Starting Sentinel Service...")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=9000,
        log_level="info"
    )
