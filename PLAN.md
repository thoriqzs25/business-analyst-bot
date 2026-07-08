# Business Analyst Bot — Implementation Plan

## Stack
| Layer | Technology |
|---|---|
| WhatsApp | Baileys (Node.js sidecar) |
| Agent orchestration | LangGraph |
| Memory | Mem0 Python library (local Qdrant via Docker) |
| Observability | LangSmith (free Developer tier) |
| LLM | OpenCode Go — `deepseek-v4-flash` via `https://opencode.ai/zen/go/v1` |
| Bot language | Bahasa Indonesia |
| Message queue | Redis (Node ↔ Python pub/sub) |
| Checkpoint + structured data | PostgreSQL |
| Media storage | Filesystem + LLM vision description |
| Admin dashboard | FastAPI web (same Python server) |
| Migrations | Alembic |

## Architecture

```
                         ┌───────────┐
                         │  Browser  │
                         │(Dashboard)│
                         └─────┬─────┘
                               │
WhatsApp ──► Baileys (Node.js) │
                  │            │
             Redis pub/sub     │
                  │            │
           ┌──────▼───────┐   │
           │  Python App  ├───┘
           │  (FastAPI)   │
           └──┬───┬───┬───┘
              │   │   │
        ┌─────┘   │   └──────┐
        ▼         ▼          ▼
   Business    Skills     Coding
   Analyst    Manager    Agent
   Agent      Agent      Agent
   (Individual) (Skills  (Code
                  Group)   Group)
        │         │          │
        ▼         ▼          ▼
      Mem0    Filesystem   Filesystem
    (Qdrant)  (skills/    (codebase)
    + PG for   tools/)
    profiles

   ┌──────────┬──────────┬──────────┐
   │  Redis   │PostgreSQL│  Qdrant  │
   │ (queue)  │(checkpt+ │(vectors) │
   │          │ profiles)│          │
   └──────────┴──────────┴──────────┘
```

**Communication protocol (Node.js ↔ Python):**

| Redis Channel | Direction | Payload |
|---|---|---|
| `wa:incoming` | Node → Python | `{ msg_id, from, body, type, timestamp, media?, group_id? }` |
| `wa:outgoing` | Python → Node | `{ to, body, type, key? }` |
| `wa:auth` | Node → Python | `{ event: "qr" \| "connected" \| "disconnected" \| "reconnecting", data? }` |
| `wa:reaction` | Python → Node | `{ to, key, emoji }` |

**LangGraph checkpointing:**
- `PostgresSaver` persists graph state per user
- If server restarts mid-conversation, intake resumes at last node
- 15-minute inactivity timeout triggers reminder on next message

## User Interaction Model

### Individual Chat (Business Owners)
- **No commands.** Just natural conversation in Bahasa Indonesia.
- Bot initiates intake if no profile exists: "Halo! Saya asisten bisnis Anda. Boleh tahu nama usaha Anda?"
- Bot responds to Q&A using Mem0 memory + business profile
- On each message, bot checks PostgreSQL checkpoint → resumes LangGraph state
- **15-min inactivity:** Last message saved. Next time user chats, bot says: "Sebelumnya kita sempat diskusi tentang [topik]. Ingin lanjutkan?"

### Skills Group
- **Command prefix:** `!` (e.g., `!skill tambah`, `!tool hapus`, `!knowledge simpan`, `!reset`)
- **Template mode:** `!skill tambah` → bot asks structured questions:
  1. Nama skill?
  2. Deskripsi?
  3. Trigger phrase?
  4. Isi instruksi?
- **Conversation mode:** Chat naturally, bot extracts skill from discussion
- Commands: `!skill tambah`, `!skill hapus <nama>`, `!skill edit <nama>`, `!skill list`
- Same pattern for tools: `!tool tambah`, `!tool hapus`, `!tool list`
- Knowledge: `!knowledge simpan <teks>`, `!knowledge hapus <id>`, `!knowledge reset`, `!knowledge list`

### Coding Agent Group
- **Command prefix:** `!` 
- **`!feature tambah`** → Bot asks template questions:
  1. Fitur apa yang ingin ditambahkan?
  2. File mana yang terkait?
  3. Bagaimana perilaku yang diinginkan?
  4. Ada preferensi implementasi?
- **`!fix <deskripsi>`** → Describe bug, bot investigates and proposes fix
- After template, bot creates plan → sends to group → waits for confirmation
- Only applies changes after user says `!setuju` or `!konfirmasi`
- Commands: `!feature tambah`, `!feature list`, `!fix <bug>`, `!status`, `!cancel`

## Project Structure

