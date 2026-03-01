# Walkthrough 04: Secret Redaction

**How RULE 8 works: No plaintext logging of tokens, passwords, API keys, or PII**

This walkthrough shows the exact code path when a skill Lambda returns a response containing sensitive data, how the output sanitizer detects and redacts it, and what gets logged.

---

## Scenario

A user requests to read their Gmail OAuth token configuration (hypothetical debug command).

**User Request:**

```
"Show me my Gmail connection details"
```

**Email Skill Response (CONTAINS SECRETS):**

```json
{
  "status": "connected",
  "provider": "gmail",
  "email": "user@example.com",
  "oauth_token": "ya29.a0AfH6SMBx7K...",
  "refresh_token": "1//0gZ1xYz...",
  "token_expiry": "2026-03-01T15:30:00Z",
  "api_key": "AIzaSyD-9tVz..."
}
```

**This response violates RULE 8** — it contains plaintext OAuth tokens and API keys that must NOT be logged or returned to the user.

---

## Request Flow

```
User → API Gateway → Orchestrator → Validator → Intent Classifier →
Action Router → Email Skill [returns secrets] → Output Sanitizer [REDACTS HERE] → Response
```

---

## Step 1: Email Skill Returns Sensitive Data

**File:** `lambdas/skills/email_skill.py`
**Function:** `get_connection_details()` (hypothetical debug function)

**Output:**

```json
{
  "statusCode": 200,
  "body": {
    "result": {
      "status": "connected",
      "provider": "gmail",
      "email": "user@example.com",
      "oauth_token": "ya29.a0AfH6SMBx7K1jZ3cV8bN2mQ4rT6sW9eL5kD8pF3vX0yH7iC2aU4wB6nG9tR1sL0",
      "refresh_token": "1//0gZ1xYz3cV8bN2mQ4rT6sW9eL5kD8pF3vX0yH7iC2aU4wB6nG9tR1sL0",
      "token_expiry": "2026-03-01T15:30:00Z",
      "api_key": "AIzaSyD-9tVz3cV8bN2mQ4rT6sW9eL5kD8pF3vX0"
    },
    "skill": "email",
    "action": "get_connection_details"
  }
}
```

**CloudWatch Log:** `/aws/lambda/lateos-skill-email`

```json
{
  "timestamp": "2026-03-01T14:45:12.123Z",
  "level": "INFO",
  "service": "email_skill",
  "user_id": "user-abc123",
  "action": "get_connection_details",
  "message": "Retrieved Gmail connection details for user user-abc123"
}
```

**Note:** The skill Lambda logs the action but NOT the token values (good practice).

---

## Step 2: Output Sanitizer Receives Sensitive Data

**File:** `lambdas/core/output_sanitizer.py`
**Handler:** Line 224

**Input Event:**

```json
{
  "request_id": "xyz-789",
  "result": {
    "status": "connected",
    "provider": "gmail",
    "email": "user@example.com",
    "oauth_token": "ya29.a0AfH6SMBx7K1jZ3cV8bN2mQ4rT6sW9eL5kD8pF3vX0yH7iC2aU4wB6nG9tR1sL0",
    "refresh_token": "1//0gZ1xYz3cV8bN2mQ4rT6sW9eL5kD8pF3vX0yH7iC2aU4wB6nG9tR1sL0",
    "token_expiry": "2026-03-01T15:30:00Z",
    "api_key": "AIzaSyD-9tVz3cV8bN2mQ4rT6sW9eL5kD8pF3vX0"
  }
}
```

---

## Step 3: Sanitize Dictionary (Recursive Scan)

**Function:** `sanitize_dict(action_result)` at line 93

**Code Path:**

### 3.1: Check for Sensitive Keys (Line 110-112)

```python
sensitive_keys = ["password", "token", "secret", "api_key", "private_key"]
if any(sk in key.lower() for sk in sensitive_keys):
    sanitized[key] = "***REDACTED***"
```

**Keys Scanned:**

- `"status"` → No match, keep value
- `"provider"` → No match, keep value
- `"email"` → No match, keep value
- `"oauth_token"` → **MATCH** ("token" in key) → Redact to `"***REDACTED***"`
- `"refresh_token"` → **MATCH** ("token" in key) → Redact to `"***REDACTED***"`
- `"token_expiry"` → **MATCH** ("token" in key) → Redact to `"***REDACTED***"`
- `"api_key"` → **MATCH** ("api_key" in key) → Redact to `"***REDACTED***"`

**After Key-Based Redaction:**

