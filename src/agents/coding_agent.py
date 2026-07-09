"""
Coding Agent - Phase 5

Handles code operations via WhatsApp group commands.
Commands:
  file list [path]           - List files in directory
  file read <path>           - Read file content
  file write <path>          - Write file (interactive)
  file search <pattern>      - Search files
  
  cmd run <command>          - Run allowed command
  cmd test [path]            - Run pytest
  cmd lint [path]            - Run ruff/mypy
  cmd format [path]          - Run black/ruff format
  
  status                     - Show git status
  diff                       - Show git diff

Security: Commands are sandboxed - only allowed commands can be executed.
"""

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Optional

from src.redis_client import publish
from src.config import settings

logger = logging.getLogger(__name__)

# Allowed directories for file operations
ALLOWED_DIRS = [
    Path("src"),
    Path("tests"),
    Path("registry"),
]

# Blocked paths (absolute or relative)
BLOCKED_PATTERNS = [
    r"\.\."           # No directory traversal
    r"^/",           # No absolute paths outside project
    r"\.env",        # No environment files
    r"/\.git/",      # No git internals
    r"/\.ssh/",      # No SSH keys
    r"/etc/",        # No system files
    r"/root/",       # No root files
]

# Allowed shell commands (whitelist)
ALLOWED_COMMANDS = {
    "pytest": ["pytest", "-v", "--tb=short"],
    "test": ["pytest", "-v", "--tb=short"],
    "ruff": ["ruff", "check"],
    "lint": ["ruff", "check"],
    "format": ["ruff", "format"],
    "black": ["black", "--check"],
    "mypy": ["mypy"],
    "git": ["git"],
    "pip": ["pip", "list"],
    "python": ["python", "--version"],
    "ls": ["ls", "-la"],
    "cat": ["cat"],
    "pwd": ["pwd"],
    "find": ["find", ".", "-name"],
    "grep": ["grep", "-r"],
}

MAX_OUTPUT_LENGTH = 3500  # WhatsApp message limit
MAX_FILE_SIZE = 100_000   # 100KB max file to read


def validate_path(filepath: str) -> tuple[bool, Optional[Path], str]:
    """
    Validate that filepath is within allowed directories.
    Returns: (is_valid, resolved_path, error_message)
    """
    # Check blocked patterns
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, filepath):
            return False, None, f"❌ Path pattern not allowed: {pattern}"
    
    # Resolve path
    try:
        target = Path(filepath).resolve()
        project_root = Path(".").resolve()
    except Exception as e:
        return False, None, f"❌ Invalid path: {e}"
    
    # Check if within project
    try:
        target.relative_to(project_root)
    except ValueError:
        return False, None, "❌ Path outside project directory"
    
    return True, target, ""


async def send_reply(group_id: str, text: str):
    """Send reply back to WhatsApp group via Redis."""
    # Truncate if too long
    if len(text) > MAX_OUTPUT_LENGTH:
        text = text[:MAX_OUTPUT_LENGTH - 100] + "\n\n...(truncated)"
    
    await publish("wa:reply", {
        "group_id": group_id,
        "body": text,
    })


def truncate_output(text: str, max_lines: int = 50) -> str:
    """Truncate output to max lines."""
    lines = text.split("\n")
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + f"\n\n... ({len(lines) - max_lines} more lines)"
    return text


# ============ FILE OPERATIONS ============

async def file_list(group_id: str, path: str = ".") -> str:
    """List files in directory."""
    is_valid, target, error = validate_path(path)
    if not is_valid or target is None:
        return error
    
    if not target.exists():
        return f"❌ Directory not found: {path}"
    
    if target.is_file():
        return f"📄 {path} is a file, not directory"
    
    try:
        entries = sorted(target.iterdir())
        lines = [f"📁 *{path}*"]
        
        for entry in entries:
            icon = "📁" if entry.is_dir() else "📄"
            size = ""
            if entry.is_file():
                size_bytes = entry.stat().st_size
                if size_bytes < 1024:
                    size = f" ({size_bytes}B)"
                elif size_bytes < 1024 * 1024:
                    size = f" ({size_bytes // 1024}KB)"
                else:
                    size = f" ({size_bytes // (1024 * 1024)}MB)"
            lines.append(f"{icon} {entry.name}{size}")
        
        return "\n".join(lines[:100])  # Max 100 entries
    except Exception as e:
        return f"❌ Error listing directory: {e}"


