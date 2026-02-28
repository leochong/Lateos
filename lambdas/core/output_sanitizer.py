"""
Output Sanitizer Lambda

Sanitizes output before returning to user.
Ensures RULE 8: No plaintext secrets in responses.

Sanitization:
- Redact API keys, tokens, passwords
- Remove internal error details
- Sanitize file paths
- Remove IP addresses and internal URLs
"""

import re
from typing import Any, Dict

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger(service="output-sanitizer")
tracer = Tracer(service="output-sanitizer")

# Patterns to redact (RULE 8)
REDACTION_PATTERNS = [
    # API keys and tokens
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

        logger.info(
            "Output sanitized",
            extra={
                "request_id": request_id,
                "output_size": len(str(sanitized_result)),
            },
        )

        return {
            "statusCode": 200,
            "sanitized_result": sanitized_result,
            "request_id": request_id,
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
