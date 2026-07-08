# Business Analyst Bot — Implementation Plan

## Stack
| Layer | Technology |
|---|---|
| WhatsApp | Baileys (Node.js sidecar) |
| Agent orchestration | LangGraph |
| Memory | Mem0 (self-hosted, Docker + Qdrant) |
| Observability | LangSmith |
| LLM | OpenCode Go API (OpenAI-compatible) |
| Bot language | Bahasa Indonesia |

## Architecture

```
WhatsApp ──► Baileys (Node.js sidecar)
                 │
                 ▼ HTTP POST/GET
          ┌──────────────┐
          │ Python Server │  (FastAPI)
          └──┬───┬───┬───┘
             │   │   │
       ┌─────┘   │   └──────┐
       ▼         ▼          ▼
  Business    Skills     Coding
  Analyst    Manager    Agent
  Agent      Agent      Agent
  (Group 1)  (Group 2)  (Group 3)
       │         │          │
       ▼         ▼          ▼
     Mem0    Filesystem   Filesystem
    (Qdrant)  (skills/    (codebase)
               tools/)
```

## Groups

| Group | Purpose | Capability |
|---|---|---|
| **Individual chat** | Business owners | Intake, Q&A, business profiling. Per-user Mem0 memory. |
| **Skills Group** | Devs/Admins | Add/modify skills (prompts) and tools (Python functions). Writes to `registry/skills/` and `registry/tools/`. |
| **Code Group** | Devs/Admins | Full coding assistant. Read/write any file in the bot codebase, run shell commands (sandboxed). |

## Project Structure

```
business-analyst-bot/
├── whatsapp-bridge/           # Node.js Baileys sidecar
│   ├── package.json
│   └── index.js
├── src/                       # Python backend
│   ├── main.py                # FastAPI entry point
│   ├── config.py              # Phone numbers, groups, API keys
│   ├── llm.py                 # OpenCode Go client
│   ├── router.py              # Message router
│   ├── agents/
│   │   ├── business_analyst.py   # LangGraph BA agent
│   │   ├── skills_manager.py     # LangGraph skills/tools agent
│   │   └── coding_agent.py       # LangGraph coding agent
│   ├── intake/
│   │   ├── graph.py           # LangGraph state machine
│   │   └── schema.py          # Pydantic business profile
│   ├── registry/
│   │   ├── loader.py          # Dynamic skill/tool loader
│   │   ├── skills/
│   │   └── tools/
│   └── knowledge/
├── docker-compose.yml         # Mem0 + Qdrant
├── requirements.txt
├── pyproject.toml
├── PLAN.md
├── AGENTS.md
├── conversations/
└── .env
```

## Phases

### Phase 1 — Scaffolding + WhatsApp Bridge
- Python project setup (pyproject.toml, requirements.txt, .env)
- Docker Compose: Mem0 + Qdrant + Python app + Node.js bridge
- Baileys Node.js sidecar (connect, auth, message forwarding)
- FastAPI webhook receiver

### Phase 2 — Business Analyst Agent
- LangGraph agent with Mem0 memory per user
- System prompt in Bahasa Indonesia
- Basic conversation flow (Q&A with memory)
- LangSmith tracing

### Phase 3 — Structured Intake Flow
- LangGraph state machine: greeting → nama → industri → omset → tim → masalah → tujuan → konfirmasi
- Business profile Pydantic schema
- Extract structured data from conversation → Mem0

### Phase 4 — Skills/Tools Manager
- LangGraph agent with filesystem access to registry/
- Can read/write skill files (markdown prompts)
- Can read/write tool files (Python functions)
- Dynamic reload after modification

### Phase 5 — Coding Agent
- LangGraph agent with sandboxed shell + filesystem access
- Can read/write any file in src/
- Can run tests, lint, etc.
- Restricted commands (no rm -rf, no network access)

### Phase 6 — Safety + Polish
- Message rate limiting
- Error handling & retry
- Graceful shutdown
- Backup strategy for Qdrant data
- Startup script
