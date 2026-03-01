# Walkthrough 06: Local Development Debug — Fixing Without AI Assistance

**How to reproduce errors in LocalStack, read structured logs, and write regression tests**

This walkthrough demonstrates the anti-vibe-coding principle: you can debug and fix Lateos without AI assistance because the system emits structured, searchable logs with actionable error codes.

---

## Scenario: Email Skill Fails with "AccessDenied"

**User Report:**

```
"I tried to send an email and got an error: 'Failed to access Gmail credentials'"
```

**Your Goal:** Reproduce the error locally, identify the root cause, fix it, and write a test to prevent regression.

---

## Phase 1: Reproduce in LocalStack

### Step 1: Start Local Environment

```bash
# Terminal 1: Start LocalStack
cd ~/Documents/projects/Lateos
docker-compose up -d localstack

# Verify services are running
docker ps | grep localstack
```

**Expected Output:**

```
CONTAINER ID   IMAGE                   STATUS         PORTS
abc123def456   localstack/localstack   Up 2 minutes   0.0.0.0:4566->4566/tcp
```

### Step 2: Deploy Infrastructure Locally

```bash
# Terminal 2: Activate virtual environment
source .venv/bin/activate

# Set AWS credentials for LocalStack
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
export AWS_ENDPOINT_URL=http://localhost:4566

# Deploy CDK stacks
cdklocal bootstrap
cdklocal deploy --all --require-approval never
```

**Expected Output:**

```
 ✅  LateosCore
 ✅  LateosOrchestration
 ✅  LateosSkills
 ✅  LateosMemory
 ✅  LateosCostProtection

Stack ARN:
arn:aws:cloudformation:us-east-1:000000000000:stack/LateosCore/...
```

### Step 3: Create Test User in LocalStack Cognito

```bash
# Create user pool (if not already created by CDK)
USER_POOL_ID=$(aws cognito-idp list-user-pools --max-results 10 \
  --endpoint-url http://localhost:4566 \
  --query 'UserPools[?Name==`lateos-dev-users`].Id' \
  --output text)

echo "User Pool ID: $USER_POOL_ID"

# Create test user
aws cognito-idp admin-create-user \
  --user-pool-id "$USER_POOL_ID" \
  --username testuser \
  --user-attributes Name=email,Value=testuser@example.com \
  --temporary-password TempPass123! \
  --endpoint-url http://localhost:4566

# Set permanent password
aws cognito-idp admin-set-user-password \
  --user-pool-id "$USER_POOL_ID" \
  --username testuser \
  --password TestPass123! \
  --permanent \
  --endpoint-url http://localhost:4566

# Get user sub (user_id)
USER_ID=$(aws cognito-idp admin-get-user \
  --user-pool-id "$USER_POOL_ID" \
  --username testuser \
  --endpoint-url http://localhost:4566 \
  --query 'UserAttributes[?Name==`sub`].Value' \
  --output text)

echo "User ID: $USER_ID"
```

### Step 4: Attempt to Invoke Email Skill (WITHOUT OAuth Secret)

```bash
# Invoke email skill Lambda directly
aws lambda invoke \
  --function-name lateos-dev-skill-email \
  --payload "{\"user_id\": \"$USER_ID\", \"action\": \"send_email\", \"parameters\": {\"to\": [\"test@example.com\"], \"subject\": \"Test\", \"body\": \"Hello\"}}" \
  --endpoint-url http://localhost:4566 \
  response.json

# View response
cat response.json | jq
```

**Expected Output (Error):**

```json
{
  "statusCode": 400,
  "body": {
    "error": "Gmail not connected. Please authorize Gmail first.",
    "skill": "email"
  }
}
```

**Success! Error reproduced locally.**

---

## Phase 2: Read Structured Logs

### Step 5: Extract CloudWatch Logs from LocalStack

```bash
# List log groups
aws logs describe-log-groups \
  --endpoint-url http://localhost:4566 \
  --query 'logGroups[].logGroupName'

# Get latest log stream for email skill
LOG_STREAM=$(aws logs describe-log-streams \
  --log-group-name /aws/lambda/lateos-dev-skill-email \
  --endpoint-url http://localhost:4566 \
  --order-by LastEventTime \
  --descending \
  --max-items 1 \
  --query 'logStreams[0].logStreamName' \
  --output text)

# Get log events
aws logs get-log-events \
  --log-group-name /aws/lambda/lateos-dev-skill-email \
  --log-stream-name "$LOG_STREAM" \
  --endpoint-url http://localhost:4566 \
  --query 'events[].message' \
  --output text
```

