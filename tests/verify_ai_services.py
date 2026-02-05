import asyncio
import httpx
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("VerifyAIServices")

ORCHESTRATOR_URL = "http://localhost:8005"

async def verify_orchestrator_health():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{ORCHESTRATOR_URL}/status")
            if response.status_code == 200:
                logger.info("✅ Orchestrator is healthy")
                return True
            else:
                logger.error(f"❌ Orchestrator returned {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Could not connect to Orchestrator: {e}")
            return False

async def submit_test_task(task_type: str, prompt: str):
    async with httpx.AsyncClient() as client:
        payload = {
            "type": task_type,
            "prompt": prompt,
            "priority": 2, # Medium
            "parameters": {
                "steps": 10, # Low steps for speed
                "width": 512,
                "height": 512
            }
        }
        try:
            response = await client.post(f"{ORCHESTRATOR_URL}/tasks", json=payload)
            if response.status_code == 200:
                task_id = response.json()["task_id"]
                logger.info(f"✅ Task submitted: {task_id} ({task_type})")
                return task_id
            else:
                logger.error(f"❌ Failed to submit task: {response.text}")
                return None
        except Exception as e:
            logger.error(f"❌ Error submitting task: {e}")
            return None

async def wait_for_task(task_id: str, timeout: int = 60):
    async with httpx.AsyncClient() as client:
        for _ in range(timeout):
            response = await client.get(f"{ORCHESTRATOR_URL}/tasks/{task_id}")
            if response.status_code == 200:
                status = response.json()
                logger.info(f"Task {task_id} status: {status['status']}")
                
                if status['status'] == 'completed':
                    logger.info(f"✅ Task completed successfully: {status.get('result')}")
                    return True
                elif status['status'] == 'failed':
                    logger.error(f"❌ Task failed: {status.get('error')}")
                    return False
            
            await asyncio.sleep(2)
            
    logger.error(f"❌ Task verification timed out after {timeout}s")
    return False

async def main():
    logger.info("🔵 Starting AI Services Verification")
    
    # 1. Check Orchestrator
    if not await verify_orchestrator_health():
        sys.exit(1)
        
    # 2. Test Text Gen (Ollama)
    # logger.info("\n🧪 Testing Text Generation (Ollama)...")
    # task_id_text = await submit_test_task("text_generation", "Hello, are you working?")
    # if task_id_text:
    #     await wait_for_task(task_id_text)
    
    # Note: We are testing Image Gen mainly as it uses the new template logic
    logger.info("\n🧪 Testing Image Generation (ComfyUI)...")
    task_id_img = await submit_test_task("image", "A futuristic city with neon lights")
    if task_id_img:
        success = await wait_for_task(task_id_img, timeout=120)
        if not success:
            logger.warning("⚠️ Image generation failed or timed out. Check if ComfyUI is running and has models.")
        else:
            logger.info("✅ Image generation verified.")

if __name__ == "__main__":
    asyncio.run(main())
