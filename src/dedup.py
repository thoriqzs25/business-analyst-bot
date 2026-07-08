import time

_seen: dict[str, float] = {}
DEDUP_TTL = 5.0


def is_duplicate(msg_id: str) -> bool:
    now = time.time()
    if msg_id in _seen:
        if now - _seen[msg_id] < DEDUP_TTL:
            return True
    _seen[msg_id] = now
    return False


def cleanup():
    global _seen
    now = time.time()
    _seen = {k: v for k, v in _seen.items() if now - v < DEDUP_TTL}