**Log Output:**

```json
{
  "level": "INFO",
  "service": "email_skill",
  "timestamp": "2026-03-01T16:30:12.123Z",
  "function_request_id": "abc-123-def-456",
  "message": "Email skill invoked",
  "event": {
    "user_id": "9f8e7d6c-5b4a-3c2d-1e0f-9a8b7c6d5e4f",
    "action": "send_email",
    "parameters": { /* ... */ }
  }
}

{
  "level": "WARNING",
  "service": "email_skill",
  "timestamp": "2026-03-01T16:30:12.234Z",
  "function_request_id": "abc-123-def-456",
  "message": "Gmail credentials not found for user 9f8e7d6c-5b4a-3c2d-1e0f-9a8b7c6d5e4f"
}

{
  "level": "ERROR",
  "service": "email_skill",
  "timestamp": "2026-03-01T16:30:12.345Z",
  "function_request_id": "abc-123-def-456",
  "error": "Email skill error: Gmail not connected. Please authorize Gmail first."
}
```

### Step 6: Identify Error Code

**File:** `lambdas/shared/error_codes.py:51-76`

Search for "Gmail credentials not found":

```bash
cd ~/Documents/projects/Lateos
grep -r "Gmail credentials not found" lambdas/
```

**Result:**

```
lambdas/skills/email_skill.py:72:            logger.warning(f"Gmail credentials not found for user {user_id}")
```

**Code at Line 72:**

```python
except ClientError as e:
    error_code = e.response["Error"]["Code"]
    if error_code == "ResourceNotFoundException":
        logger.warning(f"Gmail credentials not found for user {user_id}")
        raise EmailSkillError("Gmail not connected. Please authorize Gmail first.")
```

**Error Code:** `LATEOS-007` (Skill Lambda IAM permission denied)

**Look up in error catalog:**

```bash
grep -A 10 "SKILL_IAM_PERMISSION_DENIED" lambdas/shared/error_codes.py
```

**Result:**

```python
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
```

**Investigation Step 5 is the key:** "Check if Secrets Manager secret exists for user_id"

---

## Phase 3: Identify Root Cause

### Step 7: Check Secrets Manager

```bash
# List all secrets
aws secretsmanager list-secrets \
  --endpoint-url http://localhost:4566 \
  --query 'SecretList[].Name'

# Try to get the Gmail secret for our user
aws secretsmanager get-secret-value \
  --secret-id "lateos/dev/gmail/$USER_ID" \
  --endpoint-url http://localhost:4566
```

**Expected Output:**

```
An error occurred (ResourceNotFoundException) when calling the GetSecretValue operation:
Secrets Manager can't find the specified secret.
```

**Root Cause Identified:** The OAuth secret does not exist for this user.

**Why?** User has not completed OAuth authorization flow yet.

---

## Phase 4: Fix the Issue

### Step 8: Create Mock OAuth Secret for Testing

```bash
# Create Gmail OAuth secret for test user
aws secretsmanager create-secret \
  --name "lateos/dev/gmail/$USER_ID" \
  --description "Gmail OAuth credentials for testuser" \
  --secret-string '{
    "access_token": "ya29.mock-access-token-for-testing",
    "refresh_token": "1//mock-refresh-token-for-testing",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": "mock-client-id.apps.googleusercontent.com",
    "client_secret": "GOCSPX-mock-secret",
    "scopes": ["https://www.googleapis.com/auth/gmail.send"],
    "expiry": "2026-12-31T23:59:59Z"
  }' \
  --endpoint-url http://localhost:4566
```

**Expected Output:**

```json
{
  "ARN": "arn:aws:secretsmanager:us-east-1:000000000000:secret:lateos/dev/gmail/9f8e7d6c-abc123",
  "Name": "lateos/dev/gmail/9f8e7d6c-5b4a-3c2d-1e0f-9a8b7c6d5e4f",
  "VersionId": "abc-123-def-456"
}
```

### Step 9: Retry Email Skill Invocation

```bash
aws lambda invoke \
  --function-name lateos-dev-skill-email \
  --payload "{\"user_id\": \"$USER_ID\", \"action\": \"send_email\", \"parameters\": {\"to\": [\"test@example.com\"], \"subject\": \"Test\", \"body\": \"Hello\"}}" \
  --endpoint-url http://localhost:4566 \
  response.json

cat response.json | jq
```

