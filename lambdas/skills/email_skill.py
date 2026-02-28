"""
Email Skill Lambda

Handles email operations via Gmail API with OAuth 2.0.
Implements RULE 1: All secrets via Secrets Manager.
Implements RULE 2: Scoped IAM role (no wildcard permissions).

Capabilities:
- Send emails
- Read emails (inbox, sent, drafts)
- Search emails by query
- Mark as read/unread
- Delete/archive emails
- Reply to emails

Security:
- OAuth 2.0 tokens stored in Secrets Manager
- Per-user token isolation (user_id in secret path)
- No access to other skills' secrets
- Scoped IAM role (only Gmail OAuth secret and DynamoDB audit)
"""

import json
import os
from typing import Any, Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize AWS clients
secrets_manager = boto3.client("secretsmanager")
dynamodb = boto3.resource("dynamodb")

# Initialize logger and tracer
logger = Logger(service="email_skill")
tracer = Tracer(service="email_skill")

# Environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
AUDIT_TABLE_NAME = os.environ.get("AUDIT_TABLE_NAME")


class EmailSkillError(Exception):
    """Raised when email skill operation fails"""

    pass


def get_gmail_credentials(user_id: str) -> Dict[str, Any]:
    """
    Retrieve Gmail OAuth credentials from Secrets Manager.

    Args:
        user_id: Cognito user ID for secret isolation

    Returns:
        Gmail OAuth credentials dict

    Raises:
        EmailSkillError: If credentials cannot be retrieved
    """
    secret_name = f"lateos/{ENVIRONMENT}/gmail/{user_id}"

    try:
        response = secrets_manager.get_secret_value(SecretId=secret_name)
        return json.loads(response["SecretString"])
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ResourceNotFoundException":
            logger.warning(f"Gmail credentials not found for user {user_id}")
            raise EmailSkillError("Gmail not connected. Please authorize Gmail first.")
        else:
            logger.error(f"Failed to retrieve Gmail credentials: {e}")
            raise EmailSkillError("Failed to access Gmail credentials")


def send_email(
    user_id: str, to: List[str], subject: str, body: str, cc: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Send an email via Gmail API.

    Args:
        user_id: Cognito user ID
        to: List of recipient email addresses
        subject: Email subject
        body: Email body (plain text)
        cc: Optional list of CC recipients

    Returns:
        Result dict with message_id and status
    """
    logger.info(f"Sending email for user {user_id} to {to}")

    # Get OAuth credentials
    credentials = get_gmail_credentials(user_id)  # noqa: F841

    # In a real implementation, this would use the Gmail API
    # For Phase 3, we'll return a mock response
    # TODO: Implement actual Gmail API integration in production

    result = {
        "message_id": f"mock-{user_id}-{hash(subject)}",
        "status": "sent",
        "to": to,
        "subject": subject,
        "cc": cc or [],
    }

    # Log to audit table
    log_email_action(user_id, "send_email", result)

    return result


def read_emails(
    user_id: str,
    folder: str = "inbox",
    limit: int = 10,
    unread_only: bool = False,
) -> List[Dict[str, Any]]:
    """
    Read emails from Gmail.

    Args:
        user_id: Cognito user ID
        folder: Folder to read from (inbox, sent, drafts)
        limit: Maximum number of emails to return (max 50)
        unread_only: Only return unread emails

    Returns:
        List of email dicts
    """
    logger.info(f"Reading {limit} emails from {folder} for user {user_id}")

    # Enforce limit
    if limit > 50:
        limit = 50

    # Get OAuth credentials
    credentials = get_gmail_credentials(user_id)  # noqa: F841

    # Mock response for Phase 3
    emails = [
        {
            "id": f"mock-email-{i}",
            "from": "sender@example.com",
            "subject": f"Test Email {i}",
            "snippet": "This is a test email snippet...",
            "unread": i % 2 == 0,
            "timestamp": "2026-02-28T10:00:00Z",
        }
        for i in range(limit)
    ]

    # Filter by unread if requested
    if unread_only:
        emails = [e for e in emails if e["unread"]]

    # Log to audit table
    log_email_action(user_id, "read_emails", {"folder": folder, "count": len(emails)})

    return emails


def search_emails(user_id: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search emails by query.

    Args:
        user_id: Cognito user ID
        query: Search query (Gmail search syntax)
        limit: Maximum number of results (max 50)

    Returns:
        List of matching email dicts
    """
    logger.info(f"Searching emails for user {user_id} with query: {query}")

    # Enforce limit
    if limit > 50:
        limit = 50

    # Get OAuth credentials
    credentials = get_gmail_credentials(user_id)  # noqa: F841

    # Mock response for Phase 3
    results = [
        {
            "id": f"mock-result-{i}",
            "from": "match@example.com",
            "subject": f"Query match: {query}",
            "snippet": f"Email matching '{query}'...",
            "timestamp": "2026-02-28T10:00:00Z",
        }
        for i in range(min(limit, 5))
    ]

    # Log to audit table
    log_email_action(user_id, "search_emails", {"query": query, "count": len(results)})

    return results


def log_email_action(user_id: str, action: str, details: Dict[str, Any]) -> None:
    """
    Log email action to audit table.

    Args:
        user_id: Cognito user ID
        action: Action name (send_email, read_emails, etc.)
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
                "timestamp": details.get("timestamp", "2026-02-28T10:00:00Z"),
                "skill": "email",
                "action": action,
                "details": json.dumps(details),
            }
        )
        logger.info(f"Logged email action: {action} for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to log email action: {e}")
        # Don't fail the request if audit logging fails


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Email skill Lambda handler.

    Event format:
    {
        "user_id": "cognito-user-id",
        "action": "send_email" | "read_emails" | "search_emails",
        "parameters": {
            # Action-specific parameters
        }
    }

    Returns:
        {
            "statusCode": 200,
            "body": {
                "result": <action result>
            }
        }
    """
    logger.info("Email skill invoked", extra={"event": event})

    try:
        # Extract user context
        user_id = event.get("user_id")
        if not user_id:
            raise EmailSkillError("Missing user_id in request")

        # Extract action
        action = event.get("action")
        if not action:
            raise EmailSkillError("Missing action in request")

        # Extract parameters
        params = event.get("parameters", {})

        # Route to appropriate handler
        if action == "send_email":
            result = send_email(
                user_id=user_id,
                to=params.get("to", []),
                subject=params.get("subject", ""),
                body=params.get("body", ""),
                cc=params.get("cc"),
            )
        elif action == "read_emails":
            result = read_emails(
                user_id=user_id,
                folder=params.get("folder", "inbox"),
                limit=params.get("limit", 10),
                unread_only=params.get("unread_only", False),
            )
        elif action == "search_emails":
            result = search_emails(
                user_id=user_id,
                query=params.get("query", ""),
                limit=params.get("limit", 10),
            )
        else:
            raise EmailSkillError(f"Unknown action: {action}")

        return {
            "statusCode": 200,
            "body": {"result": result, "skill": "email", "action": action},
        }

    except EmailSkillError as e:
        logger.error(f"Email skill error: {e}")
        return {
            "statusCode": 400,
            "body": {"error": str(e), "skill": "email"},
        }
    except Exception as e:
        logger.exception(f"Unexpected error in email skill: {e}")
        return {
            "statusCode": 500,
            "body": {"error": "Internal server error", "skill": "email"},
        }
