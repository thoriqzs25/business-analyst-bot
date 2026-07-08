import logging

logger = logging.getLogger(__name__)


async def process_message(user_id: str, message: str):
    logger.info("BA agent: processing message from %s", user_id)
