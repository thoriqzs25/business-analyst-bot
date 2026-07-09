"""
Skills Manager Agent - Phase 4

Handles skill and tool management via WhatsApp group commands.
Commands:
  skill list              - List all skills
  skill read <name>       - Read a skill file
  skill create <name>     - Create new skill (interactive)
  skill update <name>     - Update skill (interactive)
  skill delete <name>     - Delete skill
  
  tool list               - List all tools
  tool read <name>        - Read a tool file
  tool create <name>      - Create new tool (interactive)
  tool update <name>      - Update tool (interactive)
  tool delete <name>      - Delete tool
"""

import logging
import os
import re
from pathlib import Path

from src.llm import chat
from src.redis_client import publish
from src.config import settings

logger = logging.getLogger(__name__)

SKILLS_DIR = Path("registry/skills")
TOOLS_DIR = Path("registry/tools")

SYSTEM_PROMPT = """Kamu adalah Skills Manager untuk Business Analyst Bot.

Tugasmu membantu developer mengelola skill dan tool via chat.

FORMAT SKILL (Markdown):
- File: registry/skills/<nama_skill>.md
- Struktur: # Title, ## Description, ## Usage, ## Examples

FORMAT TOOL (Python):
- File: registry/tools/<nama_tool>.py
- Harus ada docstring dengan description, args, returns
- Fungsi utama harus async

Respons singkat dan jelas dalam Bahasa Indonesia.
"""


def ensure_dirs():
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_filename(name: str) -> str:
    """Sanitize filename to prevent directory traversal."""
    name = re.sub(r'[^\w\-]', '_', name.lower())
    name = name.strip('_')
    return name


async def send_reply(group_id: str, text: str):
    """Send reply back to WhatsApp group via Redis."""
    await publish("wa:reply", {
        "group_id": group_id,
        "body": text,
    })


# ============ SKILL OPERATIONS ============

async def list_skills(group_id: str) -> str:
    ensure_dirs()
    files = sorted(SKILLS_DIR.glob("*.md"))
    if not files:
        return "📋 Belum ada skill. Gunakan: skill create <nama>"
    
    lines = ["📚 *Daftar Skill:*"]
    for f in files:
        name = f.stem
        content = f.read_text(encoding="utf-8")[:100]
        title = content.split("\n")[0].replace("#", "").strip() if content else name
        lines.append(f"• {name} - {title}")
    
    return "\n".join(lines)


async def read_skill(group_id: str, name: str) -> str:
    ensure_dirs()
    filename = sanitize_filename(name)
    filepath = SKILLS_DIR / f"{filename}.md"
    
    if not filepath.exists():
        return f"❌ Skill '{name}' tidak ditemukan."
    
    content = filepath.read_text(encoding="utf-8")
    # Truncate if too long for WhatsApp
    if len(content) > 3500:
        content = content[:3500] + "\n\n...(truncated)"
    
    return f"📖 *Skill: {filename}*\n```\n{content}\n```"