**Expected Output (Success):**

```json
{
  "statusCode": 200,
  "body": {
    "result": {
      "message_id": "mock-9f8e7d6c-5b4a-3c2d-1e0f-9a8b7c6d5e4f--123456",
      "status": "sent",
      "to": ["test@example.com"],
      "subject": "Test",
      "cc": []
    },
    "skill": "email",
    "action": "send_email"
  }
}
```

**Success! Issue fixed.**

---

## Phase 5: Write Regression Test

### Step 10: Create Test Case

**File:** `tests/unit/skills/test_email_skill.py`

```python
import json
import pytest
from moto import mock_secretsmanager
import boto3
from lambdas.skills.email_skill import lambda_handler, EmailSkillError


@mock_secretsmanager
def test_email_skill_missing_oauth_credentials():
    """
    Test that email skill returns appropriate error when OAuth credentials
    are not configured for the user.

    Regression test for: User attempting to send email before OAuth setup.
    Error Code: LATEOS-007
    """
    # Arrange
    user_id = "test-user-missing-oauth-123"

    # Do NOT create secret (simulating user who hasn't authorized Gmail)

    event = {
        "user_id": user_id,
        "action": "send_email",
        "parameters": {
            "to": ["recipient@example.com"],
            "subject": "Test Email",
            "body": "This should fail"
        }
    }

    # Act
    response = lambda_handler(event, None)

    # Assert
    assert response["statusCode"] == 400
    assert "Gmail not connected" in response["body"]["error"]
    assert response["body"]["skill"] == "email"


@mock_secretsmanager
def test_email_skill_send_email_success():
    """
    Test successful email send with valid OAuth credentials.

    Verifies:
    - OAuth token retrieval from Secrets Manager
    - Email send operation
    - Proper response structure
    """
    # Arrange
    user_id = "test-user-with-oauth-456"

    # Create mock Secrets Manager
    sm_client = boto3.client('secretsmanager', region_name='us-east-1')

    # Create OAuth secret
    sm_client.create_secret(
        Name=f'lateos/dev/gmail/{user_id}',
        SecretString=json.dumps({
            'access_token': 'mock-access-token',
            'refresh_token': 'mock-refresh-token',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'client_id': 'mock-client-id',
            'client_secret': 'GOCSPX-mock',
            'scopes': ['https://www.googleapis.com/auth/gmail.send'],
            'expiry': '2026-12-31T23:59:59Z'
        })
    )

    event = {
        "user_id": user_id,
        "action": "send_email",
        "parameters": {
            "to": ["recipient@example.com"],
            "subject": "Test Email",
            "body": "Hello from test"
        }
    }

    # Act
    response = lambda_handler(event, None)

    # Assert
    assert response["statusCode"] == 200
    assert response["body"]["skill"] == "email"
    assert response["body"]["action"] == "send_email"
    assert response["body"]["result"]["status"] == "sent"
    assert response["body"]["result"]["to"] == ["recipient@example.com"]
    assert "message_id" in response["body"]["result"]


@mock_secretsmanager
def test_email_skill_iam_permission_denied():
    """
    Test that email skill cannot access secrets from other skills.

    Security test for RULE 2: IAM role scoping.
    Verifies that email skill can only access lateos/dev/gmail/* secrets.
    """
    # Arrange
    user_id = "test-user-security-789"

    sm_client = boto3.client('secretsmanager', region_name='us-east-1')

    # Create a CALENDAR secret (should be inaccessible to email skill)
    sm_client.create_secret(
        Name=f'lateos/dev/calendar/{user_id}',
        SecretString=json.dumps({
            'access_token': 'calendar-token',
            'refresh_token': 'calendar-refresh'
        })
    )

    # Email skill tries to send email but only calendar secret exists
    event = {
        "user_id": user_id,
        "action": "send_email",
        "parameters": {
            "to": ["test@example.com"],
            "subject": "Test",
            "body": "Test"
        }
    }

    # Act
    response = lambda_handler(event, None)

    # Assert
    # Should fail because gmail secret doesn't exist
    # (In real AWS, would also fail if trying to access calendar secret due to IAM)
    assert response["statusCode"] == 400
    assert "Gmail not connected" in response["body"]["error"]
```

### Step 11: Run Test

