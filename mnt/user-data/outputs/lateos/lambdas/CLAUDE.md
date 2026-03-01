# Lateos Lambdas — Claude Code Context

Read the root `CLAUDE.md` and `infrastructure/CLAUDE.md` first.
This file covers Lambda function standards and patterns.

---

## Lambda Powertools — Required on Every Function

Every Lambda handler must use AWS Lambda Powertools. No exceptions.

```python
# Standard imports for every Lambda handler
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import (
    APIGatewayProxyEvent,   # or the appropriate event type
)
from aws_lambda_powertools.utilities.validation import validate
from aws_lambda_powertools.utilities.idempotency import (
    idempotent,
    DynamoDBPersistenceLayer,
)

# Module-level initialization (runs once per cold start)
logger = Logger(service="skill-email")    # matches POWERTOOLS_SERVICE_NAME env var
tracer = Tracer(service="skill-email")
metrics = Metrics(namespace="Lateos", service="skill-email")

@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=False)  # never log raw events (may contain PII)
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: APIGatewayProxyEvent, context: LambdaContext) -> dict:
    ...
```

---

## Secret Fetching Pattern

Fetch secrets at module level for warm invocation caching.
Never fetch inside the handler on every invocation.

```python
import boto3
import json
import os
from functools import lru_cache

@lru_cache(maxsize=None)
def get_secret(secret_name: str) -> dict:
    """
    Fetch secret from Secrets Manager.
    Cached per Lambda instance lifetime.
    Secret name comes from environment variable — never hardcoded.
    """
    client = boto3.client(
        "secretsmanager",
        region_name=os.environ["AWS_REGION"],
    )
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response["SecretString"])
    except client.exceptions.ResourceNotFoundException:
        logger.error("Secret not found", secret_name=secret_name)
        raise
    except client.exceptions.AccessDeniedException:
        logger.error("Access denied to secret", secret_name=secret_name)
        raise

# Module-level — fetched once on cold start, cached on warm
_secrets = get_secret(os.environ["SECRET_NAME"])

def handler(event, context):
    # Use cached secret — no Secrets Manager call on warm invocations
    token = _secrets["bot_token"]
    ...
```

---

## Input Sanitization — Required Before Any LLM Call

Every Lambda that passes user content to Bedrock must sanitize first.
Never pass raw user input to the LLM.

```python
# lambdas/shared/sanitizer.py
import re
from typing import Optional

# Known prompt injection patterns — add new ones as discovered
# Based on OWASP LLM Top 10 and documented Moltbot attack vectors
INJECTION_PATTERNS = [
    r"ignore\s+(previous|prior|above|all)\s+instructions?",
    r"you\s+are\s+now\s+(in\s+)?(developer|admin|god|jailbreak)\s+mode",
    r"repeat\s+(your\s+)?(system\s+)?prompt",
    r"(reveal|show|print|output|display)\s+(your\s+)?(system\s+)?prompt",
    r"act\s+as\s+(if\s+you\s+(are|were)\s+)?(?!a\s+helpful)",
    r"pretend\s+(you\s+are|to\s+be)\s+(?!helping)",
    r"from\s+now\s+on\s+(you\s+are|you\s+will|ignore)",
    r"disregard\s+(your\s+)?(previous|prior|safety|ethical)",
    r"(sudo|root|admin)\s*:",
    r"<\s*script[^>]*>",                # XSS attempt
    r"javascript\s*:",                   # JavaScript injection
    r"(exec|eval|system|subprocess)\s*\(",  # Code execution attempt
    r"\{\{.*\}\}",                       # Template injection
    r"<!--.*-->",                        # HTML comment injection
]

MAX_INPUT_LENGTH = 4096  # characters — never process beyond this

def sanitize_user_input(
    text: str,
    allow_code: bool = False,
    context: Optional[str] = None,
) -> tuple[str, list[str]]:
    """
    Sanitize user input before passing to LLM.

    Returns:
        Tuple of (sanitized_text, list_of_detected_issues)
        If issues are detected, caller decides whether to reject or flag.

    Never raises — always returns something.
    """
    if not text:
        return "", []

    issues = []

    # Truncate excessive length
    if len(text) > MAX_INPUT_LENGTH:
        text = text[:MAX_INPUT_LENGTH]
        issues.append(f"INPUT_TRUNCATED_AT_{MAX_INPUT_LENGTH}")

    # Check for injection patterns
    text_lower = text.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE | re.DOTALL):
            issues.append(f"INJECTION_PATTERN_DETECTED: {pattern[:50]}")

    # Remove null bytes and control characters
    text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", text)

    # Normalize Unicode (prevent homoglyph attacks)
    import unicodedata
    text = unicodedata.normalize("NFKC", text)

    return text, issues


def is_safe_for_llm(text: str) -> bool:
    """Quick check — use in high-throughput paths."""
    _, issues = sanitize_user_input(text)
    return len(issues) == 0
```

