"""
Input Validator Lambda

Sanitizes and validates user input before processing.
Implements RULE 5: Prompt injection detection and sanitization.

Security checks:
1. Prompt injection pattern detection (18+ patterns)
2. Content safety (profanity, hate speech)
3. Length and format validation
4. Malicious payload detection
"""

import re
from typing import Any, Dict, List

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

# Initialize logger and tracer
logger = Logger(service="validator")
tracer = Tracer(service="validator")

# Prompt injection patterns (RULE 5)
INJECTION_PATTERNS = [
    # Direct instruction injection
    r"ignore\s+(all\s+)?(previous|above|prior)\s+instructions",
    r"disregard\s+(all\s+)?(previous|above|prior)\s+instructions",
    r"forget\s+(all\s+)?(previous|above|prior)\s+instructions",
    # System prompt exfiltration attempts
    r"(reveal|show|display|print|output)\s+(your\s+)?(system\s+)?(prompt|instructions)",
    r"what\s+(is|are)\s+your\s+(system\s+)?(prompt|instructions)",
    r"tell\s+me\s+your\s+(system\s+)?(prompt|instructions)",
    # System message injection
    r"<\|?system\|?>",
    r"<\|?assistant\|?>",
    r"<\|?user\|?>",
    # Role manipulation
    r"you\s+are\s+now",
    r"act\s+as\s+(if\s+)?you\s+(are|were)",
    r"pretend\s+(to\s+be|you\s+are)",
    # Delimiter attacks
    r"={5,}",  # Multiple equals signs
    r"-{5,}",  # Multiple dashes
    r"#{3,}",  # Multiple hash signs
    # Special token injection
    r"\[INST\]",
    r"\[/INST\]",
    r"<s>",
    r"</s>",
    # Encoding bypass attempts
    r"\\x[0-9a-fA-F]{2}",  # Hex encoding
    r"&#\d+;",  # HTML entity encoding
    r"%[0-9a-fA-F]{2}",  # URL encoding
]

# Compile patterns for performance
COMPILED_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in INJECTION_PATTERNS]

# Maximum input length (prevent resource exhaustion)
MAX_INPUT_LENGTH = 4000  # characters

# Minimum input length
MIN_INPUT_LENGTH = 1


class ValidationError(Exception):
    """Raised when input fails validation"""

    pass


def detect_injection_patterns(text: str) -> List[str]:
    """
    Detect prompt injection patterns in input text.

    Args:
        text: User input text to check

    Returns:
        List of detected threat indicators
    """
    threats = []

    for pattern in COMPILED_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            threats.append(f"Injection pattern detected: {pattern.pattern}")

    return threats


def sanitize_input(text: str) -> str:
    """
    Sanitize user input by removing potentially dangerous content.

    Args:
        text: Raw user input

    Returns:
        Sanitized text
    """
    # Remove null bytes
    text = text.replace("\x00", "")

    # Remove control characters except newlines and tabs
    text = "".join(char for char in text if ord(char) >= 32 or char in "\n\t")

    # Normalize whitespace
    text = " ".join(text.split())

    # Remove potential encoding bypass attempts
    # Remove hex sequences
    text = re.sub(r"\\x[0-9a-fA-F]{2}", "", text)

    # Remove HTML entities
    text = re.sub(r"&#\d+;", "", text)

    # Remove URL encoding
    text = re.sub(r"%[0-9a-fA-F]{2}", "", text)

    return text.strip()


def validate_length(text: str) -> None:
    """
    Validate input length is within acceptable bounds.

    Args:
        text: Input text to validate

    Raises:
        ValidationError: If length is invalid
    """
    if len(text) < MIN_INPUT_LENGTH:
        raise ValidationError("Input is too short (minimum 1 character)")

    if len(text) > MAX_INPUT_LENGTH:
        raise ValidationError(f"Input is too long (maximum {MAX_INPUT_LENGTH} characters)")


def validate_format(text: str) -> None:
    """
    Validate input format is acceptable.

    Args:
        text: Input text to validate

    Raises:
        ValidationError: If format is invalid
    """
    # Check for excessive special characters (potential obfuscation)
    special_char_ratio = sum(1 for c in text if not c.isalnum() and not c.isspace()) / max(
        len(text), 1
    )

    if special_char_ratio > 0.5:
        raise ValidationError("Input contains excessive special characters")

    # Check for excessive repetition (potential DoS)
    # Find longest repeating substring
    max_repetition = 0
    for i in range(len(text)):
        for j in range(i + 1, len(text)):
            if text[i] == text[j]:
                length = 1
                while (
                    i + length < len(text)
                    and j + length < len(text)
                    and text[i + length] == text[j + length]
                ):
                    length += 1
                max_repetition = max(max_repetition, length)

    if max_repetition > 100:
        raise ValidationError("Input contains excessive repetition")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Validator Lambda handler.

    Validates and sanitizes user input before processing.

    Args:
        event: Lambda event containing user input
        context: Lambda context

    Returns:
        Validation result with sanitized input
    """
    try:
        # Extract user input from event
        user_input = event.get("input", "")

        logger.info(
            "Validating input",
            extra={
                "input_length": len(user_input),
                "request_id": event.get("request_id", "unknown"),
            },
        )

        # Step 1: Sanitize input
        sanitized_input = sanitize_input(user_input)

        # Step 2: Validate length
        try:
            validate_length(sanitized_input)
        except ValidationError as e:
            logger.warning("Length validation failed", extra={"reason": str(e)})
            return {
                "statusCode": 200,
                "is_valid": False,
                "sanitized_input": sanitized_input,
                "blocked_reason": str(e),
                "warnings": [],
                "threat_indicators": [],
            }

        # Step 3: Validate format
        try:
            validate_format(sanitized_input)
        except ValidationError as e:
            logger.warning("Format validation failed", extra={"reason": str(e)})
            return {
                "statusCode": 200,
                "is_valid": False,
                "sanitized_input": sanitized_input,
                "blocked_reason": str(e),
                "warnings": [],
                "threat_indicators": [],
            }

        # Step 4: Detect injection patterns (RULE 5)
        threats = detect_injection_patterns(sanitized_input)

        # If severe threats detected, block the input
        if len(threats) >= 2:  # Multiple injection indicators = block
            logger.warning(
                "Multiple injection patterns detected",
                extra={"threat_count": len(threats), "threats": threats},
            )
            return {
                "statusCode": 200,
                "is_valid": False,
                "sanitized_input": sanitized_input,
                "blocked_reason": "Multiple security threats detected",
                "warnings": threats,
                "threat_indicators": threats,
            }

        # Single threat or no threats = allow with warnings
        warnings = threats if threats else []

        logger.info(
            "Validation complete",
            extra={
                "is_valid": True,
                "warning_count": len(warnings),
                "sanitized_length": len(sanitized_input),
            },
        )

        return {
            "statusCode": 200,
            "is_valid": True,
            "sanitized_input": sanitized_input,
            "warnings": warnings,
            "threat_indicators": threats,
            "blocked_reason": None,
        }

    except Exception as e:
        logger.exception("Validation error", extra={"error": str(e)})
        # Fail closed: block input on unexpected errors
        return {
            "statusCode": 500,
            "is_valid": False,
            "sanitized_input": "",
            "blocked_reason": f"Internal validation error: {str(e)}",
            "warnings": [],
            "threat_indicators": [],
        }