```
business-analyst-bot/
├── whatsapp-bridge/           # Node.js Baileys sidecar
│   ├── package.json
│   └── index.js               # Baileys client + Redis pub/sub
├── src/                       # Python backend
│   ├── main.py                # FastAPI entry point
│   ├── redis_client.py        # Redis pub/sub
│   ├── config.py              # Phone numbers, groups, API keys
│   ├── llm.py                 # OpenCode Go client
│   ├── router.py              # Message router
│   ├── dedup.py               # Message dedup (by msg_id)
│   ├── token_tracker.py       # Token usage per user
│   ├── admin/
│   │   ├── __init__.py
│   │   ├── routes.py          # Web dashboard routes
│   │   └── templates/         # HTML templates
│   ├── agents/
│   │   ├── business_analyst.py
│   │   ├── skills_manager.py
│   │   └── coding_agent.py
│   ├── intake/
│   │   ├── graph.py           # LangGraph state machine
│   │   └── schema.py          # Pydantic business profile
│   ├── media/
│   │   └── handler.py         # Download + describe images
│   ├── models/
│   │   └── business_profile.py
│   ├── checkpoint/
│   │   └── postgres_saver.py
│   └── registry/
│       ├── loader.py          # Dynamic skill/tool loader
│       ├── skills/
│       └── tools/
├── migrations/                # Alembic migrations
├── tests/                     # Tests
│   ├── test_router.py
│   └── test_agents.py
├── docker-compose.yml
├── Dockerfile.python
├── Dockerfile.node
├── requirements.txt
├── pyproject.toml
├── alembic.ini
├── PLAN.md
├── AGENTS.md
├── conversations/
└── .env
```

## Docker Compose Services

| Service | Image | Exposed Ports |
|---|---|---|
| `python-app` | Custom | 8000 (API + dashboard) |
| `node-bridge` | Custom | — (internal) |
| `redis` | redis:7-alpine | 6379 |
| `postgres` | postgres:16-alpine | 5432 |
| `qdrant` | qdrant/qdrant | 6333, 6334 |

## Media Handling

- Images/docs saved to `media/{user_id}/{timestamp}_{filename}`
- Image sent to LLM vision for description
- Description stored in Mem0 memory
- Filesystem path logged in PostgreSQL profile

## Token Tracking

- Every LLM call logs: `{ user_id, timestamp, model, prompt_tokens, completion_tokens, cost }`
- Stored in PostgreSQL table `token_usage`
- Admin dashboard shows per-user token usage, total cost, trends
- Optional: per-user daily/monthly token limit

## Phases

### Phase 1 — Project Scaffolding
- pyproject.toml, requirements.txt, .env template
- Docker Compose (all 6 services)
- Dockerfile.python, Dockerfile.node
- Redis pub/sub setup (both Node and Python)
- PostgreSQL + Alembic initialization
- Basic health check endpoint

### Phase 2 — Baileys Bridge
- Node.js Baileys client with Redis pub/sub
- QR code display on first connection
- Auth event handling (reconnect, re-scan)
- Message deduplication by `msg_id`
- Media download pipeline

### Phase 3 — Business Analyst Agent
- LangGraph agent with Mem0 (Qdrant) + PostgreSQL checkpoint
- Bahasa Indonesia system prompt
- Intake state machine: greeting → nama → industri → omset → tim → masalah → tujuan → konfirmasi
- Conditional branching based on industry
- 15-min inactivity: save last node, remind on return
- Token tracking integration
- LangSmith tracing

### Phase 4 — Skills Group Manager
- Command parser (`!skill`, `!tool`, `!knowledge`, `!reset`)
- Template input mode (bot asks structured questions)
- Conversation mode (bot extracts intent from discussion)
- Read/write to registry/skills/ and registry/tools/
- Dynamic reload

### Phase 5 — Coding Agent Group
- Command parser (`!feature`, `!fix`, `!status`, `!cancel`, `!konfirmasi`)
- Template input for new features
- Bug investigation flow (`!fix deskripsi masalah`)
- LangGraph agent generates plan → posts to group → waits for confirmation
- Sandboxed shell + filesystem access
- Only applies changes on `!konfirmasi`

### Phase 6 — Admin Dashboard
- Web dashboard (FastAPI HTML)
- Business profiles list (searchable)
- Token usage per user (table + chart)
- Bot health status (connection, uptime)
- Recent conversations log
- Skills/tools registry browser

### Phase 7 — Testing + Polish
- Unit tests for router, agents, commands
- Integration test without WhatsApp (mock Baileys messages via Redis)
- Message deduplication (idempotency by `msg_id`)
- Rate limiting per user
- Error handling & retry for all services
- Graceful shutdown
- Qdrant + PostgreSQL backup strategy
- Startup script (`docker compose up --build`)
