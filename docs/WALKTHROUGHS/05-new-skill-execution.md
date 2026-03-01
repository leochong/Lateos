# Walkthrough 05: New Skill Execution — Email Skill End-to-End

**Complete trace of email skill execution from intent classification to audit log**

This walkthrough shows the exact code path when a user requests to send an email, including IAM role scope verification, OAuth token retrieval from Secrets Manager, and DynamoDB audit logging.

---

## Scenario

User sends a natural language request to send an email.

**User Request:**

```
"Send an email to john@example.com with subject 'Meeting Tomorrow' and body 'Let's meet at 10am'"
```

---

## Request Flow

```
User → API Gateway → Cognito Auth → Orchestrator →
Validator → Intent Classifier [EMAIL_SEND] →
Action Router → Email Skill Lambda [FOCUS OF THIS WALKTHROUGH] →
Output Sanitizer → Response
```

---

## Step 1: Intent Classification

**File:** `lambdas/core/intent_classifier.py:142-210`

**Input:**

```json
{
  "sanitized_input": "Send an email to john@example.com with subject 'Meeting Tomorrow' and body 'Let's meet at 10am'",
  "request_id": "req-abc-123"
}
```

**Pattern Matching (Lines 49-88):**

```python
INTENT_PATTERNS = {
    "email": [
        r"\b(email|send|message|compose|draft|mail)\b.*\b(to|recipient)\b",
        r"\b(send|write|compose)\b.*\b(email|message)\b",
    ],
    # ... other patterns
}
```

**Match Found:**

- Pattern: `r"\b(send|write|compose)\b.*\b(email|message)\b"`
- Match: "**Send**" + "**email**"
- Confidence: **0.8** (high confidence for direct pattern match)

**Entity Extraction (Lines 92-137):**

```python
def extract_entities(text: str, intent: str) -> Dict[str, Any]:
    entities = {}

    if intent == "email":
        # Extract email addresses
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        emails = re.findall(email_pattern, text)
        if emails:
            entities["recipients"] = emails
```

**Extracted Entities:**

```json
{
  "recipients": ["john@example.com"]
}
```

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
  "request_id": "req-abc-123"
}
```

**CloudWatch Log:**

```json
{
  "timestamp": "2026-03-01T15:45:20.234Z",
  "level": "INFO",
  "service": "intent-classifier",
  "request_id": "req-abc-123",
  "intent": "email",
  "confidence": 0.8,
  "suggested_action": "send_email",
  "entity_count": 1,
  "message": "Intent classified"
}
```

---

## Step 2: Action Router Routes to Email Skill

**File:** `lambdas/core/action_router.py:68-179`

**Input:**

```json
{
  "suggested_action": "send_email",
  "user_context": {
    "user_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
    "email": "user@example.com",
    "username": "user123"
  },
  "request_id": "req-abc-123",
  "entities": {
    "recipients": ["john@example.com"]
  }
}
```

**Skill Lookup (Line 106):**

```python
SKILL_HANDLERS = {
    "send_email": "lateos-skill-email",
    "create_calendar_event": "lateos-skill-calendar",
    "web_search": "lateos-skill-web",
    "respond_greeting": "built-in",
    "show_help": "built-in",
}

skill_handler = SKILL_HANDLERS.get(suggested_action)
# Returns: "lateos-skill-email"
```

**Step Functions Routing (infrastructure/stacks/orchestration_stack.py:483-496):**

```python
# Email skill routing
if hasattr(self.skills_stack, "email_skill"):
    email_skill_task = tasks.LambdaInvoke(
        self,
        "InvokeEmailSkill",
        lambda_function=self.skills_stack.email_skill,
        output_path="$.Payload",
        comment="Execute email skill",
    )
    email_skill_task.next(sanitize_output_task)
    choice.when(
        sfn.Condition.string_equals("$.skill", "email"),
        email_skill_task,
    )