---

## Bedrock Invocation Pattern

```python
# lambdas/shared/bedrock_client.py
import boto3
import os
from typing import Optional
from aws_lambda_powertools import Logger

logger = Logger()

MAX_INPUT_TOKENS = 4096   # never exceed — cost and injection protection
MAX_OUTPUT_TOKENS = 1024  # always set — prevent runaway generation

bedrock = boto3.client(
    "bedrock-runtime",
    region_name=os.environ.get("AWS_REGION", "us-east-1"),
)

def invoke_bedrock(
    system_prompt: str,
    user_message: str,
    model_id: Optional[str] = None,
    max_tokens: int = MAX_OUTPUT_TOKENS,
) -> str:
    """
    Invoke Bedrock with consistent safety settings.
    Always uses Bedrock Guardrails.
    Never exposes raw API errors to users.
    """
    if len(user_message) > MAX_INPUT_TOKENS:
        raise ValueError(f"Input exceeds maximum token limit of {MAX_INPUT_TOKENS}")

    model = model_id or os.environ.get(
        "BEDROCK_MODEL_ID",
        "anthropic.claude-3-sonnet-20240229-v1:0"
    )

    guardrail_id = os.environ.get("BEDROCK_GUARDRAIL_ID")
    guardrail_version = os.environ.get("BEDROCK_GUARDRAIL_VERSION", "DRAFT")

    request_params = {
        "modelId": model,
        "messages": [{"role": "user", "content": user_message}],
        "system": [{"text": system_prompt}],
        "inferenceConfig": {
            "maxTokens": max_tokens,
            "temperature": 0.1,    # low temperature for predictable behavior
            "topP": 0.9,
        },
    }

    # Always apply guardrails if configured
    if guardrail_id:
        request_params["guardrailConfig"] = {
            "guardrailIdentifier": guardrail_id,
            "guardrailVersion": guardrail_version,
            "trace": "ENABLED",
        }

    try:
        response = bedrock.converse(**request_params)

        # Check if guardrail blocked the response
        if response.get("stopReason") == "guardrail_intervened":
            logger.warning("Bedrock guardrail intervened",
                           user_id=logger.get_correlation_id())
            return "I'm unable to process that request."

        return response["output"]["message"]["content"][0]["text"]

    except bedrock.exceptions.ThrottlingException:
        logger.warning("Bedrock throttling — retrying")
        raise  # Step Functions handles retry
    except Exception as e:
        # Never expose raw Bedrock errors to users
        logger.error("Bedrock invocation failed", error=str(e))
        raise RuntimeError("Unable to process request") from e
```

---

## Structured Logging — Required Pattern

Never use `print()`. Always use Powertools Logger with structured fields.
Never log secrets, tokens, passwords, or PII.

```python
# CORRECT
logger.info("Skill executed successfully",
    user_id=user_id,           # OK — internal identifier
    skill_name="email",
    action="read",
    duration_ms=elapsed,
)

logger.error("Authentication failed",
    user_id=user_id,
    reason="token_expired",
    # NEVER: token=token, password=password, api_key=key
)

# WRONG
print(f"Processing request for {user_id} with token {token}")  # ← never
logger.info(f"Secret value: {secret_value}")                    # ← never
```

---

