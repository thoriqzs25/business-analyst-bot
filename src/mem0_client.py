from mem0 import Memory

from src.config import settings

_memory: Memory | None = None


def get_memory() -> Memory:
    global _memory
    if _memory is None:
        _memory = Memory(
            config={
                "vector_store": {
                    "provider": "qdrant",
                    "config": {
                        "host": settings.qdrant_host,
                        "port": settings.qdrant_port,
                        "collection_name": settings.mem0_qdrant_collection,
                    },
                },
                "llm": {
                    "provider": "openai",
                    "config": {
                        "model": settings.llm_model,
                        "openai_base_url": settings.opencode_go_base_url,
                        "openai_api_key": settings.opencode_go_api_key,
                    },
                },
            }
        )
    return _memory


async def add_memory(user_id: str, messages: list[dict]):
    mem = get_memory()
    mem.add(messages, user_id=user_id)


def search_memory(user_id: str, query: str, top_k: int = 5) -> list[dict]:
    mem = get_memory()
    result = mem.search(query=query, filters={"user_id": user_id}, top_k=top_k)
    return result.get("results", [])
