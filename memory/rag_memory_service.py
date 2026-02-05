"""
PROMETHEUS MEMORY - RAG & Incremental Learning
Sistema de memória vetorial persistente para aprendizado de decisões
"""

import os
import json
import asyncio
import logging
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple, Union
from dataclasses import dataclass, field

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
import httpx
from prometheus_client import Counter, Histogram, Gauge, start_http_server

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, Range
from sentence_transformers import SentenceTransformer
import numpy as np

# ============================================================================
# CONFIGURAÇÃO E LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("RAGMemoryService")

# Métricas Prometheus
MEMORY_OPERATIONS = Counter('rag_memory_operations_total', 'Operações de memória', ['operation', 'collection'])
MEMORY_SIZE = Gauge('rag_memory_entries', 'Total de entradas', ['collection'])
SEARCH_LATENCY = Histogram('rag_memory_search_seconds', 'Latência de busca', ['collection'])
EMBEDDING_LATENCY = Histogram('rag_memory_embedding_seconds', 'Latência de geração de embedding')

class MemoryConfig:
    """Configurações de memória"""
    
    QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
    API_KEY = os.getenv("MEMORY_API_KEY", "prometheus-memory-key-change-me")
    
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    EMBEDDING_DIM = 384
    
    # Collections
    COLLECTIONS = {
        "decisions": "Histórico de decisões e automações do sistema",
        "conversations": "Histórico de conversas com o usuário",
        "knowledge": "Base de conhecimento técnico e fatos aprendidos",
        "security": "Eventos de segurança e ameaças conhecidas"
    }
    
    # Políticas de retenção (dias)
    CONVERSATION_RETENTION_DAYS = 30
    DECISION_RETENTION_DAYS = 90

# ============================================================================
# MODELOS DE DADOS
# ============================================================================

class MemoryEntry(BaseModel):
    """Entrada de memória"""
    content: str
    metadata: Dict[str, Any] = {}
    timestamp: datetime = Field(default_factory=datetime.now)
    user_id: Optional[str] = None
    importance: int = 1  # 1-10

class SearchQuery(BaseModel):
    """Query de busca"""
    query: str
    collection: str
    limit: int = 5
    min_score: float = 0.7
    filters: Optional[Dict[str, Any]] = None

class SearchResult(BaseModel):
    """Resultado de busca"""
    id: str
    content: str
    score: float
    metadata: Dict[str, Any]
    timestamp: datetime

class DecisionRecord(BaseModel):
    """Registro de decisão para aprendizado"""
    action: str
    context: Dict[str, Any]
    user_approved: bool
    auto_approved: bool = False
    outcome: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class LearningFeedback(BaseModel):
    """Feedback para aprendizado"""
    decision_id: str
    was_correct: bool
    user_feedback: Optional[str] = None
    corrections: Dict[str, Any] = {}

# ============================================================================
# RAG MEMORY CORE
# ============================================================================

