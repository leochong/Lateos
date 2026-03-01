# Walkthrough 01: User Sends Message

**Complete request trace from user input to response**

This walkthrough shows the exact code path, JSON payloads, and CloudWatch logs for a normal user request through the Lateos pipeline.

---

## Request Flow Overview

```
User → API Gateway → Cognito Auth → Orchestrator Lambda →
Validator Lambda → Intent Classifier Lambda → Action Router Lambda →
Skill Lambda → Output Sanitizer Lambda → Response
```

---

## Step 1: User Sends POST Request

**Endpoint:** `POST https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/agent`

**Headers:**

```http
Authorization: Bearer {cognito_jwt_token}
Content-Type: application/json
```

**Request Body:**

```json
{
  "input": "Send an email to john@example.com saying hello"
}
```

**CloudWatch Log:** API Gateway Access Logs

```json
{
  "requestId": "abc123-def456",
  "ip": "203.0.113.42",
  "requestTime": "2026-03-01T10:15:32Z",
  "httpMethod": "POST",
  "resourcePath": "/agent",
  "status": 200
}
```

---

## Step 2: Cognito Authorizer Validation

**Location:** API Gateway Authorizer (configured in `infrastructure/stacks/core_stack.py:131-137`)

**What Happens:**

- Cognito verifies JWT signature
- Checks token expiration (`exp` claim)
- Extracts user claims: `sub`, `email`, `cognito:username`
- Adds claims to `event.requestContext.authorizer.claims`

**If Auth Fails:**

- HTTP 401 Unauthorized
- Error code: `LATEOS-002` (Cognito token validation failed)
- CloudWatch log in API Gateway authorizer logs

**Auth Success - Claims Added:**

```json
{
  "claims": {
    "sub": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
    "email": "user@example.com",
    "cognito:username": "user123"
  }
}
```

---

## Step 3: Orchestrator Lambda Invocation

**File:** `lambdas/core/orchestrator.py`
**Handler:** `orchestrator.handler` (line 36)

**Input Event:**

```json
{
  "body": "{\"input\": \"Send an email to john@example.com saying hello\"}",
  "requestContext": {
    "authorizer": {
      "claims": {
        "sub": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
        "email": "user@example.com",
        "cognito:username": "user123"
      }
    }
  }
}
```

**Code Path:**

- Line 49: Parse request body: `body = json.loads(event.get("body", "{}"))`
- Line 50: Extract user input: `user_input = body.get("input", "")`
- Line 53-60: Extract user context from Cognito claims
- Line 63: Generate request ID: `request_id = str(uuid.uuid4())`

**User Context Created:**

```json
{
  "user_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
  "email": "user@example.com",
  "username": "user123"
}
```

**CloudWatch Log:** `/aws/lambda/lateos-dev-orchestrator`

```json
{
  "timestamp": "2026-03-01T10:15:32.123Z",
  "level": "INFO",
  "service": "orchestrator",
  "request_id": "xyz-789",
  "user_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
  "input_length": 44,
  "message": "Orchestrating request"
}
```

**Output (Phase 2 placeholder):**

```json
{
  "statusCode": 200,
  "headers": {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*"
  },
  "body": "{\"response_text\": \"Lateos received your request...\", \"success\": true, \"request_id\": \"xyz-789\"}"
}
```

---

## Step 4: Validator Lambda (Step Functions - Phase 3)

**File:** `lambdas/core/validator.py`
**Handler:** `validator.handler` (line 181)

**Note:** In Phase 2, orchestrator returns directly. In Phase 3+, Step Functions invokes validator.

**Input Event (from Step Functions):**

```json
{
  "input": "Send an email to john@example.com saying hello",
  "request_id": "xyz-789"
}
```

**Code Path:**

- Line 196: Extract user input: `user_input = event.get("input", "")`
- Line 207: Sanitize input: `sanitized_input = sanitize_input(user_input)` (line 93)
  - Line 104: Remove null bytes
  - Line 107: Remove control characters
  - Line 110: Normalize whitespace
  - Line 114-120: Remove encoding bypass attempts (hex, HTML entities, URL encoding)
