"""
PROMETHEUS MESH - Resource Orchestrator
Gerencia ciclo de vida de containers Docker com otimização de VRAM
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from collections import deque
import json
import os

import docker
from docker.errors import NotFound, APIError
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import httpx
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Configuration
from config.settings import settings

# Ports & Adapters (Iterations 2 & 3)
# Ports & Adapters (Iterations 2, 3 & 4)
from adapters.discord_adapter import DiscordAdapter, NullNotificationAdapter
from adapters.docker_adapter import DockerAdapter
from adapters.ollama_adapter import OllamaAdapter
from adapters.comfyui_adapter import ComfyUIAdapter

# Domain Models (Iteration 4)
from domain.models import (
    Task, TaskRequest, TaskResponse, ServiceHealth,
    TaskType, Priority, ContextMode, ServiceState
)

# ============================================================================
# CONFIGURAÇÃO E LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("PrometheusOrchestrator")

# Métricas Prometheus
TASK_COUNTER = Counter('prometheus_tasks_total', 'Total de tarefas processadas', ['type', 'status'])
SWAP_DURATION = Histogram('prometheus_swap_seconds', 'Tempo de swap de contexto')
VRAM_USAGE = Gauge('prometheus_vram_mb', 'Uso estimado de VRAM', ['service'])
QUEUE_SIZE = Gauge('prometheus_queue_size', 'Tamanho da fila de tarefas')

# ============================================================================
# ENUMS E CONSTANTES
# ============================================================================

# Domain Models imported from domain.models (Iteration 4 - Domain Isolation)

# ============================================================================
# ORQUESTRADOR PRINCIPAL
# ============================================================================

class PrometheusOrchestrator:
    """
    Orquestrador central que gerencia:
    - Fila de tarefas com priorização
    - Swap inteligente de containers
    - Monitoramento de VRAM
    - Healthchecks e recuperação de falhas
    """
    
    def __init__(
        self,
        notification_service: Optional[Any] = None,  # NotificationPort
        container_runtime: Optional[Any] = None,  # ContainerRuntimePort
        text_provider: Optional[Any] = None,  # AIProviderPort
        image_provider: Optional[Any] = None   # AIProviderPort
    ):
        # Adapters (Iteration 2 & 3 - Dependency Injection)
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Notification adapter (default to Null for safety)
        self.notification_service = notification_service or NullNotificationAdapter()
        
        # Container runtime adapter (default to Docker)
        if container_runtime is None:
            docker_client = docker.from_env()
            self.container_runtime = DockerAdapter(docker_client)
        else:
            self.container_runtime = container_runtime
            
        # AI Providers (Iteration 4)
        self.text_provider = text_provider or OllamaAdapter(http_client=self.http_client)
        self.image_provider = image_provider or ComfyUIAdapter(http_client=self.http_client)
        
        # Keep docker_client reference for compatibility (will be removed in Iteration 4)
        self.docker_client = docker.from_env() if container_runtime is None else None
        
        # Estado do sistema
        self.current_mode: ContextMode = ContextMode.TEXT_HEAVY
        self.services: Dict[str, ServiceHealth] = {}
        self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.active_tasks: Dict[str, Task] = {}
        self.history: deque = deque(maxlen=100)
        
        # Locks para evitar race conditions
        self.swap_lock = asyncio.Lock()
        self.vram_lock = asyncio.Lock()
        
        # Worker de processamento
        self.worker_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # Cache de decisões preditivas
        self.last_user_prompts: deque = deque(maxlen=10)
        self.predicted_next_mode: Optional[ContextMode] = None
        
        # Service URLs from Settings
        self.ollama_url = settings.ollama_url
        self.comfyui_url = settings.comfyui_url
        self.whisper_url = settings.whisper_url
        self.notifications_url = settings.notifications_url
        
        logger.info("🚀 Prometheus Orchestrator initialized")

    async def notify(self, title: str, message: str, priority: str = "normal", channel: str = "discord"):
        """Envia notificação via adapter (Iteration 2)"""
        try:
            await self.notification_service.send(
                title=title,
                message=message,
                priority=priority,  # type: ignore
                channel=channel  # type: ignore
            )
        except Exception as e:
            logger.warning(f"Failed to send notification: {e}")
    
    # ========================================================================
    # INICIALIZAÇÃO E LIFECYCLE
    # ========================================================================
    
    async def start(self):
        """Inicia o orquestrador"""
        logger.info("Starting Prometheus Orchestrator...")
        
        # Descobre containers disponíveis
        await self._discover_services()
        
        # Inicia no modo texto (padrão)
        await self.transition_to(ContextMode.TEXT_HEAVY)
        
        # Inicia worker de processamento
        self.is_running = True
        self.worker_task = asyncio.create_task(self._task_worker())
        
        # Inicia healthcheck periódico
        asyncio.create_task(self._healthcheck_loop())
        
        # Inicia predição de contexto
        asyncio.create_task(self._predictive_warmup_loop())
        
        logger.info("✅ Orchestrator ready")
    
    async def shutdown(self):
        """Desliga gracefully"""
        logger.info("Shutting down orchestrator...")
        self.is_running = False
        
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        
        # Aguarda fila esvaziar (máx 30s)
        try:
            await asyncio.wait_for(self.task_queue.join(), timeout=30.0)
        except asyncio.TimeoutError:
            logger.warning("Queue did not empty in time")
        
        await self.http_client.aclose()
        logger.info("👋 Orchestrator stopped")
    
    async def _discover_services(self):
        """Descobre e registra containers Docker disponíveis"""
        try:
            # We map container names (or service names) to internal configs
            # Assuming container names are prefixed with 'gilgamesh-' based on docker-compose
            # or just rely on service names if using internal docker DNS
            
            service_map = {
                "ollama": {"url": self.ollama_url, "vram": settings.vram.ollama_llama3_8b, "container": "gilgamesh-ollama"},
                "comfyui": {"url": self.comfyui_url, "vram": settings.vram.comfyui_sdxl, "container": "gilgamesh-comfyui"},
                "whisper": {"url": self.whisper_url, "vram": settings.vram.whisper_medium, "container": "gilgamesh-whisper"},
            }
            
            for name, config in service_map.items():
                try:
                    # Check if container exists/is running via docker client
                    # We utilize the container name defined in docker-compose
                    container = self.docker_client.containers.get(config["container"])
                    state = ServiceState.READY if container.status == "running" else ServiceState.STOPPED
                    
                    self.services[name] = ServiceHealth(
                        name=name,
                        state=state,
                        vram_allocated=0 if state == ServiceState.STOPPED else config["vram"],
                        last_used=datetime.now(),
                        url=config["url"]
                    )
                    
                    VRAM_USAGE.labels(service=name).set(self.services[name].vram_allocated)
                    logger.info(f"Discovered service: {name} (state: {state})")
                except NotFound:
                    logger.warning(f"Service container {config['container']} not found")
        
        except Exception as e:
            logger.error(f"Error discovering services: {e}")
    
    # ========================================================================
    # GERENCIAMENTO DE TAREFAS
    # ========================================================================
    
    async def submit_task(self, request: TaskRequest) -> str:
        """Submete uma tarefa para processamento"""
        task = Task(
            id=f"task_{datetime.now().timestamp()}",
            type=request.type,
            prompt=request.prompt,
            priority=request.priority,
            parameters=request.parameters
        )
        
        await self.task_queue.put((task.priority.value, task))
        QUEUE_SIZE.set(self.task_queue.qsize())
        
        self.active_tasks[task.id] = task
        logger.info(f"📝 Task submitted: {task.id} (type: {task.type}, priority: {task.priority})")
        
        # Atualiza histórico para predição
        self.last_user_prompts.append({
            "type": task.type,
            "keywords": self._extract_keywords(request.prompt),
            "timestamp": datetime.now()
        })
        
        return task.id
    
    async def get_task_status(self, task_id: str) -> Optional[TaskResponse]:
        """Consulta status de uma tarefa"""
        if task_id not in self.active_tasks:
            return None
        
        task = self.active_tasks[task_id]
        
        status = "pending"
        if task.completed_at:
            status = "completed" if not task.error else "failed"
        elif task.started_at:
            status = "running"
        
        execution_time = 0.0
        if task.started_at:
            end = task.completed_at or datetime.now()
            execution_time = (end - task.started_at).total_seconds()
        
        return TaskResponse(
            task_id=task.id,
            status=status,
            result=task.result,
            error=task.error,
            execution_time=execution_time,
            vram_used=self._get_current_vram_usage()
        )
    
    async def _task_worker(self):
        """Worker que processa tarefas da fila"""
        logger.info("🔄 Task worker started")
        
        while self.is_running:
            try:
                # Pega próxima tarefa (bloqueante com timeout)
                try:
                    _, task = await asyncio.wait_for(
                        self.task_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                QUEUE_SIZE.set(self.task_queue.qsize())
                
                # Processa tarefa
                task.started_at = datetime.now()
                logger.info(f"▶️  Processing task: {task.id}")
                
                try:
                    result = await self._execute_task(task)
                    task.result = result
                    task.completed_at = datetime.now()
                    
                    TASK_COUNTER.labels(type=task.type, status="success").inc()
                    logger.info(f"✅ Task completed: {task.id}")
                    
                    # Notify
                    await self.notify(
                        title=f"Task Completed: {task.type}",
                        message=f"Task {task.id} finished successfully in {(task.completed_at - task.started_at).total_seconds():.1f}s",
                        priority="normal"
                    )
                
                except Exception as e:
                    task.error = str(e)
                    task.completed_at = datetime.now()
                    
                    TASK_COUNTER.labels(type=task.type, status="error").inc()
                    logger.error(f"❌ Task failed: {task.id} - {e}")
                    
                    # Notify Error
                    await self.notify(
                        title=f"Task Failed: {task.type}",
                        message=f"Task {task.id} failed: {e}",
                        priority="high"
                    )
                
                finally:
                    self.task_queue.task_done()
                    self.history.append(task)
            
            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(1)
    
    async def _execute_task(self, task: Task) -> Any:
        """Executa uma tarefa específica"""
        # Determina modo necessário
        required_mode = self._get_required_mode(task.type)
        
        # Faz swap se necessário
        if self.current_mode != required_mode:
            await self.transition_to(required_mode)
        
        # Delega para executor específico
        if task.type == TaskType.TEXT_GENERATION:
            return await self._execute_text_generation(task)
        
        elif task.type == TaskType.IMAGE_GENERATION:
            return await self._execute_image_generation(task)
        
        elif task.type == TaskType.TRANSCRIPTION:
            return await self._execute_transcription(task)
        
        elif task.type == TaskType.SYSTEM_COMMAND:
            return await self._execute_system_command(task)
        
        else:
            raise NotImplementedError(f"Task type {task.type} not implemented")
    
    # ========================================================================
    # EXECUTORES DE TAREFAS ESPECÍFICAS
    # ========================================================================
    
    async def _execute_text_generation(self, task: Task) -> str:
        """Executa geração de texto via AI Provider"""
        service = self.services.get("ollama")
        if not service or service.state != ServiceState.READY:
            raise RuntimeError("Ollama service not ready")
        
        try:
            return await self.text_provider.generate_text(
                prompt=task.prompt,
                parameters=task.parameters
            )
        except Exception as e:
            logger.error(f"Text generation failed: {e}")
            raise

    async def _execute_image_generation(self, task: Task) -> Dict[str, Any]:
        """Executa geração de imagem via AI Provider"""
        service = self.services.get("comfyui")
        if not service or service.state != ServiceState.READY:
            raise RuntimeError("ComfyUI service not ready")
        
        try:
             # Carrega workflow template
            workflow_path = os.path.join(os.path.dirname(__file__), "..", "ai_services", "comfyui", "workflows", "default.json")
            if os.path.exists(workflow_path):
                 import json
                 with open(workflow_path, "r") as f:
                     workflow_str = f.read()
                     
                 # Parâmetros padrão
                 params = {
                     "prompt": task.prompt,
                     "negative_prompt": task.parameters.get("negative_prompt", "blur, low quality"),
                     "steps": task.parameters.get("steps", 20),
                     "cfg_scale": task.parameters.get("cfg", 7.0),
                     "width": task.parameters.get("width", 512),
                     "height": task.parameters.get("height", 512),
                     "seed": task.parameters.get("seed", 42)
                 }
                 
                 # Substituição simples de template ({{key}})
                 for key, value in params.items():
                     workflow_str = workflow_str.replace(f"{{{{{key}}}}}", str(value))
                 
                 workflow = json.loads(workflow_str)
            else:
                 # Fallback: assume que o workflow veio no parâmetro "workflow"
                 workflow = task.parameters.get("workflow", {})
                 if not workflow:
                     raise ValueError("Workflow not found and not provided in parameters")

            return await self.image_provider.generate_image(
                prompt=workflow,
                parameters=task.parameters
            )
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            raise
    

    
    async def _execute_transcription(self, task: Task) -> str:
        """Executa transcrição de áudio via Whisper"""
        service = self.services.get("whisper")
        if not service or service.state != ServiceState.READY:
            raise RuntimeError("Whisper service not ready")
        
        audio_file = task.parameters.get("audio_file")
        if not audio_file:
            raise ValueError("audio_file parameter required")
        
        # Implementação simplificada (em produção, enviaria arquivo)
        return f"[Transcription placeholder for {audio_file}]"
    
    async def _execute_system_command(self, task: Task) -> Dict[str, Any]:
        """Executa comandos de sistema (via Sentinel)"""
        command = task.parameters.get("command")
        
        # Aqui chamaria a API do Sentinel
        logger.info(f"Executing system command: {command}")
        
        return {"status": "executed", "command": command}
    
    # ========================================================================
    # GERENCIAMENTO DE CONTEXTO E SWAP
    # ========================================================================
    
    async def transition_to(self, target_mode: ContextMode):
        """Faz transição entre modos operacionais"""
        if self.current_mode == target_mode:
            logger.debug(f"Already in mode {target_mode}")
            return
        
        async with self.swap_lock:
            logger.info(f"🔄 Transitioning: {self.current_mode} -> {target_mode}")
            
            with SWAP_DURATION.time():
                try:
                    if target_mode == ContextMode.TEXT_HEAVY:
                        await self._activate_text_mode()
                    
                    elif target_mode == ContextMode.CREATIVE:
                        await self._activate_creative_mode()
                    
                    elif target_mode == ContextMode.AUDIO_PROCESSING:
                        await self._activate_audio_mode()
                    
                    self.current_mode = target_mode
                    logger.info(f"✅ Transition complete: Now in {target_mode}")
                    
                    # Notify Transition
                    await self.notify(
                        title="Context Switched",
                        message=f"System transitioned to {target_mode} mode",
                        priority="low"
                    )
                
                except Exception as e:
                    logger.error(f"❌ Transition failed: {e}")
                    raise
    
    async def _activate_text_mode(self):
        """Ativa modo texto: Ollama ligado, ComfyUI desligado"""
        # Para ComfyUI
        await self._stop_service("comfyui")
        
        # Aguarda VRAM liberar
        await asyncio.sleep(2)
        
        # Inicia Ollama
        await self._start_service("ollama")
        
        # Aguarda carregar modelo
        await self._wait_for_service_ready("ollama", max_wait=30)
    
    async def _activate_creative_mode(self):
        """Ativa modo criativo: ComfyUI ligado, Ollama desligado"""
        # Descarrega modelo do Ollama explicitamente
        if self.services.get("ollama", {}).state == ServiceState.READY:
            try:
                # Força unload do modelo
                await self.http_client.post(
                    f"{self.services['ollama'].url}/api/generate",
                    json={"model": "", "keep_alive": 0}
                )
            except:
                pass
        
        await self._stop_service("ollama")
        await asyncio.sleep(3)  # VRAM demora para liberar completamente
        
        await self._start_service("comfyui")
        await self._wait_for_service_ready("comfyui", max_wait=60)
    
    async def _activate_audio_mode(self):
        """Ativa modo áudio: Whisper ligado"""
        await self._start_service("whisper")
        await self._wait_for_service_ready("whisper", max_wait=20)
    
    # ========================================================================
    # CONTROLE DE CONTAINERS DOCKER
    # ========================================================================
    
    async def _start_service(self, service_name: str):
        """Inicia um container Docker"""
        if service_name not in self.services:
            raise ValueError(f"Unknown service: {service_name}")
        
        service = self.services[service_name]
        
        if service.state == ServiceState.READY:
            logger.debug(f"Service {service_name} already running")
            return
        
        try:
            # Map internal service name to container name
            container_name = f"gilgamesh-{service_name}"
            container = self.docker_client.containers.get(container_name)
            
            logger.info(f"Starting {service_name}...")
            service.state = ServiceState.STARTING
            
            container.start()
            
            # Espera um pouco para o container inicializar
            await asyncio.sleep(2)
            
            logger.info(f"✅ {service_name} started")
        
        except NotFound:
            logger.error(f"Container {service_name} not found")
            service.state = ServiceState.ERROR
            raise
        
        except APIError as e:
            logger.error(f"Failed to start {service_name}: {e}")
            service.state = ServiceState.ERROR
            raise
    
    async def _stop_service(self, service_name: str):
        """Para um container Docker"""
        if service_name not in self.services:
            return
        
        service = self.services[service_name]
        
        if service.state == ServiceState.STOPPED:
            return
        
        try:
            container_name = f"gilgamesh-{service_name}"
            container = self.docker_client.containers.get(container_name)
            
            logger.info(f"Stopping {service_name}...")
            service.state = ServiceState.STOPPING
            
            container.stop(timeout=10)
            
            service.state = ServiceState.STOPPED
            service.vram_allocated = 0
            VRAM_USAGE.labels(service=service_name).set(0)
            
            logger.info(f"🛑 {service_name} stopped")
        
        except NotFound:
            service.state = ServiceState.STOPPED
        
        except APIError as e:
            logger.error(f"Failed to stop {service_name}: {e}")
            raise
    
    async def _wait_for_service_ready(self, service_name: str, max_wait: int = 30):
        """Aguarda serviço ficar pronto (healthcheck)"""
        service = self.services[service_name]
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < max_wait:
            try:
                # Tenta ping no serviço
                # Note: Ollama check is distinct
                url = f"{service.url}/api/tags" if service_name == "ollama" else f"{service.url}/health"
                if service_name == "whisper":
                     url = f"{service.url}/" # Whisper container might just have root or docs
                
                # Simpler check for now: just root or specific known endpoints
                if service_name == "comfyui":
                    url = f"{service.url}/system_stats"
                elif service_name == "whisper":
                    url = f"{service.url}/params" # example

                response = await self.http_client.get(
                   url,
                    timeout=5.0
                )
                
                # Loose check: if we get a response, it's alive-ish
                if response.status_code < 500:
                    service.state = ServiceState.READY
                    service.vram_allocated = VRAM_LIMITS.get(
                        f"{service_name}_sdxl" if service_name == "comfyui" else f"{service_name}_llama3_8b",
                        2000
                    )
                    VRAM_USAGE.labels(service=service_name).set(service.vram_allocated)
                    logger.info(f"✅ {service_name} is ready")
                    return
            
            except:
                pass
            
            await asyncio.sleep(1)
        
        raise TimeoutError(f"{service_name} did not become ready in {max_wait}s")
    
    # ========================================================================
    # HEALTHCHECK E PREDIÇÃO
    # ========================================================================
    
    async def _healthcheck_loop(self):
        """Loop de healthcheck periódico"""
        while self.is_running:
            try:
                for service_name, service in self.services.items():
                    if service.state == ServiceState.READY:
                        try:
                            # Simple ping
                            response = await self.http_client.get(service.url, timeout=3.0)
                            
                            if response.status_code >= 500:
                                logger.warning(f"⚠️  {service_name} healthcheck failed")
                                service.error_count += 1
                        
                        except:
                            service.error_count += 1
                            
                            if service.error_count > 3:
                                logger.error(f"❌ {service_name} appears unhealthy")
                                service.state = ServiceState.ERROR
            
            except Exception as e:
                logger.error(f"Healthcheck error: {e}")
            
            await asyncio.sleep(30)  # Check a cada 30s
    
    async def _predictive_warmup_loop(self):
        """Loop de aquecimento preditivo"""
        while self.is_running:
            try:
                # Analisa últimas 10 requisições
                if len(self.last_user_prompts) >= 3:
                    recent_types = [p["type"] for p in list(self.last_user_prompts)[-3:]]
                    
                    # Se 2 das últimas 3 foram criativas, pré-aquece ComfyUI
                    creative_count = sum(1 for t in recent_types if t in [
                        TaskType.IMAGE_GENERATION,
                        TaskType.VIDEO_GENERATION
                    ])
                    
                    if creative_count >= 2 and self.current_mode != ContextMode.CREATIVE:
                        logger.info("🔮 Predicting creative mode needed, pre-warming...")
                        # Não faz swap completo, mas prepara
                        self.predicted_next_mode = ContextMode.CREATIVE
            
            except Exception as e:
                logger.error(f"Prediction error: {e}")
            
            await asyncio.sleep(10)
    
    # ========================================================================
    # UTILITÁRIOS
    # ========================================================================
    
    def _get_required_mode(self, task_type: TaskType) -> ContextMode:
        """Determina modo necessário para um tipo de tarefa"""
        if task_type == TaskType.TEXT_GENERATION:
            return ContextMode.TEXT_HEAVY
        
        elif task_type in [TaskType.IMAGE_GENERATION, TaskType.VIDEO_GENERATION]:
            return ContextMode.CREATIVE
        
        elif task_type in [TaskType.TRANSCRIPTION, TaskType.AUDIO_GENERATION]:
            return ContextMode.AUDIO_PROCESSING
        
        else:
            return ContextMode.TEXT_HEAVY
    
    def _get_current_vram_usage(self) -> int:
        """Calcula uso atual de VRAM"""
        total = sum(
            service.vram_allocated 
            for service in self.services.values() 
            if service.state == ServiceState.READY
        )
        return total
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extrai keywords para predição (simplificado)"""
        creative_keywords = ["imagem", "desenho", "foto", "arte", "vídeo", "generate", "create"]
        return [kw for kw in creative_keywords if kw in text.lower()]
    
    async def get_status(self) -> Dict[str, Any]:
        """Retorna status completo do orquestrador"""
        return {
            "mode": self.current_mode,
            "queue_size": self.task_queue.qsize(),
            "vram_usage": self._get_current_vram_usage(),
            "vram_total": VRAM_TOTAL,
            "services": {
                name: {
                    "state": service.state,
                    "vram_mb": service.vram_allocated,
                    "errors": service.error_count
                }
                for name, service in self.services.items()
            },
            "recent_tasks": len(self.history)
        }

