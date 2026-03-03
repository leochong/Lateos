"""
Output Sanitizer Lambda

Sanitizes output before returning to user.
Ensures RULE 8: No plaintext secrets in responses.

Sanitization:
- Redact API keys, tokens, passwords
- Remove internal error details
- Sanitize file paths
- Remove IP addresses and internal URLs
- Apply Bedrock Guardrails for harmful content, PII, profanity (Phase 3)

LocalStack Compatible:
- Falls back gracefully if Bedrock Guardrails not available
"""

import json
import os
import re
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

logger = Logger(service="output-sanitizer")
tracer = Tracer(service="output-sanitizer")

# Bedrock client for Guardrails
try:
    bedrock_runtime = boto3.client("bedrock-runtime")
    BEDROCK_AVAILABLE = True
except Exception as e:
    logger.warning(f"Bedrock client initialization failed (LocalStack?): {e}")
    bedrock_runtime = None
    BEDROCK_AVAILABLE = False

# Environment variables
GUARDRAILS_ID = os.environ.get("GUARDRAILS_ID", "")
GUARDRAILS_VERSION = os.environ.get("GUARDRAILS_VERSION", "DRAFT")

# Patterns to redact (RULE 8)
REDACTION_PATTERNS = [
    # API keys and tokens
    (r"\bsk-[A-Za-z0-9]{16,}\b", "***REDACTED_API_KEY***"),  # OpenAI-style keys
    (r"\b[A-Za-z0-9]{32,}\b", "***REDACTED_TOKEN***"),
    (r'api[_-]?key["\']?\s*[:=]\s*["\']?([A-Za-z0-9_\-]+)', "api_key: ***REDACTED***"),
    (r'token["\']?\s*[:=]\s*["\']?([A-Za-z0-9_\-\.]+)', "token: ***REDACTED***"),
    # AWS credentials
    (r"AKIA[0-9A-Z]{16}", "***REDACTED_AWS_KEY***"),
    (
        r'aws_secret_access_key["\']?\s*[:=]\s*["\']?([A-Za-z0-9/+=]+)',
        "aws_secret_access_key: ***REDACTED***",
    ),
    # Private keys
    (
        r"-----BEGIN [A-Z ]+PRIVATE KEY-----[\s\S]+?-----END [A-Z ]+PRIVATE KEY-----",
        "***REDACTED_PRIVATE_KEY***",
    ),
    # Email addresses (optional - may want to keep these)
    # (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '***@***.***'),
    # IP addresses (internal ranges)
    (r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "***INTERNAL_IP***"),
    (r"\b172\.(1[6-9]|2[0-9]|3[01])\.\d{1,3}\.\d{1,3}\b", "***INTERNAL_IP***"),
    (r"\b192\.168\.\d{1,3}\.\d{1,3}\b", "***INTERNAL_IP***"),
    # File paths
    (r"/home/[^\s]+", "***FILE_PATH***"),
    (r"C:\\Users\\[^\s]+", "***FILE_PATH***"),
    # Stack traces (remove sensitive file paths)
    (r'File "(/[^"]+)"', 'File "***PATH***"'),
]


def sanitize_text(text: str) -> str:
    """
    Sanitize text by redacting sensitive patterns.

    Args:
        text: Raw output text

    Returns:
        Sanitized text with sensitive data redacted
    """
    sanitized = text

    for pattern, replacement in REDACTION_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized)

    return sanitized