```json
{
  "status": "connected",
  "provider": "gmail",
  "email": "user@example.com",
  "oauth_token": "***REDACTED***",
  "refresh_token": "***REDACTED***",
  "token_expiry": "***REDACTED***",
  "api_key": "***REDACTED***"
}
```

### 3.2: Sanitize String Values (Line 127-128)

Even if key name doesn't match, string values are scanned for secret patterns.

**Function:** `sanitize_text(value)` at line 75

**Code Path:**

**Patterns Applied (lines 45-72):**

#### Pattern 1: Long alphanumeric tokens (Line 47)

```python
(r"\b[A-Za-z0-9]{32,}\b", "***REDACTED_TOKEN***")
```

**Purpose:** Catch API keys, access tokens without specific key names

**Example Match:**

```
"ya29.a0AfH6SMBx7K1jZ3cV8bN2mQ4rT6sW9eL5kD8pF3vX0yH7iC2aU4wB6nG9tR1sL0"
→ 72 characters of alphanumeric → MATCH
→ "***REDACTED_TOKEN***"
```

#### Pattern 2: API key patterns (Line 48)

```python
(r'api[_-]?key["\']?\s*[:=]\s*["\']?([A-Za-z0-9_\-]+)', "api_key: ***REDACTED***")
```

**Example Match:**

```
"api_key": "AIzaSyD-9tVz..."
→ MATCH
→ "api_key: ***REDACTED***"
```

#### Pattern 3: Token patterns (Line 49)

```python
(r'token["\']?\s*[:=]\s*["\']?([A-Za-z0-9_\-\.]+)', "token: ***REDACTED***")
```

**Example Match:**

```
"oauth_token": "ya29..."
→ MATCH
→ "token: ***REDACTED***"
```

#### Pattern 4: AWS credentials (Line 51-52)

```python
(r"AKIA[0-9A-Z]{16}", "***REDACTED_AWS_KEY***")
```

**No match in this response** (Gmail tokens, not AWS)

#### Pattern 5: Private keys (Line 57-60)

```python
(r"-----BEGIN [A-Z ]+PRIVATE KEY-----[\s\S]+?-----END [A-Z ]+PRIVATE KEY-----",
 "***REDACTED_PRIVATE_KEY***")
```

**No match in this response**

#### Pattern 6: Email addresses (Line 62-63, COMMENTED OUT)

```python
# (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '***@***.***'),
```

**Intentionally disabled** — email addresses may be legitimate user data to display.

**Decision:** Only redact if in sensitive context (like "admin_email": "...")

### 3.3: Apply All Patterns (Line 87-88)

```python
for pattern, replacement in REDACTION_PATTERNS:
    sanitized = re.sub(pattern, replacement, sanitized)
```

**Even though keys were already redacted to `"***REDACTED***"`, the string patterns provide defense-in-depth.**

---

## Step 4: Final Sanitized Result

**After `sanitize_dict()` completes (line 248):**

```json
{
  "status": "connected",
  "provider": "gmail",
  "email": "user@example.com",
  "oauth_token": "***REDACTED***",
  "refresh_token": "***REDACTED***",
  "token_expiry": "***REDACTED***",
  "api_key": "***REDACTED***"
}
```

**CloudWatch Log:** `/aws/lambda/lateos-dev-output-sanitizer`

```json
{
  "timestamp": "2026-03-01T14:45:12.456Z",
  "level": "INFO",
  "service": "output-sanitizer",
  "request_id": "xyz-789",
  "has_result": true,
  "message": "Sanitizing output"
}
```

**Note:** Even the log does NOT contain the redacted values — only metadata.

---

## Step 5: Bedrock Guardrails Check (Phase 3)

**Function:** `apply_guardrails(final_output)` at line 135

**Input:** JSON stringified sanitized result

```json
"{\"status\": \"connected\", \"provider\": \"gmail\", \"email\": \"user@example.com\", \"oauth_token\": \"***REDACTED***\", \"refresh_token\": \"***REDACTED***\", \"token_expiry\": \"***REDACTED***\", \"api_key\": \"***REDACTED***\"}"
```

**Code Path:**

### 5.1: Check Bedrock Availability (Line 148-150)

```python
if not BEDROCK_AVAILABLE or not bedrock_runtime:
    logger.info("Bedrock Guardrails not available, skipping (LocalStack mode)")
    return {"allowed": True, "reason": "guardrails_disabled"}
```

**In LocalStack:** Bedrock not available → returns `{"allowed": True, "reason": "guardrails_disabled"}`