## Error Handling Pattern

```python
from aws_lambda_powertools.utilities.typing import LambdaContext

class LateosError(Exception):
    """Base exception — safe to surface to users."""
    pass

class AuthenticationError(LateosError):
    status_code = 401
    user_message = "Authentication required."

class RateLimitError(LateosError):
    status_code = 429
    user_message = "Too many requests. Please wait a moment."

class SkillExecutionError(LateosError):
    status_code = 500
    user_message = "Unable to complete that action right now."


def safe_handler(func):
    """
    Decorator that ensures handlers always return valid responses
    and never leak internal error details to users.
    """
    def wrapper(event, context: LambdaContext):
        try:
            return func(event, context)
        except LateosError as e:
            logger.warning("Known error", error_type=type(e).__name__)
            return {
                "statusCode": e.status_code,
                "body": json.dumps({"message": e.user_message}),
            }
        except Exception as e:
            # Unknown error — log with full detail, return generic message
            logger.exception("Unexpected error", error=str(e))
            metrics.add_metric("UnexpectedErrors", MetricUnit.Count, 1)
            return {
                "statusCode": 500,
                "body": json.dumps({"message": "An unexpected error occurred."}),
                # NEVER return str(e) here — may contain sensitive info
            }
    return wrapper
```

---

## Handler Template

Use this as the starting template for every new Lambda handler:

```python
"""
{skill_name} Lambda Handler
---------------------------
Purpose: {one line description}
Trigger: {API Gateway / Step Functions / EventBridge / SNS}
IAM Role: {role name from CDK}
Secrets: {secret names this function uses}
"""
import json
import os
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext

from shared.sanitizer import sanitize_user_input
from shared.bedrock_client import invoke_bedrock
from shared.secrets import get_secret
from shared.errors import safe_handler, LateosError

logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="Lateos")

# Module-level secret fetch — cached for warm invocations
_config = get_secret(os.environ["SECRET_NAME"])


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=False)
@metrics.log_metrics(capture_cold_start_metric=True)
@safe_handler
def handler(event: dict, context: LambdaContext) -> dict:
    """
    {Description of what this handler does}

    Args:
        event: {describe the expected event structure}
        context: Lambda context

    Returns:
        dict with statusCode and body
    """
    # 1. Extract and validate input
    user_id = event.get("user_id")
    if not user_id:
        raise LateosError("user_id required")

    user_input = event.get("message", "")

    # 2. Sanitize before any processing
    clean_input, issues = sanitize_user_input(user_input)
    if issues:
        logger.warning("Input issues detected",
            user_id=user_id,
            issue_count=len(issues),
            # Log issue types but not the actual content that triggered them
        )
        # Decide whether to reject or proceed with sanitized input
        # based on severity of issues

    # 3. Business logic here
    # ...

    # 4. Return structured response
    metrics.add_metric("RequestsProcessed", MetricUnit.Count, 1)
    return {
        "statusCode": 200,
        "body": json.dumps({"status": "ok"}),
    }
```

---

## Banned Patterns in Lambda Code

Claude Code must flag these as errors and refuse to generate them:

```python
# BANNED — shell execution
import os
os.system("...")           # ← BANNED
os.popen("...")            # ← BANNED
import subprocess
subprocess.run(...)        # ← BANNED
subprocess.Popen(...)     # ← BANNED

# BANNED — dynamic code execution
eval("...")                # ← BANNED
exec("...")                # ← BANNED
compile("...")             # ← BANNED
__import__("...")          # ← BANNED

# BANNED — plaintext secret handling
os.environ["BOT_TOKEN"]   # ← BANNED (use Secrets Manager)
open(".env").read()        # ← BANNED

# BANNED — unscoped DynamoDB access patterns
table.scan()               # ← BANNED (exposes cross-user data)
table.scan(FilterExpression=...) # ← BANNED (still scans all data)

# CORRECT DynamoDB pattern — always query with user_id partition key
table.query(
    KeyConditionExpression=Key("user_id").eq(user_id)
)
```

---

*Update this file when adding new shared utilities or establishing new patterns.*
