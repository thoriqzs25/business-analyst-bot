import logging
import asyncio

from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.config import settings
from src.redis_client import init_redis, close_redis, listen, publish
from src.router import handle_incoming_message
from src.admin.routes import router as admin_router
from src.token_tracker import init_db

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")
    await init_redis()
    try:
        await init_db()
    except Exception as e:
        logger.warning("Database init failed (will retry): %s", e)

    from src.redis_client import subscribe
    subscribe("wa:incoming", handle_incoming_message)

    task = asyncio.create_task(listen())

    yield

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await close_redis()
    logger.info("Shutdown complete.")


app = FastAPI(title="Business Analyst Bot", lifespan=lifespan)
app.include_router(admin_router)


@app.get("/")
async def root():
    return {"status": "ok", "bot": "business-analyst-bot"}