async def create_skill(sender: str, group_id: str, name: str, description: str) -> str:
    ensure_dirs()
    filename = sanitize_filename(name)
    filepath = SKILLS_DIR / f"{filename}.md"
    
    if filepath.exists():
        return f"⚠️ Skill '{filename}' sudah ada. Gunakan: skill update {filename}"
    
    # Generate skill content using LLM
    prompt = f"""
Buatkan skill documentation dalam format Markdown.

Nama Skill: {filename}
Deskripsi: {description}

Struktur yang diharapkan:
```markdown
# {filename.replace('_', ' ').title()}

## Description
{description}

## Usage
Cara menggunakan skill ini...

## Examples
Contoh penggunaan:
- Example 1: ...
- Example 2: ...

## Notes
Catatan tambahan...
```

Respons hanya berisi markdown content, tanpa penjelasan tambahan.
"""
    
    content, _, _ = await chat(SYSTEM_PROMPT, prompt)
    
    # Clean up markdown code block if present
    if content.startswith("```markdown"):
        content = content[11:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()
    
    filepath.write_text(content, encoding="utf-8")
    logger.info("Skill created: %s by %s", filename, sender)
    
    return f"✅ Skill '{filename}' berhasil dibuat!\n\n{content[:500]}..."


async def update_skill(sender: str, group_id: str, name: str, new_content: str) -> str:
    ensure_dirs()
    filename = sanitize_filename(name)
    filepath = SKILLS_DIR / f"{filename}.md"
    
    if not filepath.exists():
        return f"❌ Skill '{filename}' tidak ditemukan. Gunakan: skill create {filename}"
    
    filepath.write_text(new_content, encoding="utf-8")
    logger.info("Skill updated: %s by %s", filename, sender)
    
    return f"✅ Skill '{filename}' berhasil diupdate!"


async def delete_skill(sender: str, group_id: str, name: str) -> str:
    ensure_dirs()
    filename = sanitize_filename(name)
    filepath = SKILLS_DIR / f"{filename}.md"
    
    if not filepath.exists():
        return f"❌ Skill '{filename}' tidak ditemukan."
    
    filepath.unlink()
    logger.info("Skill deleted: %s by %s", filename, sender)
    
    return f"🗑️ Skill '{filename}' berhasil dihapus."


# ============ TOOL OPERATIONS ============

async def list_tools(group_id: str) -> str:
    ensure_dirs()
    files = sorted(TOOLS_DIR.glob("*.py"))
    if not files:
        return "🛠️ Belum ada tool. Gunakan: tool create <nama>"
    
    lines = ["🛠️ *Daftar Tool:*"]
    for f in files:
        name = f.stem
        content = f.read_text(encoding="utf-8")[:200]
        # Extract docstring
        docstring = ""
        if '"""' in content:
            parts = content.split('"""')
            if len(parts) >= 3:
                docstring = parts[1].split("\n")[0][:50]
        lines.append(f"• {name} - {docstring or 'No description'}")
    
    return "\n".join(lines)


async def read_tool(group_id: str, name: str) -> str:
    ensure_dirs()
    filename = sanitize_filename(name)
    filepath = TOOLS_DIR / f"{filename}.py"
    
    if not filepath.exists():
        return f"❌ Tool '{name}' tidak ditemukan."
    
    content = filepath.read_text(encoding="utf-8")
    if len(content) > 3500:
        content = content[:3500] + "\n\n...(truncated)"
    
    return f"📜 *Tool: {filename}*\n```python\n{content}\n```"


async def create_tool(sender: str, group_id: str, name: str, description: str) -> str:
    ensure_dirs()
    filename = sanitize_filename(name)
    filepath = TOOLS_DIR / f"{filename}.py"
    
    if filepath.exists():
        return f"⚠️ Tool '{filename}' sudah ada. Gunakan: tool update {filename}"
    
    # Generate tool content using LLM
    prompt = f"""
Buatkan Python tool function dalam format async.

Nama Tool: {filename}
Deskripsi: {description}

Struktur yang diharapkan:
```python
\"\"\"
{description}

Args:
    param1: description
    
Returns:
    result description
\"\"\"

import logging

logger = logging.getLogger(__name__)

async def {filename}(param1: str) -> dict:
    \"\"\"
    {description}
    \"\"\"
    try:
        # Implementation here
        result = {{"status": "success", "data": None}}
        return result
    except Exception as e:
        logger.error(f"Error in {filename}: {{e}}")
        return {{"status": "error", "message": str(e)}}
```

Respons hanya berisi Python code, tanpa penjelasan tambahan.
"""
    
    content, _, _ = await chat(SYSTEM_PROMPT, prompt)
    
    # Clean up code block if present
    if content.startswith("```python"):
        content = content[9:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()
    
    filepath.write_text(content, encoding="utf-8")
    logger.info("Tool created: %s by %s", filename, sender)
    
    return f"✅ Tool '{filename}' berhasil dibuat!\n\n{content[:500]}..."


async def update_tool(sender: str, group_id: str, name: str, new_content: str) -> str:
    ensure_dirs()
    filename = sanitize_filename(name)
    filepath = TOOLS_DIR / f"{filename}.py"
    
    if not filepath.exists():
        return f"❌ Tool '{filename}' tidak ditemukan. Gunakan: tool create {filename}"
    
    filepath.write_text(new_content, encoding="utf-8")
    logger.info("Tool updated: %s by %s", filename, sender)
    
    return f"✅ Tool '{filename}' berhasil diupdate!"


async def delete_tool(sender: str, group_id: str, name: str) -> str:
    ensure_dirs()
    filename = sanitize_filename(name)
    filepath = TOOLS_DIR / f"{filename}.py"
    
    if not filepath.exists():
        return f"❌ Tool '{filename}' tidak ditemukan."
    
    filepath.unlink()
    logger.info("Tool deleted: %s by %s", filename, sender)
    
    return f"🗑️ Tool '{filename}' berhasil dihapus."


# ============ COMMAND PARSER ============

async def process_command(sender: str, group_id: str, body: str):
    """Main entry point for skills manager commands."""
    logger.info("Skills manager: %s from %s", body[:60], sender)
    
    body = body.strip()
    parts = body.split(maxsplit=2)
    
    if len(parts) < 2:
        await send_reply(group_id, HELP_TEXT)
        return
    
    cmd_type = parts[0].lower()  # skill or tool
    action = parts[1].lower()    # list, read, create, update, delete
    name = parts[2] if len(parts) > 2 else ""
    
    reply = ""
    
    if cmd_type == "skill":
        if action == "list":
            reply = await list_skills(group_id)
        elif action == "read" and name:
            reply = await read_skill(group_id, name)
        elif action == "create" and name:
            # For create, we need description - use remaining text or ask
            reply = await create_skill(sender, group_id, name, name.replace("_", " "))
        elif action == "update" and name:
            reply = "✍️ Kirim konten baru dengan format:\n```\n<konten skill>\n```"
        elif action == "delete" and name:
            reply = await delete_skill(sender, group_id, name)
        else:
            reply = HELP_TEXT
    
    elif cmd_type == "tool":
        if action == "list":
            reply = await list_tools(group_id)
        elif action == "read" and name:
            reply = await read_tool(group_id, name)
        elif action == "create" and name:
            reply = await create_tool(sender, group_id, name, name.replace("_", " "))
        elif action == "update" and name:
            reply = "✍️ Kirim konten baru dengan format:\n```python\n<kode tool>\n```"
        elif action == "delete" and name:
            reply = await delete_tool(sender, group_id, name)
        else:
            reply = HELP_TEXT
    else:
        reply = HELP_TEXT
    
    await send_reply(group_id, reply)


HELP_TEXT = """📚 *Skills Manager Commands:*

*Skill:*
• skill list
• skill read <nama>
• skill create <nama>
• skill update <nama>
• skill delete <nama>

*Tool:*
• tool list
• tool read <nama>
• tool create <nama>
• tool update <nama>
• tool delete <nama>
"""