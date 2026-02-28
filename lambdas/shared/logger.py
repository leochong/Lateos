"""
Structured logging utility for Lateos Lambda functions.

Uses AWS Lambda Powertools Logger for structured JSON logging
with automatic redaction of sensitive fields (RULE 8).
"""

import os

from aws_lambda_powertools import Logger

# Get log level from environment variable
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# Create logger instance
logger = Logger(
    service="lateos",
    level=LOG_LEVEL,
    log_uncaught_exceptions=True,
)


def get_logger(service_name: str) -> Logger:
    """
    Get a logger instance for a specific service.

    Args:
        service_name: Name of the service (e.g., "orchestrator", "validator")

    Returns:
        Logger instance configured for the service
    """
    return Logger(
        service=service_name,
        level=LOG_LEVEL,
        log_uncaught_exceptions=True,
    )


# Fields to redact from logs (RULE 8: No plaintext logging of secrets)
SENSITIVE_FIELDS = [
    "password",
    "token",
    "api_key",
    "secret",
    "access_key",
    "private_key",
    "authorization",
    "x-api-key",
    "session",
    "cookie",
]


def redact_sensitive_data(data: dict) -> dict:
    """
    Redact sensitive fields from a dictionary before logging.

    Args:
        data: Dictionary that may contain sensitive data

    Returns:
        Dictionary with sensitive fields redacted
    """
    if not isinstance(data, dict):
        return data

    redacted = data.copy()

    for key, value in data.items():
        # Check if key matches any sensitive field
        if any(sensitive in key.lower() for sensitive in SENSITIVE_FIELDS):
            redacted[key] = "***REDACTED***"
        # Recursively redact nested dictionaries
        elif isinstance(value, dict):
            redacted[key] = redact_sensitive_data(value)
        # Redact lists of dictionaries
        elif isinstance(value, list):
            redacted[key] = [
                redact_sensitive_data(item) if isinstance(item, dict) else item for item in value
            ]

    return redacted
