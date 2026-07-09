"""
Registry Loader - Dynamic skill and tool loading

Loads skills (markdown docs) and tools (Python modules) from registry/ directory.
"""

import importlib.util
import logging
from pathlib import Path
from typing import Callable, Any

logger = logging.getLogger(__name__)

SKILLS_DIR = Path("registry/skills")
TOOLS_DIR = Path("registry/tools")

# Cache for loaded tools
_loaded_tools: dict[str, Callable] = {}


def list_skills() -> list[dict]:
    """List all available skills with metadata."""
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    
    skills = []
    for filepath in sorted(SKILLS_DIR.glob("*.md")):
        try:
            content = filepath.read_text(encoding="utf-8")
            lines = content.split("\n")
            
            # Extract title from first header
            title = filepath.stem.replace("_", " ").title()
            for line in lines:
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            
            # Extract description from second paragraph
            description = ""
            in_description = False
            for line in lines:
                if line.startswith("## Description"):
                    in_description = True
                    continue
                if in_description:
                    if line.startswith("##"):
                        break
                    description += line + " "
            
            skills.append({
                "name": filepath.stem,
                "title": title,
                "description": description.strip()[:200],
                "path": str(filepath),
            })
        except Exception as e:
            logger.error(f"Error reading skill {filepath}: {e}")
    
    return skills


def get_skill(name: str) -> str | None:
    """Get skill content by name."""
    filepath = SKILLS_DIR / f"{name}.md"
    if not filepath.exists():
        return None
    
    try:
        return filepath.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Error reading skill {name}: {e}")
        return None


def list_tools() -> list[dict]:
    """List all available tools with metadata."""
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    
    tools = []
    for filepath in sorted(TOOLS_DIR.glob("*.py")):
        try:
            content = filepath.read_text(encoding="utf-8")
            
            # Extract docstring
            docstring = ""
            if '"""' in content:
                parts = content.split('"""')
                if len(parts) >= 3:
                    docstring = parts[1].strip()
            
            # Get first line of docstring as description
            description = docstring.split("\n")[0][:100] if docstring else ""
            
            tools.append({
                "name": filepath.stem,
                "description": description,
                "path": str(filepath),
            })
        except Exception as e:
            logger.error(f"Error reading tool {filepath}: {e}")
    
    return tools


def load_tool(name: str) -> Callable | None:
    """
    Dynamically load a tool function from registry/tools/.
    
    Args:
        name: Tool name (without .py extension)
    
    Returns:
        The async function if found and loaded, None otherwise.
    """
    global _loaded_tools
    
    # Check cache first
    if name in _loaded_tools:
        return _loaded_tools[name]
    
    filepath = TOOLS_DIR / f"{name}.py"
    if not filepath.exists():
        logger.warning(f"Tool not found: {name}")
        return None
    
    try:
        # Load module dynamically
        spec = importlib.util.spec_from_file_location(f"tool_{name}", filepath)
        if not spec or not spec.loader:
            logger.error(f"Cannot load spec for tool: {name}")
            return None
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Get the main function (should match filename)
        func = getattr(module, name, None)
        if func is None:
            # Try to find any async function
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if callable(attr) and not attr_name.startswith("_"):
                    func = attr
                    break
        
        if func:
            _loaded_tools[name] = func
            logger.info(f"Tool loaded: {name}")
            return func
        else:
            logger.error(f"No callable found in tool: {name}")
            return None
            
    except Exception as e:
        logger.error(f"Error loading tool {name}: {e}")
        return None


def reload_tool(name: str) -> bool:
    """Reload a tool (for hot-reload during development)."""
    if name in _loaded_tools:
        del _loaded_tools[name]
    
    return load_tool(name) is not None


def reload_all_tools():
    """Reload all tools."""
    global _loaded_tools
    _loaded_tools.clear()
    
    for tool_info in list_tools():
        load_tool(tool_info["name"])
    
    logger.info(f"Reloaded {len(_loaded_tools)} tools")


def get_loaded_tools() -> dict[str, Callable]:
    """Get all currently loaded tools."""
    return _loaded_tools.copy()


# Initialize on import
logger.info("Registry loader initialized")
