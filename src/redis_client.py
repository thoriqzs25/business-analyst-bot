import json
import asyncio
from typing import Callable, Coroutine, Any

from redis.asyncio import Redis

from src.config import settings

redis: Redis | None = None
_subscriptions: dict[str, list[Callable]] = {}


async def init_redis() -> Redis:
    global redis
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return redis


async def close_redis():
    global redis
    if redis:
        await redis.close()
        redis = None


async def publish(channel: str, data: dict):
    if redis:
        await redis.publish(channel, json.dumps(data))


def subscribe(channel: str, handler: Callable[[dict], Coroutine[Any, Any, None]]):
    if channel not in _subscriptions:
        _subscriptions[channel] = []
    _subscriptions[channel].append(handler)


async def listen():
    if not redis:
        return

    channels = list(_subscriptions.keys())
    if not channels:
        return

    pubsub = redis.pubsub()
    await pubsub.subscribe(*channels)

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None:
                continue

            channel = message["channel"]
            data = json.loads(message["data"])

            handlers = _subscriptions.get(channel, [])
            for handler in handlers:
                asyncio.create_task(handler(data))

            await asyncio.sleep(0.01)
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe()
        await pubsub.close()