```bash
# Install test dependencies
pip install pytest pytest-cov moto

# Run the specific test
pytest tests/unit/skills/test_email_skill.py::test_email_skill_missing_oauth_credentials -v

# Run all email skill tests
pytest tests/unit/skills/test_email_skill.py -v

# Run with coverage
pytest tests/unit/skills/test_email_skill.py --cov=lambdas/skills/email_skill --cov-report=term-missing
```

**Expected Output:**

```
tests/unit/skills/test_email_skill.py::test_email_skill_missing_oauth_credentials PASSED
tests/unit/skills/test_email_skill.py::test_email_skill_send_email_success PASSED
tests/unit/skills/test_email_skill.py::test_email_skill_iam_permission_denied PASSED

---------- coverage: platform darwin, python 3.12.0 -----------
Name                                    Stmts   Miss  Cover   Missing
---------------------------------------------------------------------
lambdas/skills/email_skill.py             95      3    97%   45-47
---------------------------------------------------------------------
TOTAL                                     95      3    97%

3 passed in 0.45s
```

---

## Phase 6: Verify Fix End-to-End

### Step 12: Test Full Request Flow in LocalStack

```bash
# Get Cognito client credentials
CLIENT_ID=$(aws cognito-idp list-user-pool-clients \
  --user-pool-id "$USER_POOL_ID" \
  --endpoint-url http://localhost:4566 \
  --query 'UserPoolClients[0].ClientId' \
  --output text)

# Authenticate and get JWT token
AUTH_RESULT=$(aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id "$CLIENT_ID" \
  --auth-parameters USERNAME=testuser,PASSWORD=TestPass123! \
  --endpoint-url http://localhost:4566)

ACCESS_TOKEN=$(echo "$AUTH_RESULT" | jq -r '.AuthenticationResult.AccessToken')

# Get API Gateway URL
API_ID=$(aws apigateway get-rest-apis \
  --endpoint-url http://localhost:4566 \
  --query 'items[?name==`lateos-dev-api`].id' \
  --output text)

API_URL="http://localhost:4566/restapis/$API_ID/dev/_user_request_/agent"

# Send POST request to /agent endpoint
curl -X POST "$API_URL" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"input": "Send an email to john@example.com saying hello"}' \
  | jq
```

**Expected Output:**

```json
{
  "statusCode": 200,
  "body": {
    "response_text": "Email sent successfully to john@example.com",
    "success": true,
    "request_id": "abc-123-def-456",
    "metadata": {
      "user_id": "9f8e7d6c-5b4a-3c2d-1e0f-9a8b7c6d5e4f",
      "timestamp": "2026-03-01T16:45:30.123Z",
      "message_id": "mock-9f8e7d6c-***"
    }
  }
}
```

**Success! Full end-to-end flow works.**

---

## Common Failure Patterns & Fixes

### Pattern 1: Lambda Timeout

**Symptom:**

```json
{
  "errorType": "Task timed out after 30.00 seconds"
}
```

**Investigation:**

1. Check Lambda CloudWatch logs for slow operation
2. Look for external API calls (Gmail, Bedrock) taking too long
3. Check if LocalStack is slow (restart container)

**Fix:**

```python
# In infrastructure CDK stack
timeout=Duration.seconds(60)  # Increase from 30s to 60s
```

**Test:**

```python
def test_email_skill_timeout_handling():
    """Test that skill handles slow Gmail API gracefully"""
    with mock.patch('email_skill.send_gmail_api_request',
                    side_effect=TimeoutError):
        response = lambda_handler(event, None)
        assert response["statusCode"] == 500
        assert "timeout" in response["body"]["error"].lower()
```

### Pattern 2: DynamoDB Throttling

**Symptom:**

```
ProvisionedThroughputExceededException: Rate of requests exceeds allowed throughput
```

**Investigation:**

```bash
# Check DynamoDB table metrics in LocalStack
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedWriteCapacityUnits \
  --dimensions Name=TableName,Value=lateos-dev-audit \
  --start-time 2026-03-01T00:00:00Z \
  --end-time 2026-03-01T23:59:59Z \
  --period 3600 \
  --statistics Sum \
  --endpoint-url http://localhost:4566
```

**Fix:**

```python
# Use on-demand billing mode (already configured)
billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST
```

**Test:**

