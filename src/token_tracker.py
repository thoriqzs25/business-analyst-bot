from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, func

from src.config import settings
from src.models.base import Base
from src.models.token_usage import TokenUsage

_engine = None
_session_factory = None


async def init_db():
    global _engine, _session_factory
    _engine = create_async_engine(settings.postgres_dsn)
    _session_factory = async_sessionmaker(_engine, class_=AsyncSession)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None


def get_session() -> AsyncSession:
    return _session_factory()


async def log_token_usage(
    user_id: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost: float = 0.0,
):
    async with get_session() as session:
        record = TokenUsage(
            user_id=user_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost=cost,
        )
        session.add(record)
        await session.commit()


async def get_user_token_usage(user_id: str) -> dict:
    async with get_session() as session:
        result = await session.execute(
            select(
                func.sum(TokenUsage.total_tokens).label("total"),
                func.sum(TokenUsage.cost).label("cost"),
                func.count(TokenUsage.id).label("calls"),
            ).where(TokenUsage.user_id == user_id)
        )
        row = result.one()
        return {
            "total_tokens": row.total or 0,
            "total_cost": float(row.cost or 0),
            "total_calls": row.calls or 0,
        }
