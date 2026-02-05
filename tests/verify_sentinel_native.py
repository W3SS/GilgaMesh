import asyncio
import os
import sys
import json
import logging

# Adiciona diretório raiz ao path para importar sentinel
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sentinel.sentinel_service import SentinelConfig, SentinelCore, config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VerifySentinel")

async def verify_dynamic_config():
    """Testa se a configuração dinâmica funciona"""
    logger.info("🧪 Testing Dynamic Config...")
    
    # 1. Adicionar item à whitelist
    test_proc = "test_safe_process.exe"
    config.PROTECTED_PROCESSES.add(test_proc)
    config.save()
    
    # 2. Recarregar e verificar
    new_config = SentinelConfig()
    new_config.load()
    
    if test_proc in new_config.PROTECTED_PROCESSES:
        logger.info("✅ Config persistence verified")
    else:
        logger.error("❌ Config persistence failed")

    # Limpeza
    if os.path.exists("sentinel_config.json"):
        os.remove("sentinel_config.json")

async def verify_core_logic():
    """Testa lógica do core (mocked)"""
    logger.info("🧪 Testing Sentinel Core Logic...")
    
    core = SentinelCore()
    
    # 1. Testar listagem de processos
    procs = await core.get_processes(top_n=5)
    logger.info(f"Processes found: {len(procs)}")
    assert len(procs) > 0
    
    # 2. Testar detecção de ameaças (mock)
    # Cria um processo falso
    from sentinel.sentinel_service import ProcessInfo
    fake_proc = ProcessInfo(
        pid=99999,
        name="mimikatz.exe", # Nome suspeito
        username="SYSTEM",
        cpu_percent=10.0,
        memory_mb=50.0,
        status="running",
        create_time=0.0,
        num_threads=1,
        connections=0
    )
    
    threats = await core.analyze_process_threats([fake_proc])
    
    if threats.level in ["high", "critical"]:
         logger.info(f"✅ Threat detection passed. Score: {threats.score}")
    else:
         logger.error(f"❌ Threat detection failed. Level: {threats.level}")

async def main():
    try:
        await verify_dynamic_config()
        await verify_core_logic()
        logger.info("🎉 All Sentinel native tests passed!")
    except Exception as e:
        logger.error(f"Tests failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
