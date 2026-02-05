import asyncio
import httpx
import json
import logging
from datetime import datetime

# Configuração
MEMORY_URL = "http://localhost:9001"
API_KEY = "prometheus-memory-key-change-me"
HEADERS = {"X-API-Key": API_KEY}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VerifyPhase2")

async def verify_memory_feedback_loop():
    """Verifica o ciclo de decisão -> feedback -> aprendizado"""
    logger.info("🔵 Starting Verification: Memory Feedback Loop")
    
    async with httpx.AsyncClient() as client:
        # 1. Armazenar uma Decisão de Teste
        decision_payload = {
            "action": "test_action_verify",
            "context": {"test_id": "phase2_verify", "metric": 0.5},
            "user_approved": False,
            "auto_approved": False,
            "outcome": "Pending verification"
        }
        
        logger.info("1. Storing test decision...")
        response = await client.post(
            f"{MEMORY_URL}/decisions/store",
            json=decision_payload,
            headers=HEADERS
        )
        assert response.status_code == 200
        decision_id = response.json()["decision_id"]
        logger.info(f"✅ Decision stored. ID: {decision_id}")
        
        # 2. Enviar Feedback Positivo (o usuário aprovou depois, ou disse que a IA estava certa em reprovar?)
        # Vamos assumir que o sistema reprovou (user_approved=False) e estava CORRETO (was_correct=True)
        # Ou seja, "foi bom não ter feito nada".
        
        feedback_payload = {
            "decision_id": decision_id,
            "was_correct": True,
            "user_feedback": "Correct decision to wait.",
            "corrections": {"recommended_action": "wait"}
        }
        
        logger.info("2. Sending positive feedback...")
        response = await client.post(
            f"{MEMORY_URL}/decisions/feedback",
            json=feedback_payload,
            headers=HEADERS
        )
        assert response.status_code == 200
        logger.info("✅ Feedback processed")
        
        # 3. Verificar se a decisão foi atualizada
        # Infelizmente a API atual de "search" não retorna o ID direto facilmente sem busca semântica,
        # mas podemos buscar pelo ID se a API suportasse retrieve por ID.
        # RAGMemoryCore tem `qdrant.retrieve`, mas a API exposta é `search`.
        # Vamos usar um search bem específico.
        
        logger.info("3. Verifying update...")
        await asyncio.sleep(1) # Espera indexar
        
        search_payload = {
            "query": "Action: test_action_verify",
            "collection": "decisions",
            "limit": 1,
            "filters": {"action": "test_action_verify"}
        }
        
        response = await client.post(
            f"{MEMORY_URL}/memory/search",
            json=search_payload,
            headers=HEADERS
        )
        results = response.json()
        
        if not results:
            logger.error("❌ Could not retrieve stored decision")
            return
            
        stored_metadata = results[0]["metadata"]
        
        if "feedback" in stored_metadata and stored_metadata["feedback"]["was_correct"] is True:
            logger.info("✅ Verification SUCCESS: Feedback persisted in metadata.")
            logger.info(f"Feedback data: {stored_metadata['feedback']}")
        else:
            logger.error(f"❌ Verification FAILED: Feedback not found in metadata. Got: {stored_metadata}")

async def main():
    try:
        await verify_memory_feedback_loop()
    except Exception as e:
        logger.error(f"Test Execution Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