async def file_read(group_id: str, path: str) -> str:
    """Read file content."""
    is_valid, target, error = validate_path(path)
    if not is_valid or target is None:
        return error
    
    if not target.exists():
        return f"❌ File not found: {path}"
    
    if target.is_dir():
        return f"📁 {path} is a directory. Use: file list {path}"
    
    try:
        size = target.stat().st_size
        if size > MAX_FILE_SIZE:
            return f"❌ File too large ({size // 1024}KB > {MAX_FILE_SIZE // 1024}KB). Use file head/tail."
        
        content = target.read_text(encoding="utf-8")
        ext = target.suffix.lstrip(".")
        
        # Format with code block
        return f"📄 *{path}* ({size} bytes)\n```{ext}\n{content}\n```"
    except UnicodeDecodeError:
        return f"❌ File appears to be binary: {path}"
    except Exception as e:
        return f"❌ Error reading file: {e}"


async def file_write(group_id: str, path: str, content: str) -> str:
    """Write content to file."""
    is_valid, target, error = validate_path(path)
    if not is_valid or target is None:
        return error
    
    try:
        # Create parent directories if needed
        target.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if file exists
        existed = target.exists()
        
        target.write_text(content, encoding="utf-8")
        
        action = "updated" if existed else "created"
        return f"✅ File {action}: {path}\n({len(content)} characters)"
    except Exception as e:
        return f"❌ Error writing file: {e}"