class RAGMemoryCore:
    """
    Sistema de memória RAG com aprendizado incremental
    """
    
    def __init__(self):
        # Qdrant client
        self.qdrant = QdrantClient(
            host=MemoryConfig.QDRANT_HOST,
            port=MemoryConfig.QDRANT_PORT
        )
        
        # Modelo de embeddings
        logger.info(f"Loading embedding model: {MemoryConfig.EMBEDDING_MODEL}")
        self.embedding_model = SentenceTransformer(MemoryConfig.EMBEDDING_MODEL)
        
        # HTTP client
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Cache de embeddings (para queries frequentes)
        self.embedding_cache: Dict[str, np.ndarray] = {}
        
        # Inicializa collections
        # Movido para startup event
        # asyncio.create_task(self._initialize())

        # logger.info("🧠 RAG Memory Core initialized (Waiting for startup)")
        logger.info("🧠 RAG Memory Core initialized (Waiting for startup)")

    async def _initialize(self):
        """Inicialização completa com seed data"""
        await self._initialize_collections()
        await self._load_seed_data()
    
    # ========================================================================
    # INICIALIZAÇÃO
    # ========================================================================
    
    async def _load_seed_data(self):
        """Carrega dados iniciais do arquivo seed_knowledge.json"""
    async def _load_seed_data(self):
        """Carrega dados iniciais do arquivo seed_knowledge.json"""
        # Procura no diretório atual (Docker) ou relativo (Dev)
        seed_file = "seed_knowledge.json"
        if not os.path.exists(seed_file):
            seed_file = os.path.join(os.path.dirname(__file__), "..", "data", "seed_knowledge.json")
        
        if not os.path.exists(seed_file):
            logger.warning(f"Seed data file not found: {seed_file}")
            return

        try:
            with open(seed_file, "r", encoding="utf-8") as f:
                seed_data = json.load(f)
            
            logger.info(f"Loadind {len(seed_data)} seed entries...")
            
            for item in seed_data:
                collection = item["collection"]
                
                # Verifica se já existe (simplificado por hash do conteúdo)
                # Em produção, usaria scroll com filtro, mas aqui vamos assumir que id = hash
                # Verifica se já existe
                # import uuid -> Moved to top
                content_hash = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{item['content']}{item.get('importance', 1)}"))
                
                # Tenta buscar pelo ID (hash) se fosse gerado deterministicamente,
                # mas nosso store_memory usa timestamp.
                # Vamos simplificar: busca exata pelo content
                query = SearchQuery(
                    query=item["content"],
                    collection=collection,
                    limit=1,
                    min_score=0.99
                )
                
                exists = await self.search(query)
                
                if not exists:
                    entry = MemoryEntry(
                        content=item["content"],
                        metadata=item.get("metadata", {}),
                        importance=item.get("importance", 5),
                        timestamp=datetime.now()
                    )
                    await self.store_memory(collection, entry)
                    logger.info(f"Seeded: {item['content'][:30]}...")
                
            logger.info("✅ Seed data loaded successfully")
                
        except Exception as e:
            logger.error(f"Error loading seed data: {e}")

    async def _initialize_collections(self):
        """Cria collections no Qdrant se não existirem"""
        for collection_name, description in MemoryConfig.COLLECTIONS.items():
            try:
                # Verifica se collection existe
                collections = self.qdrant.get_collections()
                existing = [c.name for c in collections.collections]
                
                if collection_name not in existing:
                    logger.info(f"Creating collection: {collection_name}")
                    
                    self.qdrant.create_collection(
                        collection_name=collection_name,
                        vectors_config=VectorParams(
                            size=MemoryConfig.EMBEDDING_DIM,
                            distance=Distance.COSINE
                        )
                    )
                    
                    logger.info(f"✅ Collection created: {collection_name}")
                else:
                    logger.info(f"Collection already exists: {collection_name}")
                
                # Atualiza métrica
                count = self.qdrant.count(collection_name=collection_name)
                MEMORY_SIZE.labels(collection=collection_name).set(count.count)
            
            except Exception as e:
                logger.error(f"Error initializing collection {collection_name}: {e}")
    
    # ========================================================================
    # EMBEDDINGS
    # ========================================================================
    
    def _generate_embedding(self, text: str) -> np.ndarray:
        """Gera embedding para texto"""
        
        # Verifica cache
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self.embedding_cache:
            return self.embedding_cache[cache_key]
        
        with EMBEDDING_LATENCY.time():
            embedding = self.embedding_model.encode(text, convert_to_numpy=True)
        
        # Salva no cache (limitado a 1000 entradas)
        if len(self.embedding_cache) < 1000:
            self.embedding_cache[cache_key] = embedding
        
        return embedding
    
    def _generate_embeddings_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Gera embeddings em batch (mais eficiente)"""
        with EMBEDDING_LATENCY.time():
            embeddings = self.embedding_model.encode(texts, convert_to_numpy=True)
        return embeddings
    
    # ========================================================================
    # ARMAZENAMENTO
    # ========================================================================
    
    async def store_memory(self, 
                          collection: str,
                          entry: MemoryEntry) -> str:
        """Armazena entrada de memória"""
        
        if collection not in MemoryConfig.COLLECTIONS:
            raise ValueError(f"Unknown collection: {collection}")
        
        # Gera embedding
        embedding = self._generate_embedding(entry.content)
        
        # Cria ID único (UUID deterministic)
        # import uuid -> Moved to top
        entry_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{entry.content}{entry.timestamp.isoformat()}"))
        
        # Prepara payload
        payload = {
            "content": entry.content,
            "metadata": entry.metadata,
            "timestamp": entry.timestamp.isoformat(),
            "user_id": entry.user_id,
            "importance": entry.importance
        }
        
        # Armazena no Qdrant
        try:
            self.qdrant.upsert(
                collection_name=collection,
                points=[
                    PointStruct(
                        id=entry_id,
                        vector=embedding.tolist(),
                        payload=payload
                    )
                ]
            )
        except Exception as e:
            logger.error(f"CRITICAL: Qdrant Upsert Failed for ID {entry_id}: {e}")
            # Print type of entry_id
            logger.error(f"ID Type: {type(entry_id)}")
            raise
        
        MEMORY_OPERATIONS.labels(operation="store", collection=collection).inc()
        
        # Atualiza métrica
        count = self.qdrant.count(collection_name=collection)
        MEMORY_SIZE.labels(collection=collection).set(count.count)
        
        logger.info(f"Stored memory in {collection}: {entry_id[:8]}...")
        
        return entry_id
    
    async def store_memories_batch(self,
                                   collection: str,
                                   entries: List[MemoryEntry]) -> List[str]:
        """Armazena múltiplas memórias em batch"""
        
        if not entries:
            return []
        
        # Gera embeddings em batch
        texts = [entry.content for entry in entries]
        embeddings = self._generate_embeddings_batch(texts)
        
        # Prepara pontos
        points = []
        entry_ids = []
        
        for entry, embedding in zip(entries, embeddings):
            # import uuid -> Moved to top
            entry_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{entry.content}{entry.timestamp.isoformat()}"))
            
            payload = {
                "content": entry.content,
                "metadata": entry.metadata,
                "timestamp": entry.timestamp.isoformat(),
                "user_id": entry.user_id,
                "importance": entry.importance
            }
            
            points.append(PointStruct(
                id=entry_id,
                vector=embedding.tolist(),
                payload=payload
            ))
            
            entry_ids.append(entry_id)
        
        # Armazena
        self.qdrant.upsert(collection_name=collection, points=points)
        
        MEMORY_OPERATIONS.labels(operation="store_batch", collection=collection).inc()
        
        logger.info(f"Stored {len(entries)} memories in {collection}")
        
        return entry_ids
    
    # ========================================================================
    # BUSCA E RECUPERAÇÃO
    # ========================================================================
    
    async def search(self, query: SearchQuery) -> List[SearchResult]:
        """Busca semântica em memórias"""
        
        if query.collection not in MemoryConfig.COLLECTIONS:
            raise ValueError(f"Unknown collection: {query.collection}")
        
        # Gera embedding da query
        query_embedding = self._generate_embedding(query.query)
        
        # Prepara filtros
        filter_conditions = None
        if query.filters:
            conditions = []
            
            for key, value in query.filters.items():
                if isinstance(value, dict) and "gte" in value:
                    # Range filter
                    conditions.append(
                        FieldCondition(
                            key=f"metadata.{key}",
                            range=Range(gte=value["gte"], lte=value.get("lte"))
                        )
                    )
                else:
                    # Exact match
                    conditions.append(
                        FieldCondition(
                            key=f"metadata.{key}",
                            match=MatchValue(value=value)
                        )
                    )
            
            if conditions:
                filter_conditions = Filter(must=conditions)
        
        # Busca
        with SEARCH_LATENCY.labels(collection=query.collection).time():
            results = self.qdrant.search(
                collection_name=query.collection,
                query_vector=query_embedding.tolist(),
                limit=query.limit,
                score_threshold=query.min_score,
                query_filter=filter_conditions
            )
        
        MEMORY_OPERATIONS.labels(operation="search", collection=query.collection).inc()
        
        # Formata resultados
        search_results = []
        for result in results:
            search_results.append(SearchResult(
                id=result.id,
                content=result.payload.get("content", ""),
                score=result.score,
                metadata=result.payload.get("metadata", {}),
                timestamp=datetime.fromisoformat(result.payload.get("timestamp", datetime.now().isoformat()))
            ))
        
        logger.info(f"Search in {query.collection}: {len(search_results)} results (score >= {query.min_score})")
        
        return search_results
    
    async def get_recent_memories(self,
                                 collection: str,
                                 limit: int = 10,
                                 hours_back: int = 24) -> List[SearchResult]:
        """Recupera memórias recentes"""
        
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        # Busca com filtro de tempo
        results = self.qdrant.scroll(
            collection_name=collection,
            limit=limit,
            with_payload=True,
            with_vectors=False
        )
        
        memories = []
        for point in results[0]:
            timestamp = datetime.fromisoformat(point.payload.get("timestamp"))
            
            if timestamp >= cutoff_time:
                memories.append(SearchResult(
                    id=point.id,
                    content=point.payload.get("content", ""),
                    score=1.0,
                    metadata=point.payload.get("metadata", {}),
                    timestamp=timestamp
                ))
        
        # Ordena por timestamp (mais recente primeiro)
        memories.sort(key=lambda m: m.timestamp, reverse=True)
        
        return memories[:limit]
    
    # ========================================================================
    # SISTEMA DE DECISÕES
    # ========================================================================
    
    async def store_decision(self, decision: DecisionRecord) -> str:
        """Armazena decisão do sistema"""
        
        # Cria descrição textual da decisão
        content = f"Action: {decision.action}\n"
        content += f"Context: {json.dumps(decision.context, indent=2)}\n"
        content += f"User Approved: {decision.user_approved}\n"
        content += f"Auto Approved: {decision.auto_approved}"
        
        if decision.outcome:
            content += f"\nOutcome: {decision.outcome}"
        
        entry = MemoryEntry(
            content=content,
            metadata={
                "action": decision.action,
                "context": decision.context,
                "user_approved": decision.user_approved,
                "auto_approved": decision.auto_approved,
                "outcome": decision.outcome
            },
            timestamp=decision.timestamp,
            importance=8 if decision.user_approved else 5
        )
        
        decision_id = await self.store_memory("decisions", entry)
        
        logger.info(f"Stored decision: {decision.action} (ID: {decision_id[:8]}...)")
        
        return decision_id
    
    async def find_similar_decisions(self,
                                    action: str,
                                    context: Dict[str, Any],
                                    limit: int = 5) -> List[Tuple[SearchResult, bool]]:
        """
        Busca decisões similares para aprendizado
        Retorna: List[(resultado, foi_aprovada)]
        """
        
        # Monta query
        query_text = f"Action: {action}\nContext: {json.dumps(context)}"
        
        query = SearchQuery(
            query=query_text,
            collection="decisions",
            limit=limit,
            min_score=0.75,
            filters={"action": action}
        )
        
        results = await self.search(query)
        
        # Extrai se foi aprovada
        decisions_with_approval = [
            (result, result.metadata.get("user_approved", False))
            for result in results
        ]
        
        return decisions_with_approval
    
    async def should_auto_approve(self,
                                 action: str,
                                 context: Dict[str, Any],
                                 threshold: float = 0.85) -> Tuple[bool, Optional[str]]:
        """
        Determina se uma ação pode ser auto-aprovada baseado em histórico
        Retorna: (deve_aprovar, razão)
        """
        
        similar = await self.find_similar_decisions(action, context, limit=10)
        
        if not similar:
            return False, "No similar decisions found"
        
        # Conta aprovações
        approved_count = sum(1 for _, approved in similar if approved)
        total = len(similar)
        
        approval_rate = approved_count / total
        
        # Verifica score médio (similaridade)
        avg_score = sum(result.score for result, _ in similar) / total
        
        if approval_rate >= 0.8 and avg_score >= threshold:
            reason = f"Historical approval rate: {approval_rate*100:.0f}% ({approved_count}/{total}) with avg similarity {avg_score:.2f}"
            return True, reason
        
        return False, f"Insufficient historical data: {approval_rate*100:.0f}% approval rate"
    
    async def process_learning_feedback(self, feedback: LearningFeedback):
        """Processa feedback de aprendizado"""
        
        # Atualiza payload da decisão
        try:
            # Busca decisão original
            point = self.qdrant.retrieve(
                collection_name="decisions",
                ids=[feedback.decision_id]
            )
            
            if point:
                # Atualiza metadata
                updated_metadata = point[0].payload.get("metadata", {})
                updated_metadata["feedback"] = {
                    "was_correct": feedback.was_correct,
                    "user_feedback": feedback.user_feedback,
                    "corrections": feedback.corrections,
                    "feedback_timestamp": datetime.now().isoformat()
                }
                
                # Atualiza importância baseado em feedback
                importance = 9 if feedback.was_correct else 10
                
                # Re-armazena
                self.qdrant.set_payload(
                    collection_name="decisions",
                    payload={
                        "metadata": updated_metadata,
                        "importance": importance
                    },
                    points=[feedback.decision_id]
                )
                
                logger.info(f"Updated decision {feedback.decision_id[:8]} with feedback")
        
        except Exception as e:
            logger.error(f"Error processing feedback: {e}")
    
    # ========================================================================
    # SUMARIZAÇÃO E CONTEXTO
    # ========================================================================
    
    async def get_conversation_context(self,
                                      user_id: str,
                                      max_messages: int = 10) -> str:
        """
        Recupera contexto de conversação para LLM
        Retorna resumo das últimas interações
        """
        
        # Busca últimas conversas
        recent = await self.get_recent_memories(
            collection="conversations",
            limit=max_messages,
            hours_back=24
        )
        
        # Filtra por user_id
        user_messages = [m for m in recent if m.metadata.get("user_id") == user_id]
        
        if not user_messages:
            return "No recent conversation history."
        
        # Monta contexto
        context_lines = ["Recent conversation context:"]
        
        for msg in reversed(user_messages):  # Ordem cronológica
            role = msg.metadata.get("role", "unknown")
            content = msg.content[:200]  # Limita tamanho
            
            context_lines.append(f"[{role}]: {content}")
        
        return "\n".join(context_lines)
    
    async def store_conversation_turn(self,
                                     user_id: str,
                                     user_message: str,
                                     assistant_message: str):
        """Armazena turno de conversação"""
        
        entries = [
            MemoryEntry(
                content=user_message,
                metadata={"role": "user", "user_id": user_id},
                user_id=user_id,
                importance=3
            ),
            MemoryEntry(
                content=assistant_message,
                metadata={"role": "assistant", "user_id": user_id},
                user_id=user_id,
                importance=3
            )
        ]
        
        await self.store_memories_batch("conversations", entries)
    
    # ========================================================================
    # LIMPEZA E MANUTENÇÃO
    # ========================================================================
    
    async def cleanup_old_memories(self):
        """Remove memórias antigas baseado em política de retenção"""
        
        retention_policies = {
            "conversations": MemoryConfig.CONVERSATION_RETENTION_DAYS,
            "decisions": MemoryConfig.DECISION_RETENTION_DAYS
        }
        
        for collection, retention_days in retention_policies.items():
            cutoff = datetime.now() - timedelta(days=retention_days)
            
            try:
                # Qdrant não tem delete by timestamp nativo, então fazemos scroll + delete
                results = self.qdrant.scroll(
                    collection_name=collection,
                    limit=1000,
                    with_payload=True
                )
                
                to_delete = []
                for point in results[0]:
                    timestamp = datetime.fromisoformat(point.payload.get("timestamp"))
                    if timestamp < cutoff:
                        to_delete.append(point.id)
                
                if to_delete:
                    self.qdrant.delete(
                        collection_name=collection,
                        points_selector=to_delete
                    )
                    
                    logger.info(f"Cleaned up {len(to_delete)} old memories from {collection}")
            
            except Exception as e:
                logger.error(f"Error cleaning up {collection}: {e}")
    
    async def get_memory_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de memória"""
        
        stats = {}
        
        for collection in MemoryConfig.COLLECTIONS.keys():
            count = self.qdrant.count(collection_name=collection)
            stats[collection] = {
                "count": count.count,
                "description": MemoryConfig.COLLECTIONS[collection]
            }
        
        return stats

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Prometheus RAG Memory API",
    description="Sistema de Memória Vetorial e Aprendizado",
    version="2.0.0"
)