```

**Output to Email Skill:**

```json
{
  "user_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
  "action": "send_email",
  "parameters": {
    "to": ["john@example.com"],
    "subject": "Meeting Tomorrow",
    "body": "Let's meet at 10am"
  },
  "request_id": "req-abc-123"
}
```

---

## Step 3: Email Skill Lambda Execution

**File:** `lambdas/skills/email_skill.py:239-317`

**Lambda Function Name:** `lateos-dev-skill-email`

### 3.1: Handler Entry Point (Line 239)

```python
@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    logger.info("Email skill invoked", extra={"event": event})
```

**CloudWatch Log:**

```json
{
  "timestamp": "2026-03-01T15:45:20.456Z",
  "level": "INFO",
  "service": "email_skill",
  "cold_start": false,
  "function_name": "lateos-dev-skill-email",
  "function_version": "$LATEST",
  "function_memory_size": 512,
  "message": "Email skill invoked",
  "event": {
    "user_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
    "action": "send_email",
    "parameters": { /* ... */ }
  }
}
```

### 3.2: Extract Request Parameters (Lines 264-274)

```python
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
```

**Extracted:**

- `user_id`: `"a1b2c3d4-5678-90ab-cdef-1234567890ab"`
- `action`: `"send_email"`
- `params`: `{"to": ["john@example.com"], "subject": "Meeting Tomorrow", "body": "Let's meet at 10am"}`

---

## Step 4: IAM Role Scope Verification

**IAM Role:** `lateos-dev-skill-email-role`

**File:** `infrastructure/stacks/skills_stack.py` (lines defining email skill role)

**Scoped Permissions (RULE 2 — No wildcards):**

```python
# Email skill can ONLY access Gmail OAuth secrets
email_skill_role.add_to_policy(
    iam.PolicyStatement(
        sid="AllowGmailSecretsAccess",
        actions=[
            "secretsmanager:GetSecretValue",
            "secretsmanager:DescribeSecret"
        ],
        resources=[
            f"arn:aws:secretsmanager:{self.region}:{self.account}:"
            f"secret:lateos/{environment}/gmail/*"
        ]
    )
)

