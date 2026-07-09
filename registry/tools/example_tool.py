"""
Example tool demonstrating the tool format.

Args:
    name: User name to greet
    
Returns:
    Greeting message dictionary
"""

import logging

logger = logging.getLogger(__name__)


async def example_tool(name: str = "User") -> dict:
    """
    Simple example tool that returns a greeting.
    
    Args:
        name: Name to greet
        
    Returns:
        dict with greeting message
    """
    try:
        message = f"Hello, {name}! This is an example tool."
        logger.info(f"Example tool called with name: {name}")
        
        return {
            "status": "success",
            "data": {"message": message},
        }
    except Exception as e:
        logger.error(f"Error in example_tool: {e}")
        return {
            "status": "error",
            "message": str(e),
        }