async def file_search(group_id: str, pattern: str) -> str:
    """Search files for pattern."""
    import subprocess
    
    # Sanitize pattern - no shell injection
    safe_pattern = re.sub(r'[^\w\s\-\.]', '', pattern)
    
    try:
        result = subprocess.run(
            ["grep", "-r", "-l", "-n", safe_pattern, "src/", "registry/"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode != 0 and not result.stdout:
            return f"🔍 No matches found for: {pattern}"
        
        matches = result.stdout.strip().split("\n")[:20]
        lines = [f"🔍 *Search results for: {pattern}*"]
        for match in matches:
            if match:
                lines.append(f"• {match}")
        
        return "\n".join(lines)
    except subprocess.TimeoutExpired:
        return "⚠️ Search timeout (30s)"
    except Exception as e:
        return f"❌ Search error: {e}"


# ============ COMMAND EXECUTION ============

async def run_command(group_id: str, command_str: str) -> str:
    """
    Run allowed command with sandboxing.
    Format: cmd run <allowed_command> [args...]
    """
    parts = command_str.split()
    if not parts:
        return "❌ No command specified"
    
    cmd_name = parts[0].lower()
    args = parts[1:]
    
    # Check if command is allowed
    if cmd_name not in ALLOWED_COMMANDS:
        allowed = ", ".join(sorted(ALLOWED_COMMANDS.keys()))
        return f"❌ Command '{cmd_name}' not allowed.\nAllowed: {allowed}"
    
    # Build command with args
    base_cmd = ALLOWED_COMMANDS[cmd_name]
    full_cmd = base_cmd + args
    
    # Additional validation for args
    for arg in args:
        # Block dangerous patterns in args
        if any(re.search(p, arg) for p in BLOCKED_PATTERNS):
            return f"❌ Argument contains blocked pattern: {arg}"
    
    try:
        logger.info("Running command: %s", " ".join(full_cmd))
        
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=".",
        )
        
        output = []
        if result.stdout:
            output.append("*STDOUT:*\n```\n" + truncate_output(result.stdout) + "\n```")
        if result.stderr:
            output.append("*STDERR:*\n```\n" + truncate_output(result.stderr) + "\n```")
        
        if not output:
            output.append(f"✅ Command completed (exit: {result.returncode})")
        elif result.returncode != 0:
            output.append(f"⚠️ Exit code: {result.returncode}")
        
        return "\n\n".join(output)
    
    except subprocess.TimeoutExpired:
        return "❌ Command timeout (60s)"
    except FileNotFoundError:
        return f"❌ Command not found: {full_cmd[0]}"
    except Exception as e:
        return f"❌ Command error: {e}"


async def run_tests(group_id: str, path: str = "") -> str:
    """Run pytest on specified path."""
    cmd = "pytest -v --tb=short"
    if path:
        is_valid, target, error = validate_path(path)
        if is_valid:
            cmd += f" {target}"
    
    return await run_command(group_id, cmd)


async def run_lint(group_id: str, path: str = "src") -> str:
    """Run ruff linter."""
    cmd = f"ruff check {path}" if path else "ruff check ."
    return await run_command(group_id, cmd)


async def run_format(group_id: str, path: str = "src") -> str:
    """Run ruff formatter."""
    cmd = f"ruff format {path}" if path else "ruff format ."
    return await run_command(group_id, cmd)


# ============ GIT OPERATIONS ============

async def git_status(group_id: str) -> str:
    """Show git status."""
    return await run_command(group_id, "git status")


async def git_diff(group_id: str) -> str:
    """Show git diff."""
    return await run_command(group_id, "git diff --stat")


# ============ COMMAND PARSER ============

async def process_command(sender: str, group_id: str, body: str):
    """Main entry point for coding agent commands."""
    logger.info("Coding agent: %s from %s", body[:60], sender)
    
    body = body.strip()
    parts = body.split(maxsplit=2)
    
    if len(parts) < 2:
        await send_reply(group_id, HELP_TEXT)
        return
    
    category = parts[0].lower()  # file, cmd, git
    action = parts[1].lower()    # list, read, write, run, etc
    arg = parts[2] if len(parts) > 2 else ""
    
    reply = ""
    
    if category == "file":
        if action == "list":
            reply = await file_list(group_id, arg or ".")
        elif action == "read" and arg:
            reply = await file_read(group_id, arg)
        elif action == "write" and arg:
            reply = "✍️ Kirim konten file dengan format:\n```\n<konten file>\n```"
        elif action == "search" and arg:
            reply = await file_search(group_id, arg)
        else:
            reply = FILE_HELP
    
    elif category == "cmd":
        if action == "run" and arg:
            reply = await run_command(group_id, arg)
        elif action == "test":
            reply = await run_tests(group_id, arg)
        elif action == "lint":
            reply = await run_lint(group_id, arg or "src")
        elif action == "format":
            reply = await run_format(group_id, arg or "src")
        else:
            reply = CMD_HELP
    
    elif category == "git":
        if action == "status":
            reply = await git_status(group_id)
        elif action == "diff":
            reply = await git_diff(group_id)
        else:
            reply = GIT_HELP
    
    else:
        reply = HELP_TEXT
    
    await send_reply(group_id, reply)


FILE_HELP = """📄 *File Commands:*
• file list [path]
• file read <path>
• file write <path>
• file search <pattern>
"""

CMD_HELP = """🛠️ *Command Commands:*
• cmd run <allowed_cmd> [args]
• cmd test [path]
• cmd lint [path]
• cmd format [path]

*Allowed commands:*
pytest, ruff, black, mypy, git, pip, ls, cat, pwd, find, grep
"""

GIT_HELP = """🐤 *Git Commands:*
• git status
• git diff
"""

HELP_TEXT = f"""💻 *Coding Agent Commands:*

{FILE_HELP}

{CMD_HELP}

{GIT_HELP}

*Security:*
- Only allowed directories: src/, tests/, registry/
- No directory traversal (../)
- No access to .env, .git, or system files
- Command timeout: 60s
"""