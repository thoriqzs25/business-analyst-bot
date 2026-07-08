import logging

logger = logging.getLogger(__name__)


async def process_command(sender: str, group_id: str, body: str):
    logger.info("Coding agent: %s from %s", body[:60], sender)