- Line 211: Validate length: `validate_length(sanitized_input)` (line 125)
  - Check >= 1 character (line 135)
  - Check <= 4000 characters (line 138)
- Line 224: Validate format: `validate_format(sanitized_input)` (line 142)
  - Line 153-158: Check special character ratio < 50%
  - Line 161-176: Check max repetition < 100 characters
- Line 238: Detect injection patterns: `threats = detect_injection_patterns(sanitized_input)` (line 73)
  - Line 85-88: Test all 18+ compiled regex patterns
  - No matches found for this benign input
- Line 241: Check threat count: `if len(threats) >= 2:` — **0 threats, passes**

**Output:**

```json
{
  "statusCode": 200,
  "is_valid": true,
  "sanitized_input": "Send an email to john@example.com saying hello",
  "warnings": [],
  "threat_indicators": [],
  "blocked_reason": null
}
```

**CloudWatch Log:** `/aws/lambda/lateos-dev-validator`

```json
{
  "timestamp": "2026-03-01T10:15:32.456Z",
  "level": "INFO",
  "service": "validator",
  "request_id": "xyz-789",
  "is_valid": true,
  "warning_count": 0,
  "sanitized_length": 44,
  "message": "Validation complete"
}
```

---

## Step 5: Intent Classifier Lambda

**File:** `lambdas/core/intent_classifier.py`
**Handler:** `intent_classifier.handler` (line 142)

**Input Event:**

```json
{
  "sanitized_input": "Send an email to john@example.com saying hello",
  "request_id": "xyz-789"
}
```

**Code Path:**

- Line 155: Extract sanitized input
- Line 167: Classify intent: `intent, confidence, entities = classify_intent(sanitized_input)` (line 49)
  - Line 59: Convert to lowercase: `text_lower = text.lower()`
  - Line 66-73: Check EMAIL pattern (line 35-37): `r"\b(send|write|compose)\b.*\b(email|message)\b"`
  - **MATCH FOUND:** "send" + "email"
  - Line 70: Set confidence = 0.8
  - Line 87: Extract entities: `entities = extract_entities(text, best_intent)` (line 92)
    - Line 105-110: Extract email addresses
    - **Found:** `["john@example.com"]`
- Line 171-180: Determine suggested action
  - Line 172: Intent is "email" → suggested_action = "send_email"

**Output:**

```json
{
  "statusCode": 200,
  "intent": "email",
  "confidence": 0.8,
  "entities": {
    "recipients": ["john@example.com"]
  },
  "suggested_action": "send_email",
  "request_id": "xyz-789"
}
```

**CloudWatch Log:** `/aws/lambda/lateos-dev-intent-classifier`

```json
{
  "timestamp": "2026-03-01T10:15:32.789Z",
  "level": "INFO",
  "service": "intent-classifier",
  "request_id": "xyz-789",
  "intent": "email",
  "confidence": 0.8,
  "suggested_action": "send_email",
  "entity_count": 1,
  "message": "Intent classified"
}
```

---

## Step 6: Action Router Lambda

**File:** `lambdas/core/action_router.py`
**Handler:** `action_router.handler` (line 68)

**Input Event:**

```json
{
  "suggested_action": "send_email",
  "user_context": {
    "user_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
    "email": "user@example.com",
    "username": "user123"
  },
  "request_id": "xyz-789",
  "entities": {
    "recipients": ["john@example.com"]
  }
}
```

**Code Path:**

- Line 81-84: Extract action details
- Line 96-103: Check if action is null — not null, continue
- Line 106: Look up skill handler: `skill_handler = SKILL_HANDLERS.get(suggested_action)` (line 24)
  - Line 25: "send_email" maps to "lateos-skill-email"
- Line 107-118: Check if handler exists — yes, continue
- Line 121-136: Check if built-in action — no, skip
- Line 140-168: **Phase 2 placeholder** — returns mock response

**Output (Phase 2):**

```json
{
  "statusCode": 200,
  "success": true,
  "result": {
    "message": "[Phase 2 Placeholder] Would execute 'send_email' using skill 'lateos-skill-email'. Full skill integration coming in Phase 3.",
    "entities": {
      "recipients": ["john@example.com"]
    }
  },
  "error": null,
  "metadata": {
    "skill": "lateos-skill-email",
    "action": "send_email",
    "phase": "2-placeholder"
  },
  "request_id": "xyz-789"
}
```

