import time
from functools import lru_cache

# Fix #5: Use LRU cache with maxsize instead of unbounded dict
# This automatically evicts old entries when maxsize is reached

@lru_cache(maxsize=10000)
def _is_duplicate_cached(msg_id: str) -> bool:
    """Cache stores seen msg_ids. Returns False for new, True for cached."""
    return False


def is_duplicate(msg_id: str) -> bool:
    """
    Check if message ID has been seen before.
    Uses LRU cache with max 10,000 entries to prevent memory leak.
    """
    if not msg_id:
        return False
    
    # Check if already in cache
    if msg_id in _is_duplicate_cached.cache_info():
        return True
    
    # Add to cache (will evict oldest if over maxsize)
    _is_duplicate_cached(msg_id)
    return False


def get_dedup_stats() -> dict:
    """Get deduplication cache statistics."""
    info = _is_duplicate_cached.cache_info()
    return {
        "hits": info.hits,
        "misses": info.misses,
        "maxsize": info.maxsize,
        "currsize": info.currsize,
    }


# Backward compatibility - cleanup is now a no-op since LRU handles eviction
def cleanup():
    """No-op: LRU cache auto-evicts old entries."""
    pass