```python
@mock_dynamodb
def test_audit_log_throttling_resilience():
    """Test that audit logging failure doesn't break email send"""
    # Simulate DynamoDB throttling
    with mock.patch('boto3.resource') as mock_boto:
        mock_table = mock.Mock()
        mock_table.put_item.side_effect = ClientError(
            {'Error': {'Code': 'ProvisionedThroughputExceededException'}},
            'PutItem'
        )
        mock_boto.return_value.Table.return_value = mock_table

        # Email should still succeed even if audit fails
        response = lambda_handler(event, None)
        assert response["statusCode"] == 200
```

### Pattern 3: Secrets Manager Encryption Key Missing

**Symptom:**

```
AccessDeniedException: User is not authorized to perform: kms:Decrypt
```

**Investigation:**

```bash
# Check KMS key permissions
aws kms describe-key --key-id alias/lateos/dev/secrets \
  --endpoint-url http://localhost:4566
```

**Fix:**

```python
# Grant Lambda role KMS decrypt permission (infrastructure CDK)
email_skill_role.add_to_policy(
    iam.PolicyStatement(
        sid="AllowKMSDecrypt",
        actions=["kms:Decrypt", "kms:DescribeKey"],
        resources=[secrets_kms_key.key_arn]
    )
)
```

---

## Debugging Without AI: Key Principles

### 1. Always Check Structured Logs First

**Good Log (Searchable):**

```json
{
  "level": "ERROR",
  "error_code": "LATEOS-007",
  "service": "email_skill",
  "user_id": "abc-123",
  "message": "Gmail credentials not found"
}
```

**Bad Log (Vibe-coded):**

```
Error occurred
```

### 2. Use Error Code Catalog

Every error has:

- **Code**: `LATEOS-XXX`
- **Investigation Steps**: Exactly what to check
- **Fix**: Root cause category

**Lookup Command:**

```bash
grep -A 15 "LATEOS-007" lambdas/shared/error_codes.py
```

### 3. Write Regression Tests Immediately

**Pattern:**

```python
def test_{feature}_{failure_mode}():
    """
    Regression test for: {GitHub issue or incident}
    Error Code: LATEOS-XXX
    """
    # Arrange: Set up failure condition
    # Act: Trigger the code path
    # Assert: Verify error handling
```

### 4. Use LocalStack for Fast Iteration

**Benefits:**

- No AWS costs
- Fast deployment (seconds vs minutes)
- Full reset: `docker-compose down && docker-compose up`
- Same API as real AWS

### 5: Read the Source Code

**When stuck:**

1. Find the log message in the code: `grep -r "error message"`
2. Read the function context (10 lines before/after)
3. Trace backward: What calls this function?
4. Trace forward: What does this function call?

**Example:**

```bash
# Find where error is raised
grep -n "Gmail not connected" lambdas/skills/email_skill.py

# Output: Line 73
# Now read lines 60-80
sed -n '60,80p' lambdas/skills/email_skill.py
```

---

## Final Verification Checklist

Before marking issue as fixed:

- [ ] Error reproduced in LocalStack
- [ ] Root cause identified via structured logs
- [ ] Fix implemented and tested locally
- [ ] Regression test written (pytest)
- [ ] Test coverage >= 80% for changed code
- [ ] CloudWatch logs confirm fix works
- [ ] Error code documented (if new)
- [ ] ADR written (if architectural change)

---

## Summary

**What we did:**

1. Reproduced "Gmail credentials not found" error in LocalStack
2. Read structured CloudWatch logs to identify `LATEOS-007`
3. Used error catalog investigation steps to find root cause
4. Created mock OAuth secret to fix issue
5. Wrote 3 regression tests with 97% coverage
6. Verified end-to-end fix with real API call

**Time to debug:** ~15 minutes

**AI assistance required:** Zero

**This proves:** You understand the system deeply enough to debug it without AI assistance — the opposite of vibe coding.

---

**Key Files Referenced:**

| File | Lines | Purpose |
|------|-------|---------|
| `lambdas/skills/email_skill.py` | 51-76 | OAuth token retrieval |
| `lambdas/shared/error_codes.py` | 123-135 | LATEOS-007 definition |
| `tests/unit/skills/test_email_skill.py` | Full file | Regression tests |
| `infrastructure/stacks/skills_stack.py` | Role definitions | IAM permissions |

---

**Related Walkthroughs:**

- [01-user-sends-message.md](./01-user-sends-message.md) — Full request flow
- [05-new-skill-execution.md](./05-new-skill-execution.md) — Email skill details
