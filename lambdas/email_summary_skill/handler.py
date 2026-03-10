"""
Email Summary Skill Lambda

LinkedIn demo: Fetches unread Gmail messages, summarizes them with Bedrock,
and detects prompt injection attempts in email content.

Implements RULE 1: All secrets via Secrets Manager (OAuth token).
Implements RULE 4: No shell execution.
Implements RULE 8: Redact email addresses and tokens from CloudWatch logs.

Security features demonstrated:
- Per-email prompt injection detection
- Redacted logging of sensitive data
- OAuth token refresh handling
- Scoped IAM role (single secret ARN only)
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Initialize AWS clients
secrets_manager = boto3.client("secretsmanager")
bedrock_runtime = boto3.client("bedrock-runtime", region_name="us-east-1")

# Initialize logger and tracer
logger = Logger(service="email_summary_skill")
tracer = Tracer(service="email_summary_skill")

# Environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")

# Prompt injection patterns (RULE 5 compliance)
INJECTION_PATTERNS = [
    r"ignore\s+(previous|all|your)\s+instructions?",
    r"forget\s+(your|all|previous)\s+instructions?",
    r"new\s+instructions?:",
    r"system\s+prompt",
    r"reveal\s+(your|the)\s+prompt",
    r"disregard\s+(previous|all|your)",
    r"you\s+are\s+(now|a)",
    r"(forward|send)\s+(all|everything)\s+(to|emails)",
    r"reveal\s+(token|secret|key|password)",
]


class EmailSummaryError(Exception):
    """Raised when email summary operation fails"""

    pass


def get_gmail_credentials(user_id: str) -> Credentials:
    """
    Retrieve Gmail OAuth credentials from Secrets Manager and create Credentials object.

    Args:
        user_id: User ID for secret isolation (e.g., "demo-user-001")

    Returns:
        Google OAuth2 Credentials object with auto-refresh enabled

    Raises:
        EmailSummaryError: If credentials cannot be retrieved or refreshed
    """
    secret_name = f"lateos/{ENVIRONMENT}/gmail/{user_id}"

    try:
        # Retrieve secret from Secrets Manager (RULE 1: Never from env vars)
        response = secrets_manager.get_secret_value(SecretId=secret_name)
        secret_data = json.loads(response["SecretString"])

        # Create Credentials object
        creds = Credentials(
            token=secret_data.get("token"),
            refresh_token=secret_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=secret_data.get("client_id"),
            client_secret=secret_data.get("client_secret"),
            scopes=secret_data.get("scopes", ["https://www.googleapis.com/auth/gmail.readonly"]),
        )

        # Refresh token if expired
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                logger.info("OAuth token expired, refreshing...")
                creds.refresh(Request())
                logger.info("OAuth token refreshed successfully")
            else:
                raise EmailSummaryError("OAuth token is invalid and cannot be refreshed")

        return creds

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ResourceNotFoundException":
            logger.warning(f"Gmail credentials not found for user {user_id}")
            raise EmailSummaryError("Gmail not connected. Please authorize Gmail first.")
        else:
            # RULE 8: Redact error details that might contain sensitive data
            logger.error(f"Failed to retrieve Gmail credentials: {error_code}")
            raise EmailSummaryError("Failed to access Gmail credentials")
    except Exception as e:
        logger.error(f"Unexpected error retrieving credentials: {type(e).__name__}")
        raise EmailSummaryError("Failed to access Gmail credentials")


def check_for_injection(email_body: str) -> bool:
    """
    Check email body for prompt injection patterns.

    This simulates what the VALIDATOR Lambda does at the API layer,
    but applied per-email for the demo.

    Args:
        email_body: The email body text to check

    Returns:
        True if injection pattern detected, False otherwise
    """
    if not email_body:
        return False

    email_lower = email_body.lower()

    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, email_lower, re.IGNORECASE):
            logger.warning(
                f"Prompt injection pattern detected: {pattern}",
                extra={"pattern": pattern},
            )
            return True

    return False


def fetch_unread_emails(creds: Credentials, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Fetch unread emails from Gmail API.

    Args:
        creds: Google OAuth2 Credentials object
        max_results: Maximum number of emails to fetch (default 5)

    Returns:
        List of email dicts with id, from, subject, snippet, body fields

    Raises:
        EmailSummaryError: If Gmail API call fails
    """
    try:
        # Build Gmail API service
        service = build("gmail", "v1", credentials=creds)

        # List unread messages
        results = (
            service.users()
            .messages()
            .list(userId="me", labelIds=["INBOX", "UNREAD"], maxResults=max_results)
            .execute()
        )

        messages = results.get("messages", [])

        if not messages:
            logger.info("No unread messages found")
            return []

        emails = []

        # Fetch details for each message
        for msg in messages:
            msg_id = msg["id"]
            message = service.users().messages().get(userId="me", id=msg_id).execute()

            # Extract headers
            headers = message["payload"]["headers"]
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(No Subject)")
            sender = next((h["value"] for h in headers if h["name"] == "From"), "(Unknown)")

            # Extract snippet and body
            snippet = message.get("snippet", "")

            # Get body text (simplified - just use snippet for now)
            body = snippet

            emails.append(
                {
                    "id": msg_id,
                    "from": sender,
                    "subject": subject,
                    "snippet": snippet,
                    "body": body,
                }
            )

        logger.info(f"Fetched {len(emails)} unread emails")
        return emails

    except Exception as e:
        logger.error(f"Failed to fetch Gmail messages: {type(e).__name__}: {str(e)}")
        raise EmailSummaryError("Failed to fetch Gmail messages")