**In Real AWS (Phase 3):**

### 5.2: Check Guardrails Configuration (Line 152-154)

```python
if not GUARDRAILS_ID:
    logger.warning("GUARDRAILS_ID not configured, skipping Guardrails check")
    return {"allowed": True, "reason": "guardrails_not_configured"}
```

**Environment Variable:** `GUARDRAILS_ID` (set in `orchestration_stack.py:359`)

**If configured, proceed to API call:**

### 5.3: Invoke Bedrock Guardrails (Line 157-162)

```python
response = bedrock_runtime.apply_guardrail(
    guardrailIdentifier=GUARDRAILS_ID,
    guardrailVersion=GUARDRAILS_VERSION,
    source="OUTPUT",
    content=[{"text": {"text": text}}],
)
```

**Guardrails Checks:**

- **Topic Policy:** Blocked topics (e.g., violence, illegal activity)
- **Content Policy:** Harmful content filters (hate speech, sexual content)
- **Word Policy:** Profanity filters
- **Sensitive Information Policy:** PII detection (SSN, credit cards, **API keys**)

**Response:**

```json
{
  "action": "GUARDRAIL_INTERVENED",
  "assessments": [
    {
      "sensitiveInformationPolicy": {
        "piiEntities": [
          {
            "type": "API_KEY",
            "action": "BLOCKED",
            "match": "***REDACTED***"
          }
        ]
      }
    }
  ]
}
```

**Wait — Guardrails detects `"***REDACTED***"` as suspicious?**

**No.** Guardrails only flags **actual secrets**. Since we already redacted them, Guardrails sees only the placeholder text.

**Actual Response (if tokens were NOT redacted):**

```json
{
  "action": "GUARDRAIL_INTERVENED",
  "assessments": [
    {
      "sensitiveInformationPolicy": {
        "piiEntities": [
          {
            "type": "ACCESS_KEY",
            "action": "BLOCKED",
            "match": "ya29.a0AfH6SMBx7K..."
          }
        ]
      }
    }
  ]
}
```

**Defense in Depth:** Even if `sanitize_dict()` missed a secret, Bedrock Guardrails would catch it.

### 5.4: Guardrails Passed (Already Redacted)

**Code Path:** Line 202-203

```python
logger.info("Guardrails check passed", extra={"action": action})
return {"allowed": True, "reason": "passed"}
```

**CloudWatch Log:**

```json
{
  "timestamp": "2026-03-01T14:45:12.789Z",
  "level": "INFO",
  "service": "output-sanitizer",
  "request_id": "xyz-789",
  "action": "NONE",
  "guardrails_reason": "passed",
  "message": "Guardrails check passed"
}
```

---

## Step 6: Return Sanitized Output

**Handler Return (Line 291-296):**

```json
{
  "statusCode": 200,
  "sanitized_result": {
    "status": "connected",
    "provider": "gmail",
    "email": "user@example.com",
    "oauth_token": "***REDACTED***",
    "refresh_token": "***REDACTED***",
    "token_expiry": "***REDACTED***",
    "api_key": "***REDACTED***"
  },
  "request_id": "xyz-789",
  "guardrails_passed": true
}
```

**CloudWatch Log:**

```json
{
  "timestamp": "2026-03-01T14:45:13.012Z",
  "level": "INFO",
  "service": "output-sanitizer",
  "request_id": "xyz-789",
  "output_size": 142,
  "guardrails_reason": "passed",
  "message": "Output sanitized and Guardrails passed"
}
```

---

## Step 7: User Receives Safe Response

**API Gateway Response:**

```json
{
  "statusCode": 200,
  "body": {
    "response_text": "Gmail connection details:\n- Status: connected\n- Email: user@example.com\n- OAuth token: ***REDACTED***\n- Refresh token: ***REDACTED***\n- API key: ***REDACTED***",
    "success": true,
    "request_id": "xyz-789"
  }
}
```

**User sees:**

```
Gmail connection details:
- Status: connected
- Email: user@example.com
- OAuth token: ***REDACTED***
- Refresh token: ***REDACTED***
- API key: ***REDACTED***
```

**No secrets leaked.**

---

## Error Code Logging

**If secrets were detected and redacted:**

**CloudWatch Log with Error Code:**

```json
{
  "timestamp": "2026-03-01T14:45:12.456Z",
  "level": "WARNING",
  "service": "output-sanitizer",
  "error_code": "LATEOS-006",
  "category": "Security",
  "request_id": "xyz-789",
  "redaction_count": 4,
  "redacted_keys": ["oauth_token", "refresh_token", "token_expiry", "api_key"],
  "message": "Secret redaction applied to output"
}
```

