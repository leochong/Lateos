"""
MCP Protocol Handler Lambda

Implements Model Context Protocol (MCP) server interface for Lateos.
Exposes Lateos skills as MCP tools for Claude Desktop integration.

MCP Methods:
- initialize: Protocol handshake
- tools/list: Return available tools (lateos_email_summary)
- tools/call: Execute tool by invoking email_skill Lambda

Security:
- Cognito JWT authentication (same as /agent endpoint)
- User context extracted from authorizer claims
- Audit logging to DynamoDB
- Implements RULE 2: Scoped IAM (invoke email_skill only)
"""

import json
import os
from datetime import datetime
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize AWS clients
lambda_client = boto3.client("lambda")
dynamodb = boto3.resource("dynamodb")

# Initialize logger and tracer
logger = Logger(service="mcp_handler")
tracer = Tracer(service="mcp_handler")

# Environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
EMAIL_SKILL_FUNCTION_NAME = os.environ.get("EMAIL_SKILL_FUNCTION_NAME")
AUDIT_TABLE_NAME = os.environ.get("AUDIT_TABLE_NAME")

# MCP Protocol version
MCP_PROTOCOL_VERSION = "2024-11-05"

# MCP Tool schema
MCP_TOOLS = [
    {
        "name": "lateos_email_summary",
        "description": (
            "Securely reads and summarizes emails. Credentials managed via "
            "AWS Secrets Manager. Prompt injection blocked by Bedrock Guardrails."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "max_emails": {
                    "type": "integer",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                    "description": "Maximum number of emails to retrieve",
                },
                "filter": {
                    "type": "object",
                    "properties": {
                        "sender": {
                            "type": "string",
                            "description": "Filter by sender email address",
                        },
                        "subject_contains": {
                            "type": "string",
                            "description": "Filter by subject keyword",
                        },
                        "since_hours": {
                            "type": "integer",
                            "default": 24,
                            "description": "Only emails from last N hours",
                        },
                    },
                },
                "summary_style": {
                    "type": "string",
                    "enum": ["brief", "detailed", "action_items"],
                    "default": "brief",
                    "description": "Summary format style",
                },
            },
        },
    }
]


# MCP Error codes (JSON-RPC 2.0)
MCP_ERROR_PARSE = -32700
MCP_ERROR_INVALID_REQUEST = -32600
MCP_ERROR_METHOD_NOT_FOUND = -32601
MCP_ERROR_INVALID_PARAMS = -32602
MCP_ERROR_INTERNAL = -32603


class MCPError(Exception):
    """MCP protocol error"""

    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