def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively sanitize dictionary values.

    Args:
        data: Dictionary that may contain sensitive data

    Returns:
        Sanitized dictionary
    """
    if not isinstance(data, dict):
        return data

    sanitized = {}

    for key, value in data.items():
        # Redact sensitive keys entirely
        sensitive_keys = ["password", "token", "secret", "api_key", "private_key"]
        if any(sk in key.lower() for sk in sensitive_keys):
            sanitized[key] = "***REDACTED***"
        # Recursively sanitize nested dicts
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict(value)
        # Sanitize lists
        elif isinstance(value, list):
            sanitized[key] = [
                (
                    sanitize_dict(item)
                    if isinstance(item, dict)
                    else sanitize_text(str(item)) if isinstance(item, str) else item
                )
                for item in value
            ]
        # Sanitize string values
        elif isinstance(value, str):
            sanitized[key] = sanitize_text(value)
        else:
            sanitized[key] = value

    return sanitized


def apply_guardrails(text: str) -> Dict[str, Any]:
    """
    Apply Bedrock Guardrails to text output.

    Blocks harmful content, detects PII, filters profanity.
    Falls back gracefully if Bedrock not available (LocalStack).

    Args:
        text: Text to check with Guardrails

    Returns:
        Dict with 'allowed' (bool) and optional 'reason' (str)
    """
    if not BEDROCK_AVAILABLE or not bedrock_runtime:
        logger.info("Bedrock Guardrails not available, skipping (LocalStack mode)")
        return {"allowed": True, "reason": "guardrails_disabled"}

    if not GUARDRAILS_ID:
        logger.warning("GUARDRAILS_ID not configured, skipping Guardrails check")
        return {"allowed": True, "reason": "guardrails_not_configured"}

    try:
        response = bedrock_runtime.apply_guardrail(
            guardrailIdentifier=GUARDRAILS_ID,
            guardrailVersion=GUARDRAILS_VERSION,
            source="OUTPUT",
            content=[{"text": {"text": text}}],
        )

        action = response.get("action", "NONE")
        assessments = response.get("assessments", [])

        if action == "GUARDRAIL_INTERVENED":
            # Extract intervention reasons
            reasons = []
            for assessment in assessments:
                if "topicPolicy" in assessment:
                    topics = assessment["topicPolicy"].get("topics", [])
                    for topic in topics:
                        if topic.get("action") == "BLOCKED":
                            reasons.append(f"blocked_topic:{topic.get('name', 'unknown')}")

                if "contentPolicy" in assessment:
                    filters = assessment["contentPolicy"].get("filters", [])
                    for filter_item in filters:
                        if filter_item.get("action") == "BLOCKED":
                            reasons.append(f"blocked_content:{filter_item.get('type', 'unknown')}")

                if "wordPolicy" in assessment:
                    words = assessment["wordPolicy"].get("customWords", [])
                    for word in words:
                        if word.get("action") == "BLOCKED":
                            reasons.append("blocked_profanity")

                if "sensitiveInformationPolicy" in assessment:
                    pii = assessment["sensitiveInformationPolicy"].get("piiEntities", [])
                    for entity in pii:
                        if entity.get("action") == "BLOCKED":
                            reasons.append(f"blocked_pii:{entity.get('type', 'unknown')}")

            logger.warning(
                "Guardrails blocked output",
                extra={"action": action, "reasons": reasons},
            )

            return {"allowed": False, "reason": ", ".join(reasons) if reasons else "blocked"}

        logger.info("Guardrails check passed", extra={"action": action})
        return {"allowed": True, "reason": "passed"}

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ResourceNotFoundException":
            logger.warning(
                "Guardrails configuration not found, allowing output", extra={"error": str(e)}
            )
            return {"allowed": True, "reason": "guardrails_not_found"}
        else:
            logger.error("Guardrails check failed", extra={"error": str(e)})
            # Fail open: allow output if Guardrails check fails
            return {"allowed": True, "reason": "guardrails_error"}
    except Exception as e:
        logger.exception("Unexpected error in Guardrails check", extra={"error": str(e)})
        # Fail open: allow output if unexpected error
        return {"allowed": True, "reason": "guardrails_exception"}


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Output Sanitizer Lambda handler.

    Args:
        event: Contains action result to sanitize
        context: Lambda context

    Returns:
        Sanitized output ready for user
    """
    try:
        request_id = event.get("request_id", "unknown")
        action_result = event.get("result", {})

        logger.info(
            "Sanitizing output",
            extra={
                "request_id": request_id,
                "has_result": action_result is not None,
            },
        )

        # Sanitize the result
        sanitized_result = sanitize_dict(action_result) if isinstance(action_result, dict) else {}

        # Extract message if present and sanitize
        message = action_result.get("message", "") if isinstance(action_result, dict) else ""
        if message:
            sanitized_message = sanitize_text(str(message))
            sanitized_result["message"] = sanitized_message

        # Apply Bedrock Guardrails to final output (Phase 3)
        final_output = json.dumps(sanitized_result)
        guardrails_result = apply_guardrails(final_output)

        if not guardrails_result["allowed"]:
            logger.warning(
                "Output blocked by Guardrails",
                extra={
                    "request_id": request_id,
                    "reason": guardrails_result.get("reason"),
                },
            )
            # Return safe error message instead of blocked content
            return {
                "statusCode": 400,
                "sanitized_result": {
                    "message": (
                        "The response was blocked by content safety filters. "
                        "Please rephrase your request."
                    )
                },
                "request_id": request_id,
                "guardrails_blocked": True,
                "guardrails_reason": guardrails_result.get("reason"),
            }

        logger.info(
            "Output sanitized and Guardrails passed",
            extra={
                "request_id": request_id,
                "output_size": len(str(sanitized_result)),
                "guardrails_reason": guardrails_result.get("reason"),
            },
        )

        return {
            "statusCode": 200,
            "sanitized_result": sanitized_result,
            "request_id": request_id,
            "guardrails_passed": True,
        }

    except Exception as e:
        logger.exception("Output sanitization error", extra={"error": str(e)})
        # Return safe error message
        return {
            "statusCode": 200,
            "sanitized_result": {
                "message": "An error occurred processing your request. Please try again."
            },
            "error": "Sanitization failed",
        }
