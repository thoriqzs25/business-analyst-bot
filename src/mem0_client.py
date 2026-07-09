import asyncio
from mem0 import Memory
from mem0.configs.base import MemoryConfig
from mem0.vector_stores.configs import VectorStoreConfig
from mem0.llms.configs import LlmConfig
from mem0.embeddings.configs import EmbedderConfig

from src.config import settings

_memory: Memory | None = None


def get_memory() -> Memory | None:
    global _memory
    if _memory is None:
        try:
            _memory = Memory(
                config=MemoryConfig(
                    vector_store=VectorStoreConfig(
                        provider="qdrant",
                        config={
                            "host": settings.qdrant_host,
                            "port": settings.qdrant_port,
                            "collection_name": settings.mem0_qdrant_collection,
                            "embedding_model_dims": 384,
                        },
                    ),
                    llm=LlmConfig(
                        provider="openai",
                        config={
                            "model": settings.llm_model,
                            "openai_base_url": settings.opencode_go_base_url,
                            "api_key": settings.opencode_go_api_key,
                        },
                    ),
                    embedder=EmbedderConfig(
                        provider="huggingface",
                        config={
                            "model": "sentence-transformers/all-MiniLM-L6-v2",
                        },
                    ),
                )
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Mem0 init failed (memory disabled): %s", e)
            return None
    return _memory


async def add_memory(user_id: str, messages: list[dict]):
    await asyncio.to_thread(add_memory_sync, user_id, messages)


def add_memory_sync(user_id: str, messages: list[dict]):
    mem = get_memory()
    if mem is None:
        return
    try:
        mem.add(messages, user_id=user_id)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Mem0 add failed: %s", e)


def search_memory(user_id: str, query: str, top_k: int = 5) -> list[dict]:
    mem = get_memory()
    if mem is None:
        return []
    try:
        result = mem.search(query=query, filters={"user_id": user_id}, top_k=top_k)
        return result.get("results", [])
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Mem0 search failed: %s", e)
        return []
