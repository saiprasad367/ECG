import logging

logger = logging.getLogger(__name__)

client = None
db = None

async def connect_db():
    logger.info("⚡ In-Memory DB Mode: MongoDB disabled (container-free)")

async def close_db():
    pass

def get_db():
    return None