**Error Code Reference:** `lambdas/shared/error_codes.py:109-121`

```python
SECRET_REDACTION_APPLIED = ErrorCodeDefinition(
    code="LATEOS-006",
    message="Secret redaction applied to output",
    http_status=200,  # Not an error — informational
    investigation_steps=(
        "1. Review output_sanitizer logs for redacted content\n"
        "2. Check REDACTION_PATTERNS in output_sanitizer.py\n"
        "3. Verify no secrets leaked in final response\n"
        "4. If over-redacting, adjust regex patterns\n"
        "NOTE: This is informational, not an error"
    ),
    category="Security",
)
```

---

## What Secrets Are Redacted

### By Key Name (Line 110-112)

**Sensitive Keys:**

- `password`
- `token` (oauth_token, access_token, refresh_token, bearer_token, etc.)
- `secret` (client_secret, api_secret, secret_key, etc.)
- `api_key` (api_key, apiKey, apikey, etc.)
- `private_key` (private_key, privateKey, ssh_key, etc.)

**Redaction:** Entire value replaced with `"***REDACTED***"`

### By Pattern Matching (Lines 45-72)

**Pattern-Based Detection:**

1. **Long alphanumeric strings (32+ chars):** `r"\b[A-Za-z0-9]{32,}\b"`
   - Example: API keys, OAuth tokens, session IDs

2. **API key assignments:** `r'api[_-]?key["\']?\s*[:=]\s*["\']?([A-Za-z0-9_\-]+)'`
   - Example: `api_key: "abc123xyz"`

3. **Token assignments:** `r'token["\']?\s*[:=]\s*["\']?([A-Za-z0-9_\-\.]+)'`
   - Example: `token: "ya29.abc..."`

4. **AWS access keys:** `r"AKIA[0-9A-Z]{16}"`
   - Example: `AKIAIOSFODNN7EXAMPLE`

5. **AWS secret keys:** `r'aws_secret_access_key["\']?\s*[:=]\s*["\']?([A-Za-z0-9/+=]+)'`
   - Example: `aws_secret_access_key: "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"`

6. **Private keys (PEM format):**
   - Example: `-----BEGIN RSA PRIVATE KEY-----\nMIIE...`

7. **Internal IP addresses:**
   - `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`

8. **File paths:**
   - `/home/user/...`, `C:\Users\...`

9. **Stack traces with paths:**
   - `File "/var/task/lambda_function.py"`

---

## What Is NOT Redacted

**Email Addresses (Line 62-63 — Commented Out):**

```python
# (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '***@***.***'),
```

**Reason:** Email addresses are often legitimate user data to display (e.g., "Send email to <user@example.com>").

**If PII protection is required:** Enable Bedrock Guardrails Sensitive Information Policy to detect and redact email addresses.

**Phone Numbers:** Not currently redacted by pattern matching.

**Solution:** Bedrock Guardrails detects phone numbers as PII.

**Credit Card Numbers:** Not currently redacted by pattern matching.

**Solution:** Bedrock Guardrails detects credit card numbers (PCI-DSS compliance).

---

## What Could Go Wrong

### 1. New Secret Format Not Detected

**Scenario:** Third-party API introduces new token format not in patterns

**Example:**

```json
{
  "twilio_auth": "SK1234567890abcdef1234567890abcd"
}
```

**Pattern Match Attempt:**

- Line 47: `r"\b[A-Za-z0-9]{32,}\b"` → **MATCH** (32 characters) → Redacted to `"***REDACTED_TOKEN***"`

**Result:** Caught by length-based pattern

**If token is shorter (e.g., 20 chars):**

- Not caught by length pattern
- Key name doesn't contain "token" or "secret"
- **LEAKED**

**Fix:**

```python
# Add Twilio-specific pattern
(r"SK[0-9a-fA-F]{32}", "***REDACTED_TWILIO_KEY***"),
```

### 2. Secrets in Nested Objects

**Scenario:** Secret deeply nested in response

**Example:**

```json
{
  "user": {
    "profile": {
      "integrations": {
        "slack": {
          "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX"
        }
      }
    }
  }
}
```

**Sanitization:**

- Line 114-115: `sanitize_dict()` is recursive
- Traverses all nested dicts
- Line 127-128: Applies `sanitize_text()` to all string values
- Webhook URL contains long alphanumeric token → **REDACTED**

