# Codebase Audit: Business Analyst Bot

Date: 2026-07-08
Scope: All source files, configs, tests, and infrastructure

---

## Critical

### 1. `decide_next` always returns `"selesai"` — state machine broken
**File:** `src/intake/graph.py:185`
**Issue:** The conditional edge defines `"lanjut"` and `"selesai"` branches, but the routing function **always** returns `"selesai"`. The `"lanjut"` branch is unreachable. The LangGraph processes exactly one message and terminates — it never loops for multi-turn conversation.
**Impact:** The entire intake state machine design is non-functional. Multi-turn profile collection relies on external Redis stitching, not the graph's intended self-loop.

### 2. `updated_at` never actually updates
**File:** `src/models/business_profile.py:22`
```python
updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```
**Issue:** `onupdate=datetime.utcnow` evaluates `datetime.utcnow` **at class definition time**, not at row update time. The `onupdate` parameter expects a callable, but `datetime.utcnow()` is called immediately and its result is stored permanently.
**Fix:** Pass the function reference without calling it: `onupdate=lambda: datetime.now(datetime.UTC)`

### 3. Real API key exposed on disk
**File:** `.env:2`
**Issue:** A live OpenCode Go API key is stored in `.env` on disk. Anyone with filesystem access can use it to make LLM calls at the owner's expense.

### 4. Dedup memory leak
**File:** `src/dedup.py:3-13`
**Issue:** `_seen` dict stores every `msg_id` ever seen. The `cleanup()` function is defined at line 16 but **never called anywhere**. Over hours/days of operation, the dict grows to millions of entries until OOM.
**Impact:** Production server will eventually run out of memory and be killed.

### 5. No timeout on OpenAI HTTP client
**File:** `src/llm.py:5-7`
**Issue:** The `AsyncOpenAI` client is created with no `timeout` parameter. A network partition or slow upstream can block `chat()` and `chat_with_messages()` indefinitely, holding the event loop and preventing other requests from being processed. With concurrent users this becomes a denial-of-service vector.

### 6. Sync `search_memory()` called from async context — blocks event loop
**File:** `src/intake/graph.py:76`
```python
relevant = search_memory(user_id, conversation[-1]["content"] if conversation else "")
```
**Issue:** `search_memory` performs HuggingFace inference (vector embedding) and Qdrant search synchronously, blocking the event loop for 100ms-2s per call. Meanwhile `add_memory` correctly uses `asyncio.to_thread`. Inconsistency means every memory search stalls all concurrent users.

---

## High

### 7. Admin dashboard has no authentication
**Files:** `src/admin/routes.py` (entire file), `src/config.py:34-35`
**Issue:** `ADMIN_USERNAME` and `ADMIN_PASSWORD` are configured but never used. No auth middleware, no basic auth check. Anyone who reaches the port can access the admin interface.

### 8. `close_db()` never called — connection pool leaks on shutdown
**Files:** `src/token_tracker.py:23-27`, `src/main.py:34-42`
**Issue:** `close_db()` is defined but never invoked during the shutdown lifespan. The async engine's connection pool is not disposed cleanly. On repeated restarts (Docker `restart: unless-stopped`), PostgreSQL connection slots accumulate until exhausted.

### 9. `get_memory()` race condition
**File:** `src/mem0_client.py:13-48`
**Issue:** Check-then-create pattern with no locking. Two concurrent async tasks can both pass the `None` check and create two `Memory` instances, including duplicate HuggingFace model downloads.

### 10. No retry for LLM calls
**File:** `src/llm.py:11-44`
**Issue:** Neither `chat()` nor `chat_with_messages()` implements retry logic for transient failures (rate limits, 429, 503, network timeouts). A single transient failure kills the entire user interaction with "Maaf, ada gangguan sistem".

### 11. LLM response parsing is brittle
**File:** `src/intake/graph.py:137-160`
**Issue:** Profile updates are parsed by splitting on `---BEGIN PROFILE UPDATE---`. Vulnerabilities:
- If the LLM generates the marker in visible text, it leaks to the user
- If the LLM puts the marker before the conversational text, bot sends an empty message
- Malformed JSON (trailing comma, unescaped quotes) silently discards the profile update

### 12. `listen()` task dies permanently on any unhandled error
**File:** `src/main.py:32`
**Issue:** `asyncio.create_task(listen())` creates a fire-and-forget task. If `listen()` encounters an unhandled exception (Redis disconnection, invalid JSON), the task terminates silently and all pub/sub message processing stops permanently.

### 13. `IndexError` if LLM returns empty choices
**File:** `src/llm.py:25`
```python
text = response.choices[0].message.content or ""
```
**Issue:** If the API returns `choices` as an empty list (API errors, overload, content filter rejections), `response.choices[0]` raises `IndexError` that propagates unhandled through the call chain.