memory = RAGMemoryCore()

# Security
api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != MemoryConfig.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.on_event("startup")
async def startup():
    """Inicializa serviço"""
    start_http_server(9092)
    
    # Inicializa memória (Qdrant + Seed)
    await memory._initialize()
    
    # Agenda limpeza periódica
    async def cleanup_task():
        while True:
            await asyncio.sleep(86400)  # 24 horas
            await memory.cleanup_old_memories()
    
    asyncio.create_task(cleanup_task())
    
    logger.info("🧠 RAG Memory Service started")

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "rag_memory"}

@app.post("/memory/store")
async def store_memory(
    collection: str,
    entry: MemoryEntry,
    _: str = Depends(verify_api_key)
):
    """Armazena entrada de memória"""
    entry_id = await memory.store_memory(collection, entry)
    return {"id": entry_id, "collection": collection}

@app.post("/memory/search", response_model=List[SearchResult])
async def search_memory(
    query: SearchQuery,
    _: str = Depends(verify_api_key)
):
    """Busca em memórias"""
    return await memory.search(query)

@app.get("/memory/recent/{collection}")
async def get_recent(
    collection: str,
    limit: int = 10,
    hours_back: int = 24,
    _: str = Depends(verify_api_key)
):
    """Recupera memórias recentes"""
    results = await memory.get_recent_memories(collection, limit, hours_back)
    return {"memories": [r.dict() for r in results]}

