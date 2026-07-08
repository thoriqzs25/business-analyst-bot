import logging

from src.config import settings
from src.dedup import is_duplicate

logger = logging.getLogger(__name__)


async def handle_incoming_message(data: dict):
    msg_id = data.get("msg_id", "")
    if is_duplicate(msg_id):
        logger.debug("Deduplicated message %s", msg_id)
        return

    sender = data.get("from", "")
    body = data.get("body", "").strip()
    group_id = data.get("group_id")

    if not body or not sender:
        return

    if group_id:
        if group_id == settings.skills_group_jid:
            await handle_skills_group(sender, group_id, body, data)
        elif group_id == settings.code_group_jid:
            await handle_code_group(sender, group_id, body, data)
        else:
            logger.info("Unknown group %s, ignoring", group_id)
        return

    await handle_individual_chat(sender, body, data)


async def handle_individual_chat(sender: str, body: str, data: dict):
    logger.info("Individual chat from %s: %s", sender, body[:50])
    from src.agents.business_analyst import process_message
    await process_message(sender, body)


async def handle_skills_group(sender: str, group_id: str, body: str, data: dict):
    logger.info("Skills group command from %s: %s", sender, body[:50])
    from src.agents.skills_manager import process_command
    await process_command(sender, group_id, body)


async def handle_code_group(sender: str, group_id: str, body: str, data: dict):
    logger.info("Code group command from %s: %s", sender, body[:50])
    from src.agents.coding_agent import process_command
    await process_command(sender, group_id, body)