**Result:** Caught by recursive scanning

### 3. Secrets in Lists

**Scenario:** Array of tokens

**Example:**

```json
{
  "active_sessions": [
    "session_abc123xyz789",
    "session_def456uvw012"
  ]
}
```

**Sanitization:**

- Line 117-125: Lists are iterated
- Line 122: Each string item passed through `sanitize_text()`
- If key name is "active_sessions", not flagged
- If strings are long (32+ chars), **REDACTED** by pattern

**Result:** Caught by pattern matching

### 4. Base64-Encoded Secrets

**Scenario:** Token encoded in Base64

**Example:**

```json
{
  "credentials": "eWEyOS5hMEFmSDZTTUJ4N0sxalozcFY4Yk4ybVE0clQ2c1c5ZUw1a0Q4cEYzdlgweUg3aUMyYVU0d0I2bkc5dFIxc0ww"
}
```

**Pattern Match:**

- Key name "credentials" doesn't contain "password", "token", "secret", "api_key", or "private_key"
- Base64 string is 96+ characters → matches `r"\b[A-Za-z0-9]{32,}\b"`
- **REDACTED**

**Result:** Caught by length pattern

**But:** If attacker uses shorter encoding or splits across multiple fields, may evade.

**Better Defense:** Bedrock Guardrails uses ML-based detection, not just regex.

---

## Defense in Depth

**Layer 1:** Key-based redaction (line 110-112)

- Fast, catches obvious secret key names

**Layer 2:** Pattern-based redaction (line 87-88)

- Catches secrets with non-obvious key names or embedded in text

**Layer 3:** Bedrock Guardrails (line 135-219)

- ML-based PII and secret detection
- Catches novel formats and encoded secrets

**Layer 4:** Structured logging (Lambda Powertools)

- Logs are JSON-formatted
- Secrets are never in log message text (only metadata fields)

**Layer 5:** CloudWatch Logs encryption

- All logs encrypted at rest with KMS
- Secrets that somehow reach logs are encrypted

---

## Testing Secret Redaction

**Unit Test:** `tests/unit/test_output_sanitizer.py`

```python
def test_secret_redaction_applied():
    """Test that secrets in output are redacted."""
    from lambdas.core.output_sanitizer import sanitize_dict

    input_data = {
        "oauth_token": "ya29.a0AfH6SMBx7K1jZ3cV8bN2mQ4rT6sW9eL5kD8pF3vX0",
        "api_key": "AIzaSyD-9tVz3cV8bN2mQ4rT6sW9eL5kD8pF3vX0",
        "message": "Hello world"
    }

    result = sanitize_dict(input_data)

    assert result["oauth_token"] == "***REDACTED***"
    assert result["api_key"] == "***REDACTED***"
    assert result["message"] == "Hello world"  # Non-secret unchanged
```

**Integration Test:** `tests/integration/test_secret_leakage.py`

```python
def test_no_secrets_in_api_response():
    """Test that API responses never contain actual secrets."""
    import requests

    response = requests.post(
        f"{API_ENDPOINT}/agent",
        headers={"Authorization": f"Bearer {jwt_token}"},
        json={"input": "Show my Gmail token"}
    )

    body = response.json()
    assert "ya29" not in str(body)  # OAuth token prefix
    assert "AKIA" not in str(body)  # AWS access key prefix
    assert "***REDACTED***" in str(body)  # Redaction applied
```

---

## Debugging Redaction Issues

**Scenario:** Legitimate data is being over-redacted

**Example:**

```
User message: "My employee ID is ABC123XYZ456 (32 characters)"
```

**Redacted to:**

```
"My employee ID is ***REDACTED_TOKEN***"
```

**Investigation:**

```bash
# Check which pattern matched
aws logs filter-log-events \
  --log-group-name /aws/lambda/lateos-dev-output-sanitizer \
  --filter-pattern '"redaction_count"' \
  --query 'events[*].message' | jq -r '.[] | fromjson | select(.redaction_count > 0)'
```

**Fix:**

- Adjust pattern threshold (e.g., require 40+ chars instead of 32+)
- OR: Add context detection (only redact if key name suggests it's a secret)

```python
# More conservative pattern
(r"\b[A-Za-z0-9]{40,}\b", "***REDACTED_TOKEN***")  # Increase from 32 to 40
```

---

**Next Walkthrough:** [05-new-skill-execution.md](05-new-skill-execution.md) — End-to-end email skill trace with IAM scoping