@app.post("/decisions/store")
async def store_decision(
    decision: DecisionRecord,
    _: str = Depends(verify_api_key)
):
    """Armazena decisão"""
    decision_id = await memory.store_decision(decision)
    return {"decision_id": decision_id}

@app.post("/decisions/should-approve")
async def should_approve(
    action: str,
    context: Dict[str, Any],
    _: str = Depends(verify_api_key)
):
    """Verifica se ação deve ser auto-aprovada"""
    should_approve, reason = await memory.should_auto_approve(action, context)
    
    similar = await memory.find_similar_decisions(action, context)
    
    return {
        "should_approve": should_approve,
        "reason": reason,
        "similar_decisions": len(similar),
        "examples": [
            {
                "content": r.content[:200],
                "score": r.score,
                "approved": approved
            }
            for r, approved in similar[:3]
        ]
    }

@app.post("/decisions/feedback")
async def decision_feedback(
    feedback: LearningFeedback,
    _: str = Depends(verify_api_key)
):
    """Processa feedback de decisão"""
    await memory.process_learning_feedback(feedback)
    return {"status": "processed"}

@app.get("/context/conversation/{user_id}")
async def get_context(
    user_id: str,
    max_messages: int = 10,
    _: str = Depends(verify_api_key)
):
    """Recupera contexto de conversação"""
    context = await memory.get_conversation_context(user_id, max_messages)
    return {"context": context}

@app.post("/context/store-turn")
async def store_turn(
    user_id: str,
    user_message: str,
    assistant_message: str,
    _: str = Depends(verify_api_key)
):
    """Armazena turno de conversação"""
    await memory.store_conversation_turn(user_id, user_message, assistant_message)
    return {"status": "stored"}

@app.get("/stats")
async def get_stats(_: str = Depends(verify_api_key)):
    """Estatísticas de memória"""
    return await memory.get_memory_stats()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9001, log_level="info")
