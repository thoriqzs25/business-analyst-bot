# Resource Analysis: RPi5 Deployment

**Date:** 2026-07-09  
**Target Hardware:** Raspberry Pi 5 (8GB RAM, ~3.6GB available for user processes)

---

## Service Breakdown

| Service | Image | Est. RAM (Idle) | Est. RAM (Active) | Notes |
|---------|-------|-----------------|-------------------|-------|
| **Redis** | redis:7-alpine | 15 MB | 30 MB | Lightweight pub/sub, minimal data |
| **Postgres** | postgres:16-alpine | 50 MB | 100 MB | Small dataset, asyncpg connection pool |
| **Qdrant** | qdrant/qdrant:latest | 200 MB | 600 MB | **Heaviest service** - vector DB with HNSW indexing |
| **Python App** | custom (Dockerfile.python) | 200 MB | 500 MB | HuggingFace model + LangGraph + FastAPI |
| **Node Bridge** | custom (Dockerfile.node) | 80 MB | 200 MB | Baileys WhatsApp bridge |
| **OS + Docker** | - | ~500 MB | ~500 MB | Base system overhead |

---

## Total Resource Estimate

```
Minimum (idle):     ~1.0 GB
Normal usage:       ~1.8 - 2.2 GB
Peak/heavy load:    ~2.8 - 3.2 GB
Safety margin:      ~0.4 GB
─────────────────────────────────
RPi5 Available:     ~3.6 GB
Status:             ✅ FEASIBLE but tight margin
```

---

## Key Risks

### 1. HuggingFace Model Download (First Run)
- **Model:** `all-MiniLM-L6-v2` (Mem0 default)
- **Download size:** ~80 MB
- **RAM usage:** ~100 MB during embedding inference
- **Risk:** Slow download on arm64, potential timeout/OOM
- **Mitigation:** Pre-download during Docker build

### 2. Qdrant Memory Scaling
- Vector storage grows with user count
- HNSW indexing consumes additional RAM
- **Risk:** Unbounded growth if not configured
- **Mitigation:** Set memory map threshold, limit collection size

### 3. Concurrent User Load
- Per active user: ~50 MB Python heap (LLM context)
- 10 concurrent users: +500 MB
- **Risk:** OOM under heavy concurrent load
- **Mitigation:** Implement connection pooling limits

### 4. No Memory Limits (Current Config)
- Single service leak can consume all RAM
- **Risk:** System-wide OOM kills
- **Mitigation:** Add Docker memory limits per service

---

## Recommended Docker Compose Modifications

```yaml
services:
  redis:
    mem_limit: 128m
    command: redis-server --maxmemory 64mb --maxmemory-policy allkeys-lru

  postgres:
    mem_limit: 256m
    command: >
      postgres 
      -c shared_buffers=64MB
      -c effective_cache_size=128MB
      -c work_mem=4MB

  qdrant:
    mem_limit: 512m
    environment:
      - QDRANT__STORAGE__MEMORY_MAP_THRESHOLD=50000000
      - QDRANT__STORAGE__WAL_CAPACITY_MB=32

  python-app:
    mem_limit: 768m
    deploy:
      resources:
        limits:
          memory: 768M

  node-bridge:
    mem_limit: 256m
```

---

## Deployment Scenarios

| Scenario | Users | Status | Recommendation |
|----------|-------|--------|----------------|
| Development | 1-2 | ✅ Safe | Standard config works |
| Small production | 5-10 | ⚠️ Monitor | Add memory limits, enable swap |
| Medium production | 20+ | ❌ Not recommended | Upgrade to x86 server or optimize |

---

## Monitoring Commands

```bash
# Real-time RAM usage per container
docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# System-wide memory
cat /proc/meminfo | grep -E "MemTotal|MemAvailable"

# OOM events
dmesg | grep -i "out of memory"
```

---

## Related Files

- `docker-compose.yml` - Service orchestration
- `src/mem0_client.py` - HuggingFace model configuration
- `AUDIT.md` - Critical issues affecting resource usage