def redact_email_address(text: str) -> str:
    """
    Redact email addresses from text for logging (RULE 8).

    Args:
        text: Text that may contain email addresses

    Returns:
        Text with email addresses redacted
    """
    # Simple email regex
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    return re.sub(email_pattern, "***@***", text)


def summarize_with_bedrock(emails: List[Dict[str, Any]]) -> str:
    """
    Summarize emails using Amazon Bedrock (Claude Haiku).

    Args:
        emails: List of email dicts to summarize

    Returns:
        Summary text from Bedrock

    Raises:
        EmailSummaryError: If Bedrock call fails
    """
    if not emails:
        return "No unread emails to summarize."

    # Build email list for prompt
    email_list = []
    for i, email in enumerate(emails, 1):
        # RULE 8: Redact email addresses from what we log
        redacted_from = redact_email_address(email["from"])
        logger.info(f"Email {i}: from={redacted_from}, subject={email['subject']}")

        email_list.append(
            f"Email {i}:\n"
            f"From: {email['from']}\n"
            f"Subject: {email['subject']}\n"
            f"Preview: {email['snippet']}\n"
        )

    email_text = "\n".join(email_list)

    # Build Bedrock prompt (RULE 5: Sanitize input, instruct model not to reproduce PII)
    prompt = f"""You are summarizing emails for a user. Here are their unread emails:

{email_text}

Summarize each email in 2 sentences. Flag anything urgent.

IMPORTANT: Do not reproduce any personal data, phone numbers, or email addresses verbatim in your response."""

    try:
        # Call Bedrock
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        }

        response = bedrock_runtime.invoke_model(
            modelId=BEDROCK_MODEL_ID, body=json.dumps(request_body)
        )

        response_body = json.loads(response["body"].read())
        summary = response_body["content"][0]["text"]

        logger.info("Bedrock summary generated successfully")
        return summary

    except Exception as e:
        logger.error(f"Failed to call Bedrock: {type(e).__name__}: {str(e)}")
        raise EmailSummaryError("Failed to generate email summary")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=False)  # Don't log event - may contain emails
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Email Summary Skill Lambda handler.

    Event format:
    {
        "user_id": "demo-user-001",
        "max_emails": 5  # optional
    }

    Returns:
    {
        "statusCode": 200,
        "body": {
            "summary": "<Bedrock summary>",
            "emails_processed": 5,
            "emails_blocked": 1,
            "blocked_emails": [
                {
                    "id": "...",
                    "reason": "Prompt injection detected"
                }
            ]
        }
    }
    """
    logger.info("Email summary skill invoked")

    try:
        # Extract user context
        user_id = event.get("user_id")
        if not user_id:
            raise EmailSummaryError("Missing user_id in request")

        max_emails = event.get("max_emails", 5)

        # Get Gmail credentials from Secrets Manager
        creds = get_gmail_credentials(user_id)

        # Fetch unread emails
        emails = fetch_unread_emails(creds, max_results=max_emails)

        if not emails:
            return {
                "statusCode": 200,
                "body": {
                    "summary": "No unread emails.",
                    "emails_processed": 0,
                    "emails_blocked": 0,
                    "blocked_emails": [],
                },
            }

        # Check each email for injection attempts
        safe_emails = []
        blocked_emails = []

        for email in emails:
            if check_for_injection(email["body"]):
                # Block this email from being passed to Bedrock
                blocked_emails.append(
                    {
                        "id": email["id"],
                        "subject": email["subject"],
                        "reason": "Prompt injection detected",
                    }
                )
                logger.warning(
                    f"Blocked email {email['id']} from Bedrock due to injection pattern",
                    extra={"email_id": email["id"]},
                )
            else:
                safe_emails.append(email)

        # Summarize safe emails with Bedrock
        if safe_emails:
            summary = summarize_with_bedrock(safe_emails)
        else:
            summary = "All emails were blocked due to potential security issues."

        # Add blocked email notice to summary if any were blocked
        if blocked_emails:
            summary += f"\n\n⚠️ WARNING: {len(blocked_emails)} email(s) blocked due to suspected prompt injection attempts."

        return {
            "statusCode": 200,
            "body": {
                "summary": summary,
                "emails_processed": len(safe_emails),
                "emails_blocked": len(blocked_emails),
                "blocked_emails": blocked_emails,
            },
        }

    except EmailSummaryError as e:
        logger.error(f"Email summary error: {e}")
        return {"statusCode": 400, "body": {"error": str(e), "skill": "email_summary"}}
    except Exception as e:
        logger.exception(f"Unexpected error in email summary skill: {e}")
        return {
            "statusCode": 500,
            "body": {"error": "Internal server error", "skill": "email_summary"},
        }