def extract_user_context(event: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract user context from Cognito JWT in API Gateway event.

    Args:
        event: API Gateway proxy event

    Returns:
        User context dict with user_id, email, username

    Raises:
        MCPError: If user context cannot be extracted
    """
    try:
        authorizer = event.get("requestContext", {}).get("authorizer", {})
        claims = authorizer.get("claims", {})

        user_id = claims.get("sub")
        if not user_id:
            raise MCPError(
                MCP_ERROR_INVALID_REQUEST,
                "Missing user_id in authentication token",
            )

        return {
            "user_id": user_id,
            "email": claims.get("email"),
            "username": claims.get("cognito:username"),
        }
    except MCPError:
        raise
    except Exception as e:
        logger.error(f"Failed to extract user context: {e}")
        raise MCPError(MCP_ERROR_INTERNAL, "Failed to authenticate user")


def log_mcp_action(user_id: str, method: str, details: Dict[str, Any]) -> None:
    """
    Log MCP action to audit table.

    Args:
        user_id: Cognito user ID
        method: MCP method name
        details: Action details dict
    """
    if not AUDIT_TABLE_NAME:
        logger.warning("Audit table not configured, skipping audit log")
        return

    try:
        table = dynamodb.Table(AUDIT_TABLE_NAME)
        table.put_item(
            Item={
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "skill": "mcp_handler",
                "action": method,
                "details": json.dumps(details),
            }
        )
        logger.info(f"Logged MCP action: {method} for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to log MCP action: {e}")
        # Don't fail the request if audit logging fails


def handle_initialize(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle MCP initialize method.

    Args:
        params: Initialize parameters

    Returns:
        Initialize response
    """
    logger.info("MCP initialize called", extra={"params": params})

    return {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "capabilities": {
            "tools": {},
        },
        "serverInfo": {
            "name": "lateos-mcp-server",
            "version": "1.0.0",
        },
    }


def handle_tools_list() -> Dict[str, Any]:
    """
    Handle MCP tools/list method.

    Returns:
        List of available tools
    """
    logger.info("MCP tools/list called")

    return {
        "tools": MCP_TOOLS,
    }


def handle_tools_call(user_id: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle MCP tools/call method.

    Invokes email_skill Lambda with user_id and tool arguments.

    Args:
        user_id: Cognito user ID
        tool_name: Name of tool to call
        arguments: Tool arguments

    Returns:
        Tool execution result

    Raises:
        MCPError: If tool not found or execution fails
    """
    logger.info(
        "MCP tools/call",
        extra={"tool_name": tool_name, "user_id": user_id},
    )

    # Validate tool name
    if tool_name != "lateos_email_summary":
        raise MCPError(
            MCP_ERROR_METHOD_NOT_FOUND,
            f"Tool not found: {tool_name}",
            {"available_tools": ["lateos_email_summary"]},
        )

    # Validate email_skill function is configured
    if not EMAIL_SKILL_FUNCTION_NAME:
        raise MCPError(
            MCP_ERROR_INTERNAL,
            "Email skill not configured",
        )

    # Build email_summary_skill event payload
    max_emails = arguments.get("max_emails", 5)  # Default to 5 for summary

    # Email summary skill takes user_id and max_emails
    email_event = {
        "user_id": user_id,
        "max_emails": max_emails,
    }

    try:
        # Invoke email_skill Lambda
        logger.info(
            "Invoking email_skill Lambda",
            extra={
                "function_name": EMAIL_SKILL_FUNCTION_NAME,
                "user_id": user_id,
            },
        )

        response = lambda_client.invoke(
            FunctionName=EMAIL_SKILL_FUNCTION_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps(email_event),
        )

        # Parse response
        payload = json.loads(response["Payload"].read())
        logger.info("Email skill response", extra={"status_code": payload.get("statusCode")})

        if payload.get("statusCode") != 200:
            error_msg = payload.get("body", {}).get("error", "Email summary skill failed")
            raise MCPError(MCP_ERROR_INTERNAL, error_msg)

        # Extract summary from email_summary_skill response
        body = payload.get("body", {})
        summary = body.get("summary", "No summary available")
        emails_processed = body.get("emails_processed", 0)
        emails_blocked = body.get("emails_blocked", 0)
        blocked_emails = body.get("blocked_emails", [])

        # Add metadata to summary
        summary_with_metadata = f"{summary}\n\n---\n"
        summary_with_metadata += f"Emails processed: {emails_processed}\n"
        if emails_blocked > 0:
            summary_with_metadata += f"⚠️ Emails blocked (injection detected): {emails_blocked}\n"
            for blocked in blocked_emails:
                summary_with_metadata += (
                    f"  - {blocked.get('subject', 'No subject')}: {blocked.get('reason')}\n"
                )

        # Use the full summary with metadata
        summary = summary_with_metadata

        # Log to audit
        log_mcp_action(
            user_id,
            "tools/call",
            {
                "tool_name": tool_name,
                "arguments": arguments,
                "emails_processed": emails_processed,
                "emails_blocked": emails_blocked,
            },
        )

        return {
            "content": [
                {
                    "type": "text",
                    "text": summary,
                }
            ],
        }

    except ClientError as e:
        logger.error(f"Failed to invoke email_skill: {e}")
        raise MCPError(
            MCP_ERROR_INTERNAL,
            "Failed to execute email skill",
            {"error": str(e)},
        )


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    MCP Handler Lambda entry point.

    Handles MCP protocol requests from Claude Desktop.

    Args:
        event: API Gateway proxy event
        context: Lambda context

    Returns:
        API Gateway proxy response
    """
    try:
        # Parse request body (MCP JSON-RPC format)
        try:
            body = json.loads(event.get("body", "{}"))
        except json.JSONDecodeError:
            raise MCPError(MCP_ERROR_PARSE, "Invalid JSON in request body")

        # Extract MCP fields
        jsonrpc = body.get("jsonrpc")
        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")

        # Validate JSON-RPC version
        if jsonrpc != "2.0":
            raise MCPError(MCP_ERROR_INVALID_REQUEST, "Invalid JSON-RPC version")

        # Validate method
        if not method:
            raise MCPError(MCP_ERROR_INVALID_REQUEST, "Missing method")

        logger.info(
            "MCP request received",
            extra={"method": method, "request_id": request_id},
        )

        # Extract user context (for authenticated methods)
        user_context = None
        if method not in ["initialize"]:
            user_context = extract_user_context(event)
            logger.info(f"User authenticated: {user_context['user_id']}")

        # Route to appropriate handler
        if method == "initialize":
            result = handle_initialize(params)
        elif method == "tools/list":
            result = handle_tools_list()
        elif method == "tools/call":
            # Validate required params
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if not tool_name:
                raise MCPError(
                    MCP_ERROR_INVALID_PARAMS,
                    "Missing required parameter: name",
                )

            result = handle_tools_call(user_context["user_id"], tool_name, arguments)
        else:
            raise MCPError(MCP_ERROR_METHOD_NOT_FOUND, f"Method not found: {method}")

        # Return MCP success response
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result,
                }
            ),
        }

    except MCPError as e:
        logger.error(f"MCP error: code={e.code}, msg={e.message}, data={e.data}")
        return {
            "statusCode": 200,  # MCP errors return 200 with error in body
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": body.get("id") if "body" in locals() else None,
                    "error": {
                        "code": e.code,
                        "message": e.message,
                        "data": e.data,
                    },
                }
            ),
        }

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "error": "Internal server error",
                    "message": str(e),
                }
            ),
        }