# ============================================================================
# API FASTAPI
# ============================================================================

app = FastAPI(title="Prometheus Orchestrator API")
orchestrator = PrometheusOrchestrator()

# System monitor adapter (Iteration 6 — Port & Service Discovery)
from adapters.psutil_system_adapter import PsutilSystemAdapter
from prometheus_client import Counter as _Counter

_SUSPICIOUS_PORT_COUNTER = _Counter(
    'sentinel_suspicious_port_detected_total',
    'Suspicious open ports detected by system monitor',
    ['port', 'process_name']
)

_system_monitor = PsutilSystemAdapter()

@app.on_event("startup")
async def startup():
    """Inicializa orquestrador ao subir API"""
    # Inicia métricas Prometheus em porta separada
    start_http_server(9090)
    await orchestrator.start()

@app.on_event("shutdown")
async def shutdown():
    """Desliga gracefully"""
    await orchestrator.shutdown()

@app.post("/tasks", response_model=Dict[str, str])
async def create_task(request: TaskRequest):
    """
    Submete uma nova tarefa
    
    Exemplo:
    ```json
    {
      "type": "text",
      "prompt": "Explique quantum computing",
      "priority": "medium",
      "parameters": {"temperature": 0.8}
    }
    ```
    """
    try:
        task_id = await orchestrator.submit_task(request)
        return {"task_id": task_id, "status": "queued"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """Consulta status de uma tarefa"""
    result = await orchestrator.get_task_status(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result

@app.get("/status")
async def get_status():
    """Retorna status completo do sistema"""
    return await orchestrator.get_status()

@app.post("/mode/{target_mode}")
async def set_mode(target_mode: ContextMode, background_tasks: BackgroundTasks):
    """Força transição de modo (para debug)"""
    background_tasks.add_task(orchestrator.transition_to, target_mode)
    return {"message": f"Transitioning to {target_mode}"}

@app.get("/health")
async def health():
    """Healthcheck da API"""
    return {"status": "healthy", "mode": orchestrator.current_mode}


# ============================================================================
# SYSTEM MONITOR ENDPOINTS (Iteration 6 — Port & Service Discovery)
# ============================================================================

@app.get("/api/v1/system/ports")
async def get_open_ports():
    """
    Lista todas as portas TCP/UDP abertas na máquina local.

    Portas suspeitas (ex: 4444, 31337, 3389) são sinalizadas com suspicious=true.
    Resultados são cacheados por 5 segundos para minimizar overhead de CPU.

    Returns:
        JSON com lista de conexões abertas ordenadas por porta ascendente.
    """
    connections = await _system_monitor.get_open_ports()

    # Increment Prometheus counter for each suspicious port found
    for conn in connections:
        if conn.suspicious:
            _SUSPICIOUS_PORT_COUNTER.labels(
                port=str(conn.local_port),
                process_name=conn.process_name or "unknown"
            ).inc()

    return {
        "count": len(connections),
        "suspicious_count": sum(1 for c in connections if c.suspicious),
        "ports": [
            {
                "local_port": c.local_port,
                "local_address": c.local_address,
                "remote_address": c.remote_address,
                "protocol": c.protocol,
                "state": c.state,
                "pid": c.pid,
                "process_name": c.process_name,
                "suspicious": c.suspicious,
            }
            for c in connections
        ]
    }


@app.get("/api/v1/system/services")
async def get_background_services():
    """
    Lista todos os processos em execução com uso de CPU e memória.

    Resultados são cacheados por 10 segundos.
    Ordenados por uso de CPU decrescente.

    Returns:
        JSON com lista de serviços/processos em background.
    """
    services = await _system_monitor.get_background_services()

    return {
        "count": len(services),
        "services": [
            {
                "pid": s.pid,
                "name": s.name,
                "status": s.status,
                "cpu_percent": s.cpu_percent,
                "memory_mb": s.memory_mb,
                "username": s.username,
                "create_time": s.create_time,
            }
            for s in services
        ]
    }


@app.get("/api/v1/system/ports/{port}")
async def check_port(port: int):
    """
    Verifica se uma porta específica está aberta localmente.

    Args:
        port: Número da porta (1-65535)

    Returns:
        JSON com is_open e detalhes da conexão se encontrada.
    """
    if not 1 <= port <= 65535:
        raise HTTPException(status_code=422, detail="Port must be between 1 and 65535")

    connections = await _system_monitor.get_open_ports()
    matches = [c for c in connections if c.local_port == port]

    return {
        "port": port,
        "is_open": len(matches) > 0,
        "suspicious": port in {22, 23, 3389, 4444, 5900, 6667, 31337},
        "connections": [
            {
                "local_address": c.local_address,
                "remote_address": c.remote_address,
                "protocol": c.protocol,
                "state": c.state,
                "pid": c.pid,
                "process_name": c.process_name,
            }
            for c in matches
        ]
    }


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