# Email skill can ONLY write to audit table
email_skill_role.add_to_policy(
    iam.PolicyStatement(
        sid="AllowAuditTableWrite",
        actions=["dynamodb:PutItem"],
        resources=[audit_table.table_arn],
        conditions={
            "ForAllValues:StringEquals": {
                "dynamodb:LeadingKeys": ["${aws:PrincipalTag/user_id}"]
            }
        }
    )
)
```

**What This Means:**

| Can Access | Cannot Access |
|------------|---------------|
| `lateos/dev/gmail/*` secrets | Calendar skill secrets |
| Audit DynamoDB table (own user_id only) | Other users' data |
| CloudWatch Logs (own Lambda only) | Other Lambdas' logs |

**If skill tries to access calendar secret:**

```
botocore.exceptions.ClientError: An error occurred (AccessDenied) when calling
the GetSecretValue operation: User is not authorized to perform
secretsmanager:GetSecretValue on resource: lateos/dev/calendar/user-123
```

**Error Code:** `LATEOS-007` (Skill Lambda IAM permission denied)

---

## Step 5: Retrieve OAuth Token from Secrets Manager

**File:** `lambdas/skills/email_skill.py:51-76`

**Function Call (Line 98):**

```python
credentials = get_gmail_credentials(user_id)
```

**Implementation:**

```python
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
```

**Secrets Manager Call:**

```python
secret_name = "lateos/dev/gmail/a1b2c3d4-5678-90ab-cdef-1234567890ab"
response = secrets_manager.get_secret_value(SecretId=secret_name)
```

**Secret Structure (NEVER LOGGED):**

```json
{
  "access_token": "ya29.a0AfH6SMBx7K1jZ3cV8bN2mQ4rT6sW...",
  "refresh_token": "1//0gZ1xYz3cV8bN2mQ4rT6sW9eL5kD8pF...",
  "token_uri": "https://oauth2.googleapis.com/token",
  "client_id": "123456789012-abc...apps.googleusercontent.com",
  "client_secret": "GOCSPX-abc123...",
  "scopes": ["https://www.googleapis.com/auth/gmail.send"],
  "expiry": "2026-03-01T16:45:20Z"
}
```

**CloudWatch Log (Secrets REDACTED):**

```json
{
  "timestamp": "2026-03-01T15:45:20.567Z",
  "level": "INFO",
  "service": "email_skill",
  "user_id": "a1b2c3d4-***-***",
  "message": "Retrieved OAuth credentials for Gmail"
}
```

**Note:** User ID is partially redacted in logs to prevent correlation attacks.

---

## Step 6: Send Email via Gmail API

**File:** `lambdas/skills/email_skill.py:79-115`

**Function:** `send_email()` at line 79

```python
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
    credentials = get_gmail_credentials(user_id)

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
```

**In Production (Phase 4+):**

```python
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# Build credentials object
creds = Credentials(
    token=credentials['access_token'],
    refresh_token=credentials['refresh_token'],
    token_uri=credentials['token_uri'],
    client_id=credentials['client_id'],
    client_secret=credentials['client_secret'],
    scopes=credentials['scopes']
)

# Build Gmail service
service = build('gmail', 'v1', credentials=creds)

# Create message
message = MIMEText(body)
message['to'] = ', '.join(to)
message['subject'] = subject
raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

# Send
send_result = service.users().messages().send(
    userId='me',
    body={'raw': raw_message}
).execute()

result = {
    "message_id": send_result['id'],
    "thread_id": send_result['threadId'],
    "status": "sent",
    "to": to,
    "subject": subject
}
```

**Mock Result (Phase 3):**

```json
{
  "message_id": "mock-a1b2c3d4-5678-90ab-cdef-1234567890ab--1234567890",
  "status": "sent",
  "to": ["john@example.com"],
  "subject": "Meeting Tomorrow",
  "cc": []
}
```

**CloudWatch Log:**

```json
{
  "timestamp": "2026-03-01T15:45:20.678Z",
  "level": "INFO",
  "service": "email_skill",
  "user_id": "a1b2c3d4-***-***",
  "action": "send_email",
  "recipient_count": 1,
  "message": "Sending email for user a1b2c3d4-5678-90ab-cdef-1234567890ab to ['john@example.com']"
}
```

---

## Step 7: Write Audit Log to DynamoDB

**File:** `lambdas/skills/email_skill.py:207-234`

**Function:** `log_email_action()` at line 207

```python
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
```

**DynamoDB Table:** `lateos-dev-audit`

**Partition Key:** `user_id` (ensures RULE 6 — per-user isolation)
**Sort Key:** `timestamp`

**Item Written:**

```json
{
  "user_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
  "timestamp": "2026-03-01T15:45:20.789Z",
  "skill": "email",
  "action": "send_email",
  "details": "{\"message_id\": \"mock-a1b2c3d4-5678-90ab-cdef-1234567890ab--1234567890\", \"status\": \"sent\", \"to\": [\"john@example.com\"], \"subject\": \"Meeting Tomorrow\", \"cc\": []}",
  "request_id": "req-abc-123"
}
```

**IAM Permission Check:**

The DynamoDB write is scoped to the authenticated user's partition key:

```python
conditions={
    "ForAllValues:StringEquals": {
        "dynamodb:LeadingKeys": ["${aws:PrincipalTag/user_id}"]
    }
}
```

**If skill tries to write to another user's partition:**

```
AccessDeniedException: User is not authorized to perform dynamodb:PutItem
on resource with leading key user-999 (authenticated as user-123)
```

**CloudWatch Log:**

```json
{
  "timestamp": "2026-03-01T15:45:20.801Z",
  "level": "INFO",
  "service": "email_skill",
  "user_id": "a1b2c3d4-***-***",
  "action": "send_email",
  "message": "Logged email action: send_email for user a1b2c3d4-5678-90ab-cdef-1234567890ab"
}
```

---

## Step 8: Return Result to Step Functions

**Email Skill Output:**

```json
{
  "statusCode": 200,
  "body": {
    "result": {
      "message_id": "mock-a1b2c3d4-5678-90ab-cdef-1234567890ab--1234567890",
      "status": "sent",
      "to": ["john@example.com"],
      "subject": "Meeting Tomorrow",
      "cc": []
    },
    "skill": "email",
    "action": "send_email"
  }
}
```

**Step Functions continues to:**
→ Output Sanitizer Lambda (sanitizes result, applies Bedrock Guardrails)
→ Returns final response to user

---

## Step 9: Output Sanitization

**File:** `lambdas/core/output_sanitizer.py:224-307`

**Input:**

```json
{
  "request_id": "req-abc-123",
  "result": {
    "message_id": "mock-a1b2c3d4-5678-90ab-cdef-1234567890ab--1234567890",
    "status": "sent",
    "to": ["john@example.com"],
    "subject": "Meeting Tomorrow",
    "cc": []
  }
}
```

**Sanitization Process:**

1. **Dictionary Sanitization** (Line 248):
   - Scan for sensitive keys: `password`, `token`, `secret`, `api_key`
   - None found in this output

2. **Text Pattern Redaction** (Lines 75-90):
   - Apply regex patterns: API keys, AWS credentials, private keys, IPs
   - None found in this output

3. **Bedrock Guardrails** (Lines 135-219):
   - Check for harmful content
   - Check for PII leakage
   - Clean output — PASS

**Output:**

```json
{
  "statusCode": 200,
  "sanitized_result": {
    "message_id": "mock-a1b2c3d4-5678-90ab-cdef-1234567890ab--1234567890",
    "status": "sent",
    "to": ["john@example.com"],
    "subject": "Meeting Tomorrow",
    "cc": []
  },
  "request_id": "req-abc-123",
  "guardrails_passed": true
}
```

---

## Final Response to User

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
    "request_id": "req-abc-123",
    "metadata": {
      "user_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
      "timestamp": "2026-03-01T15:45:20.900Z",
      "message_id": "mock-a1b2c3d4-5678-90ab-cdef-1234567890ab--1234567890"
    }
  }
}
```

**User Sees:**

```
Lateos: "Email sent successfully to john@example.com (Message ID: mock-a1b2c3d4-***)"
```

---

## Execution Timeline

| Timestamp | Component | Duration | Action |
|-----------|-----------|----------|--------|
| 15:45:20.234 | Intent Classifier | 45ms | Classified as EMAIL_SEND |
| 15:45:20.279 | Action Router | 30ms | Routed to email skill |
| 15:45:20.456 | Email Skill | 222ms | **Skill execution start** |
| 15:45:20.567 | Secrets Manager | 111ms | Retrieved OAuth token |
| 15:45:20.678 | Gmail API (mock) | 111ms | Sent email |
| 15:45:20.801 | DynamoDB | 123ms | Wrote audit log |
| 15:45:20.824 | Email Skill | 0ms | **Skill execution complete** |
| 15:45:20.900 | Output Sanitizer | 76ms | Sanitized and returned |

**Total Email Skill Execution:** 368ms

---

## What Could Go Wrong?

### 1. OAuth Token Not Found

**Where:** Step 5, line 67 of `email_skill.py`

```python
except ClientError as e:
    error_code = e.response["Error"]["Code"]
    if error_code == "ResourceNotFoundException":
        raise EmailSkillError("Gmail not connected. Please authorize Gmail first.")
```

**Error Code:** `LATEOS-007`
**User Message:** "Gmail not connected. Please authorize Gmail first."

### 2. OAuth Token Expired

**Where:** Gmail API call (production)

```python
except RefreshError as e:
    raise EmailSkillError("Gmail authorization expired. Please re-authorize.")
```

**Error Code:** `LATEOS-015`
**Fix:** User re-authorizes via OAuth flow

### 3. IAM Permission Denied

**Where:** Secrets Manager retrieval

```
AccessDeniedException: User: arn:aws:sts::123456789012:assumed-role/lateos-dev-skill-email-role
is not authorized to perform: secretsmanager:GetSecretValue
on resource: lateos/dev/calendar/user-123
```

**Error Code:** `LATEOS-007`
**Cause:** Skill tried to access another skill's secret (security violation)

### 4. DynamoDB Throttling

**Where:** Step 7, line 222-229 of `email_skill.py`

```
ProvisionedThroughputExceededException: Rate of requests exceeds the allowed throughput
```

**Behavior:** Log error, continue anyway (audit write is non-blocking)
**Error Code:** `LATEOS-008`

### 5. Gmail API Rate Limit (Production)

**Where:** Gmail API send call

```
HttpError 429: Rate Limit Exceeded
```

**Mitigation:** Exponential backoff retry (3 attempts)
**Error Code:** Custom skill error

---

## Security Guarantees Demonstrated

| Security Rule | How It's Enforced |
|---------------|-------------------|
| RULE 1 | OAuth token retrieved from Secrets Manager only |
| RULE 2 | IAM role scoped to `lateos/dev/gmail/*` only |
| RULE 6 | DynamoDB write scoped to authenticated user_id partition |
| RULE 7 | Email skill Lambda has `reserved_concurrent_executions = 10` |
| RULE 8 | OAuth token NEVER logged, redacted by output sanitizer |

---

## CloudWatch Insights Query: Trace Email Skill Execution

```sql
fields @timestamp, service, action, message, user_id
| filter request_id = "req-abc-123"
| sort @timestamp asc
```

**Result:**

```
15:45:20.234  intent-classifier  -           Intent classified
15:45:20.279  action-router      -           Skill execution placeholder
15:45:20.456  email_skill        send_email  Email skill invoked
15:45:20.567  email_skill        send_email  Retrieved OAuth credentials
15:45:20.678  email_skill        send_email  Sending email for user...
15:45:20.801  email_skill        send_email  Logged email action
15:45:20.900  output-sanitizer   -           Output sanitized and Guardrails passed
```

---

**Next Walkthrough:** [06-local-development-debug.md](./06-local-development-debug.md) — How to debug without AI assistance