**CloudWatch Log:** `/aws/lambda/lateos-dev-action-router`

```json
{
  "timestamp": "2026-03-01T10:15:33.012Z",
  "level": "INFO",
  "service": "action-router",
  "request_id": "xyz-789",
  "skill": "lateos-skill-email",
  "action": "send_email",
  "message": "Skill execution placeholder"
}
```

---

## Step 7: Email Skill Lambda (Phase 3+)

**File:** `lambdas/skills/email_skill.py`
**Handler:** `email_skill.lambda_handler` (line 239)

**Input Event:**

```json
{
  "user_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
  "action": "send_email",
  "parameters": {
    "to": ["john@example.com"],
    "subject": "Hello",
    "body": "Hello from Lateos"
  }
}
```

**Code Path:**

- Line 264-266: Extract user_id
- Line 269-271: Extract action
- Line 274: Extract parameters
- Line 277-284: Route to send_email handler (line 79)
  - Line 98: Get Gmail OAuth credentials: `credentials = get_gmail_credentials(user_id)` (line 51)
    - Line 64: Secret name: `lateos/dev/gmail/{user_id}`
    - Line 67: Retrieve from Secrets Manager
    - Line 68: Parse JSON credentials
  - Line 104-110: **Phase 3 mock** — create result dict
  - Line 113: Log to audit table: `log_email_action(user_id, "send_email", result)` (line 207)
    - Line 222-229: DynamoDB put_item

**Output:**

```json
{
  "statusCode": 200,
  "body": {
    "result": {
      "message_id": "mock-a1b2c3d4-5678-90ab-cdef-1234567890ab-123456",
      "status": "sent",
      "to": ["john@example.com"],
      "subject": "Hello",
      "cc": []
    },
    "skill": "email",
    "action": "send_email"
  }
}
```

**CloudWatch Log:** `/aws/lambda/lateos-skill-email`

```json
{
  "timestamp": "2026-03-01T10:15:33.345Z",
  "level": "INFO",
  "service": "email_skill",
  "user_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
  "action": "send_email",
  "message": "Sending email for user a1b2c3d4-5678-90ab-cdef-1234567890ab to ['john@example.com']"
}
```

---

## Step 8: Output Sanitizer Lambda

**File:** `lambdas/core/output_sanitizer.py`
**Handler:** `output_sanitizer.handler` (line 224)

**Input Event:**

```json
{
  "request_id": "xyz-789",
  "result": {
    "message_id": "mock-a1b2c3d4-5678-90ab-cdef-1234567890ab-123456",
    "status": "sent",
    "to": ["john@example.com"],
    "subject": "Hello",
    "cc": []
  }
}
```

**Code Path:**

- Line 236-237: Extract request_id and result
- Line 248: Sanitize result: `sanitized_result = sanitize_dict(action_result)` (line 93)
  - Line 106-131: Recursively scan dictionary
  - Line 110-112: Check for sensitive keys (password, token, secret, api_key, private_key) — none found
  - Line 127-128: Sanitize string values with `sanitize_text()` (line 75)
    - Line 87-88: Apply all redaction patterns (line 45-72)
    - No secrets detected in this output
- Line 251-254: Extract and sanitize message if present
- Line 257-258: Apply Bedrock Guardrails: `guardrails_result = apply_guardrails(final_output)` (line 135)
  - Line 148-150: Check if Bedrock available (LocalStack fallback)
  - Line 150: Return `{"allowed": True, "reason": "guardrails_disabled"}` in LocalStack
- Line 260: Check if allowed — yes, continue

**Output:**

```json
{
  "statusCode": 200,
  "sanitized_result": {
    "message_id": "mock-a1b2c3d4-5678-90ab-cdef-1234567890ab-123456",
    "status": "sent",
    "to": ["john@example.com"],
    "subject": "Hello",
    "cc": []
  },
  "request_id": "xyz-789",
  "guardrails_passed": true
}
```

**CloudWatch Log:** `/aws/lambda/lateos-dev-output-sanitizer`

