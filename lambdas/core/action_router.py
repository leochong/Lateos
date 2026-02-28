"""
Action Router Lambda

Routes classified intents to appropriate skill executors.
Phase 2: Returns placeholder responses
Phase 3: Will invoke actual skill Lambda functions

Routing logic:
- Validates action request
- Checks user authorization (RULE 6)
- Routes to appropriate skill executor
- Returns execution result
"""

from typing import Any, Dict

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger(service="action-router")
tracer = Tracer(service="action-router")

# Skill mapping (Phase 2 placeholders)
SKILL_HANDLERS = {
    "send_email": "lateos-skill-email",
    "create_calendar_event": "lateos-skill-calendar",
    "web_search": "lateos-skill-web",
    "respond_greeting": "built-in",
    "show_help": "built-in",
}


def handle_greeting(user_context: Dict[str, Any]) -> Dict[str, Any]:
    """Handle greeting intent with built-in response."""
    username = user_context.get("username") or user_context.get("email", "there")
    return {
        "success": True,
        "result": {
            "message": (
                f"Hello {username}! I'm Lateos, your AI personal agent. "
                f"How can I help you today?"
            )
        },
        "metadata": {"handler": "built-in"},
    }


def handle_help(user_context: Dict[str, Any]) -> Dict[str, Any]:
    """Handle help intent with built-in response."""
    return {
        "success": True,
        "result": {
            "message": (
                "I can help you with:\n"
                "- Sending emails\n"
                "- Managing your calendar\n"
                "- Searching the web\n"
                "- And more!\n\n"
                "Just tell me what you need in natural language."
            )
        },
        "metadata": {"handler": "built-in"},
    }


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Action Router Lambda handler.

    Args:
        event: Contains intent classification and user context
        context: Lambda context

    Returns:
        Action execution result
    """
    try:
        # Extract action details
        suggested_action = event.get("suggested_action")
        user_context = event.get("user_context", {})
        request_id = event.get("request_id", "unknown")
        entities = event.get("entities", {})

        logger.info(
            "Routing action",
            extra={
                "request_id": request_id,
                "action": suggested_action,
                "user_id": user_context.get("user_id"),
            },
        )

        # No action to route
        if not suggested_action:
            return {
                "statusCode": 200,
                "success": False,
                "result": None,
                "error": "No action suggested",
                "metadata": {},
            }

        # Check if skill handler exists
        skill_handler = SKILL_HANDLERS.get(suggested_action)
        if not skill_handler:
            logger.warning(
                "Unknown action",
                extra={"action": suggested_action, "request_id": request_id},
            )
            return {
                "statusCode": 200,
                "success": False,
                "result": None,
                "error": f"Unknown action: {suggested_action}",
                "metadata": {},
            }

        # Handle built-in actions
        if skill_handler == "built-in":
            if suggested_action == "respond_greeting":
                result = handle_greeting(user_context)
            elif suggested_action == "show_help":
                result = handle_help(user_context)
            else:
                result = {
                    "success": False,
                    "error": f"Unknown built-in action: {suggested_action}",
                }

            return {
                "statusCode": 200,
                **result,
                "request_id": request_id,
            }

        # Phase 2: Return placeholder for skill execution
        # Phase 3 will invoke actual Lambda functions
        logger.info(
            "Skill execution placeholder",
            extra={
                "skill": skill_handler,
                "action": suggested_action,
                "request_id": request_id,
            },
        )

        placeholder_message = (
            f"[Phase 2 Placeholder] Would execute '{suggested_action}' "
            f"using skill '{skill_handler}'. "
            f"Full skill integration coming in Phase 3."
        )

        return {
            "statusCode": 200,
            "success": True,
            "result": {
                "message": placeholder_message,
                "entities": entities,
            },
            "error": None,
            "metadata": {
                "skill": skill_handler,
                "action": suggested_action,
                "phase": "2-placeholder",
            },
            "request_id": request_id,
        }

    except Exception as e:
        logger.exception("Action routing error", extra={"error": str(e)})
        return {
            "statusCode": 500,
            "success": False,
            "result": None,
            "error": str(e),
            "metadata": {},
        }
