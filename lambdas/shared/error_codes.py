"""
LATEOS Error Code System

Standardized error codes for all Lambda functions.
Enables consistent error handling, logging, and investigation.

Usage:
    from shared.error_codes import LateosError, ErrorCode

    # Raise structured error
    raise LateosError(ErrorCode.PROMPT_INJECTION_DETECTED, user_id="user-123")

    # Return error response
    return ErrorCode.INPUT_VALIDATION_FAILED.to_response(details={"field": "message"})
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


@dataclass
class ErrorCodeDefinition:
    """Definition of a LATEOS error code"""

    code: str
    message: str
    http_status: int
    investigation_steps: str
    category: str


class ErrorCode(Enum):
    """
    LATEOS standardized error codes.

    Format: LATEOS-XXX where XXX is a 3-digit number.
    Categories: 001-099 Security, 100-199 Validation, 200-299 Integration,
                300-399 Infrastructure, 400-499 Business Logic
    """

    # Security Errors (001-099)
    PROMPT_INJECTION_DETECTED = ErrorCodeDefinition(
        code="LATEOS-001",
        message="Prompt injection detected and blocked",
        http_status=400,
        investigation_steps=(
            "1. Review DynamoDB audit log for user_id and request_id\n"
            "2. Check CloudWatch Logs for full request payload\n"
            "3. Analyze detected patterns in threat_indicators field\n"
            "4. If false positive, consider adjusting detection threshold"
        ),
        category="Security",
    )

    COGNITO_TOKEN_VALIDATION_FAILED = ErrorCodeDefinition(
        code="LATEOS-002",
        message="Cognito JWT token validation failed",
        http_status=401,
        investigation_steps=(
            "1. Verify token is not expired (check exp claim)\n"
            "2. Confirm token issuer matches Cognito User Pool\n"
            "3. Check if user account is disabled or deleted\n"
            "4. Review API Gateway authorizer logs"
        ),
        category="Security",
    )

    INPUT_VALIDATION_FAILED = ErrorCodeDefinition(
        code="LATEOS-003",
        message="Input validation failed (length or format)",
        http_status=400,
        investigation_steps=(
            "1. Check input length against MAX_INPUT_LENGTH (4000)\n"
            "2. Verify no control characters or null bytes\n"
            "3. Confirm input meets minimum length (1 char)\n"
            "4. Review sanitized_message field for issues"
        ),
        category="Validation",
    )

    INTENT_CLASSIFICATION_FAILED = ErrorCodeDefinition(
        code="LATEOS-004",
        message="Intent classification failed",
        http_status=500,
        investigation_steps=(
            "1. Check if Bedrock API is available\n"
            "2. Review intent_classifier Lambda logs\n"
            "3. Verify IAM permissions for bedrock:InvokeModel\n"
            "4. Check if input was too ambiguous to classify"
        ),
        category="Business Logic",
    )

    COST_KILL_SWITCH_TRIGGERED = ErrorCodeDefinition(
        code="LATEOS-005",
        message="Cost kill switch triggered - service suspended",
        http_status=503,
        investigation_steps=(
            "1. Check AWS Budgets dashboard for current spend\n"
            "2. Review SNS cost alerts for threshold details\n"
            "3. Verify kill switch Lambda execution in CloudWatch\n"
            "4. Check if API Gateway has been disabled\n"
            "5. Resume service: re-enable API Gateway after cost review"
        ),
        category="Infrastructure",
    )

    SECRET_REDACTION_APPLIED = ErrorCodeDefinition(
        code="LATEOS-006",
        message="Secret redaction applied to output",
        http_status=200,
        investigation_steps=(
            "1. Review output_sanitizer logs for redacted content\n"
            "2. Check REDACTION_PATTERNS in output_sanitizer.py\n"
            "3. Verify no secrets leaked in final response\n"
            "4. If over-redacting, adjust regex patterns\n"
            "NOTE: This is informational, not an error"
        ),
        category="Security",
    )

    SKILL_IAM_PERMISSION_DENIED = ErrorCodeDefinition(
        code="LATEOS-007",
        message="Skill Lambda IAM permission denied",
        http_status=500,
        investigation_steps=(
            "1. Check CloudTrail for AccessDenied events\n"
            "2. Review skill Lambda IAM role policy statements\n"
            "3. Verify resource ARN scoping is correct\n"
            "4. Confirm skill is accessing only allowed resources\n"
            "5. Check if Secrets Manager secret exists for user_id"
        ),
        category="Infrastructure",
    )

    DYNAMODB_WRITE_FAILED = ErrorCodeDefinition(
        code="LATEOS-008",
        message="DynamoDB write operation failed",
        http_status=500,
        investigation_steps=(
            "1. Check DynamoDB table status (ACTIVE vs UPDATING)\n"
            "2. Verify Lambda has dynamodb:PutItem permission\n"
            "3. Review CloudWatch metrics for throttling\n"
            "4. Check if partition key (user_id) is valid\n"
            "5. Verify KMS key permissions for encryption"
        ),
        category="Infrastructure",
    )

    BEDROCK_GUARDRAILS_INTERVENTION = ErrorCodeDefinition(
        code="LATEOS-009",
        message="Bedrock Guardrails blocked harmful content",
        http_status=400,
        investigation_steps=(
            "1. Review Guardrails assessment in response payload\n"
            "2. Check intervention reason (PII, profanity, harmful content)\n"
            "3. Verify Guardrails policy configuration\n"
            "4. If false positive, adjust Guardrails sensitivity\n"
            "5. Log to audit table for compliance review"
        ),
        category="Security",
    )

    RATE_LIMIT_EXCEEDED = ErrorCodeDefinition(
        code="LATEOS-010",
        message="Rate limit exceeded",
        http_status=429,
        investigation_steps=(
            "1. Check Lambda reserved concurrency settings\n"
            "2. Review API Gateway throttling limits\n"
            "3. Verify user_id request rate in CloudWatch\n"
            "4. Check if DDoS attack or legitimate spike\n"
            "5. Consider increasing concurrency if legitimate"
        ),
        category="Infrastructure",
    )

    DOMAIN_WHITELIST_REJECTION = ErrorCodeDefinition(
        code="LATEOS-011",
        message="Domain rejected by whitelist (web fetch skill)",
        http_status=403,
        investigation_steps=(
            "1. Review requested domain in web_fetch_skill logs\n"
            "2. Check DEFAULT_ALLOWED_DOMAINS in web_fetch_skill.py\n"
            "3. Verify domain is not on blocklist\n"
            "4. If legitimate, add domain to whitelist in config\n"
            "5. Document business justification for new domain"
        ),
        category="Security",
    )

    S3_USER_ISOLATION_VIOLATION = ErrorCodeDefinition(
        code="LATEOS-012",
        message="S3 per-user isolation policy violation",
        http_status=403,
        investigation_steps=(
            "1. Check file path for directory traversal attempts (..)\n"
            "2. Verify S3 prefix matches lateos/{env}/files/{user_id}/\n"
            "3. Review file_ops_skill IAM policy conditions\n"
            "4. Check CloudTrail for unauthorized S3 access attempts\n"
            "5. Confirm user_id in request matches authenticated user"
        ),
        category="Security",
    )

    STEP_FUNCTIONS_TIMEOUT = ErrorCodeDefinition(
        code="LATEOS-013",
        message="Step Functions execution timeout",
        http_status=504,
        investigation_steps=(
            "1. Check Step Functions execution history in CloudWatch\n"
            "2. Identify which Lambda timed out (5 min Express limit)\n"
            "3. Review Lambda timeout settings (default 30s)\n"
            "4. Check if skill operation was too slow (e.g., large file)\n"
            "5. Consider async processing for long operations"
        ),
        category="Infrastructure",
    )

    KMS_DECRYPTION_FAILED = ErrorCodeDefinition(
        code="LATEOS-014",
        message="KMS decryption failed",
        http_status=500,
        investigation_steps=(
            "1. Verify Lambda has kms:Decrypt permission\n"
            "2. Check if KMS key is enabled (not disabled/deleted)\n"
            "3. Review KMS key policy for Lambda role access\n"
            "4. Check CloudTrail for KMS API errors\n"
            "5. Verify encryption context matches (if used)"
        ),
        category="Infrastructure",
    )

    OAUTH_TOKEN_REFRESH_FAILED = ErrorCodeDefinition(
        code="LATEOS-015",
        message="OAuth token refresh failed",
        http_status=401,
        investigation_steps=(
            "1. Check if refresh token is expired or revoked\n"
            "2. Verify OAuth credentials in Secrets Manager\n"
            "3. Review skill logs for OAuth provider error response\n"
            "4. Confirm redirect URIs match OAuth app config\n"
            "5. User may need to re-authorize (gmail/calendar skill)"
        ),
        category="Integration",
    )

    def to_response(self, details: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """
        Convert error code to Lambda response format.

        Args:
            details: Optional additional error details
            **kwargs: Additional fields to include in response

        Returns:
            Formatted error response dict
        """
        response = {
            "statusCode": self.value.http_status,
            "error_code": self.value.code,
            "error": self.value.message,
            "category": self.value.category,
        }

        if details:
            response["details"] = details

        response.update(kwargs)
        return response

    def log_structured(self, logger, **context) -> None:
        """
        Log error in structured format for CloudWatch Insights.

        Args:
            logger: AWS Lambda Powertools Logger instance
            **context: Additional context fields (user_id, request_id, etc.)
        """
        logger.error(
            self.value.message,
            extra={
                "error_code": self.value.code,
                "category": self.value.category,
                "http_status": self.value.http_status,
                **context,
            },
        )


class LateosError(Exception):
    """
    Base exception class for LATEOS errors.

    Usage:
        raise LateosError(ErrorCode.PROMPT_INJECTION_DETECTED, user_id="user-123")
    """

    def __init__(self, error_code: ErrorCode, details: Optional[Dict[str, Any]] = None, **context):
        self.error_code = error_code
        self.details = details or {}
        self.context = context
        super().__init__(error_code.value.message)

    def to_response(self) -> Dict[str, Any]:
        """Convert exception to Lambda response format"""
        return self.error_code.to_response(details=self.details, **self.context)


# CloudWatch Insights Query Examples
CLOUDWATCH_QUERIES = {
    "security_errors": """
        fields @timestamp, error_code, user_id, request_id
        | filter category = "Security"
        | sort @timestamp desc
        | limit 100
    """,
    "error_rate_by_code": """
        fields error_code
        | filter ispresent(error_code)
        | stats count() by error_code
        | sort count() desc
    """,
    "user_error_history": """
        fields @timestamp, error_code, error
        | filter user_id = "<USER_ID_HERE>"
        | sort @timestamp desc
        | limit 50
    """,
}