### 14. `datetime.utcnow` deprecated
**Files:** `src/models/token_usage.py:17`, `src/models/business_profile.py:21-22`
**Issue:** `datetime.utcnow()` is deprecated in Python 3.12+. The project requires `>=3.11`, so it works now, but on Python 3.12+ it emits deprecation warnings and may be removed.

### 15. Recursive `startBot()` without cleanup — duplicate listeners
**File:** `whatsapp-bridge/index.js:54`
**Issue:** On reconnection, `startBot()` creates new socket, subscriber, and event listeners without cleaning up the old ones. After a few disconnects, multiple listeners process every message, causing duplicate sends.

---

## Medium

### 16. `create_all` conflicts with Alembic
**File:** `src/token_tracker.py:20`
**Issue:** Running `create_all` at startup alongside Alembic migrations means schema changes managed by Alembic can be overwritten. In production, DDL queries may conflict with Alembic's version tracking.

### 17. Dead dependencies: `httpx` and `aiofiles`
**File:** `pyproject.toml:21,23` / `requirements.txt:15,17`
**Issue:** Listed as dependencies but never imported or used anywhere. Bloat the Docker image.

### 18. Hardcoded `embedding_model_dims: 384`
**File:** `src/mem0_client.py:25`
**Issue:** Tied to `all-MiniLM-L6-v2`. If the model changes (e.g., `all-mpnet-base-v2` with 768 dims), Qdrant silently rejects all vectors with wrong dimensionality.

### 19. LangSmith configured but never initialized
**Files:** `.env:30-32`, `pyproject.toml:11`
**Issue:** `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` are set and `langsmith>=0.3.0` is a dependency, but the SDK is never initialized. Dead configuration.

### 20. No message body validation
**File:** `src/router.py:16`
**Issue:** Message `body` is stripped but not validated. Empty string (after strip) is silently ignored. 100MB message or malicious Unicode passes through to LangGraph and Mem0 without size limits or sanitization.

### 21. Default DB password `changeme` in 3 config files
**Files:** `alembic.ini:3`, `docker-compose.yml:49`, `.env.template:21`
**Issue:** If changed in `.env`, must be changed in all other files. No centralized secret management.

### 22. No connection health checks
**Files:** `src/redis_client.py`, `src/token_tracker.py`
**Issue:** After initial connection, neither Redis nor PostgreSQL connections are health-checked. If Redis restarts, the `pubsub` object may not recover. If PostgreSQL restarts, the async engine fails on the next query with no recovery logic.

### 23. Default connection pool size (5) may be insufficient
**File:** `src/token_tracker.py:17`
**Issue:** `create_async_engine(settings.postgres_dsn)` uses default pool size (5) and overflow (10). With 20+ concurrent users and multiple sessions per message, the pool may be exhausted under load.

### 24. `test_simulate.py` is not a real test
**File:** `test_simulate.py` (entire file)
**Issue:** Zero assertions. It's a manual integration smoke test, not a proper test. Uses `sys.path.insert` hack instead of proper package install.

### 25. `media/handler.py` planned but missing
**File:** (does not exist)
**Issue:** Referenced in PLAN.md project structure but never created.

---

## Low

| # | File | Lines | Issue |
|---|------|-------|-------|
| 26 | `src/main.py` | 13-16 | `logging.basicConfig` at module level adds duplicate handlers on reload |
| 27 | `src/mem0_client.py` | 51-52 | `asyncio.to_thread` + unsynchronized global access — data race |
| 28 | Multiple | various | Global mutable state throughout (hard to test, breaks multi-worker) |
| 29 | `src/intake/graph.py` | 58-62 | `"lanjut"` branch is dead code |
| 30 | `src/dedup.py` | 16-19 | `cleanup()` defined but never invoked |
| 31 | `src/redis_client.py` | 81 | Unnecessary `sleep(0.01)` after every pub/sub message |
| 32 | `src/router.py` | 19-20 | Silent drop of messages with missing sender/body — no log |
| 33 | `src/llm.py` | 6 | Empty API key sends `"no-key"` instead of failing clearly |
| 34 | `src/router.py` | 23-26 | Case-sensitive JID comparison may fail on formatting variants |
| 35 | `src/agents/business_analyst.py` | 43 | `BusinessProfile(None)` would crash on missing profile key |
| 36 | `src/intake/schema.py` | 21-25 | `completion_percentage` may drift from `next_empty_field` |
| 37 | `migrations/001_initial.py` | 20-43 | `server_default` strings treated as SQL text, not raw values |
| 38 | `admin/templates/index.html` | entire | Placeholder dashboard — no real admin features |
| 39 | `whatsapp-bridge/package.json` | 12 | `fluent-ffmpeg` listed but unused |
| 40 | `.env` | 7-8 | Group JIDs are empty — group features non-functional by default |
