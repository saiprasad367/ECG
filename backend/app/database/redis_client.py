import logging

logger = logging.getLogger(__name__)

redis_client = None

async def connect_redis():
    logger.info("⚡ In-Memory DB Mode: Redis disabled (container-free)")

async def close_redis():
    pass

def get_redis():
    return None