```json
{
  "timestamp": "2026-03-01T10:15:33.678Z",
  "level": "INFO",
  "service": "output-sanitizer",
  "request_id": "xyz-789",
  "output_size": 142,
  "guardrails_reason": "guardrails_disabled",
  "message": "Output sanitized and Guardrails passed"
}
```

---

## Step 9: Response to User

**API Gateway Response:**

```json
{
  "statusCode": 200,
  "headers": {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*"
  },
  "body": {
    "response_text": "Email sent successfully to john@example.com",
    "success": true,
    "request_id": "xyz-789",
    "metadata": {
      "user_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
      "timestamp": "2026-03-01T10:15:33.900Z"
    }
  }
}
```

**Total Execution Time:** ~1.5 seconds

- API Gateway auth: 50ms
- Orchestrator: 100ms
- Validator: 200ms
- Intent Classifier: 150ms
- Action Router: 100ms
- Email Skill: 500ms (Secrets Manager retrieval + mock execution)
- Output Sanitizer: 300ms
- API Gateway response: 100ms

---

## What Could Go Wrong

### 1. Cognito Token Expired

- **Where:** Step 2 (API Gateway Authorizer)
- **Error:** HTTP 401 Unauthorized
- **CloudWatch Log:** `{"error": "Token expired", "error_code": "LATEOS-002"}`
- **Fix:** Client refreshes token and retries

### 2. Input Too Long

- **Where:** Step 4, line 138 of `validator.py`
- **Error:** `ValidationError("Input is too long (maximum 4000 characters)")`
- **Response:** `{"is_valid": false, "blocked_reason": "Input is too long..."}`
- **Error Code:** `LATEOS-003`

### 3. Secrets Manager Credential Missing

- **Where:** Step 7, line 72 of `email_skill.py`
- **Error:** `ClientError` with code `ResourceNotFoundException`
- **Response:** `{"error": "Gmail not connected. Please authorize Gmail first."}`
- **Error Code:** `LATEOS-007`

### 4. DynamoDB Throttling

- **Where:** Step 7, line 222-229 of `email_skill.py`
- **Error:** `ProvisionedThroughputExceededException`
- **CloudWatch Log:** `{"error": "Failed to log email action", "reason": "throttling"}`
- **Impact:** Email still sent, audit log write failed (non-blocking)
- **Error Code:** `LATEOS-008`

### 5. Lambda Timeout

- **Where:** Any Lambda (30s timeout configured)
- **Error:** Step Functions execution timeout
- **CloudWatch Log:** `{"error": "Task timed out after 30.00 seconds"}`
- **Error Code:** `LATEOS-013`

---

## Debugging This Flow

**To reproduce locally with LocalStack:**

```bash
# Start LocalStack
docker-compose up -d localstack

# Invoke orchestrator directly
aws lambda invoke \
  --function-name lateos-dev-orchestrator \
  --payload '{"body": "{\"input\": \"Send email to test@example.com\"}"}' \
  --endpoint-url http://localhost:4566 \
  response.json

# View logs
aws logs tail /aws/lambda/lateos-dev-orchestrator --follow \
  --endpoint-url http://localhost:4566
```

**To trace through Step Functions (Phase 3):**

```bash
# Start execution
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:000000000000:stateMachine:lateos-dev-workflow \
  --input '{"input": "Send email to test@example.com", "request_id": "debug-123"}' \
  --endpoint-url http://localhost:4566

# View execution history
aws stepfunctions describe-execution \
  --execution-arn {execution_arn} \
  --endpoint-url http://localhost:4566
```

**Key CloudWatch Insights Queries:**

```
# Full request trace by request_id
fields @timestamp, service, message
| filter request_id = "xyz-789"
| sort @timestamp asc

# All requests for a user
fields @timestamp, request_id, message
| filter user_id = "a1b2c3d4-5678-90ab-cdef-1234567890ab"
| sort @timestamp desc

# Errors only
fields @timestamp, service, error_code, message
| filter level = "ERROR"
| sort @timestamp desc
```

---

**Next Walkthrough:** [02-prompt-injection-blocked.md](02-prompt-injection-blocked.md) — What happens when malicious input is detected
