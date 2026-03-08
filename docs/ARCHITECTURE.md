# Lateos Architecture

## Design Philosophy

Lateos is built on a fundamental security-first principle: **Lambda functions do not listen.** There are no open ports, no admin panels exposed to the internet, no persistent processes that can be compromised. This design directly addresses the root cause of the January 2026 OpenClaw security crisis (also known as Clawdbot/Moltbot), where hundreds of instances leaked credentials because they ran as always-on services.

### Core Architectural Insights

1. **Serverless = No Persistent Attack Surface**: Every Lateos component is stateless and ephemeral. Lambdas invoke, execute, and terminate. There is no listener port, no daemon process, no admin panel — eliminating entire categories of attack vectors that plagued OpenClaw.

2. **Security by Default, Not Bolted On**: Rather than retrofitting security onto a monolithic service, security is baked into the architecture from the foundational layer:
   - Every Lambda has a dedicated, scoped IAM role (RULE 2)
   - User data isolation enforced at the partition key level (RULE 6)
   - Input and output sanitization built into the pipeline (RULES 5, 8)
   - Secrets only accessed via Secrets Manager at runtime (RULE 1)
   - Reserved concurrency limits prevent cost runaway (RULE 7)

3. **Cost-Aware and Observable**: Multi-layered cost protection prevents silent failure modes. Budgets alert at 80%, the kill switch triggers at 100%. Every action is logged to an encrypted audit trail. No blind spots.

## Stack Overview

Lateos is built as five independent AWS CDK stacks, each responsible for a specific security boundary:

| Stack | Purpose | Key Resources |
|-------|---------|---------------|
| **CoreStack** | API Gateway + Cognito authentication + KMS encryption | REST API, Cognito User Pool, CloudWatch Logs (encrypted) |
| **OrchestrationStack** | Step Functions + core request processing pipeline | Express Workflow, 5 core Lambdas (validator, orchestrator, classifier, router, sanitizer) |
| **SkillsStack** | Isolated skill execution with per-skill IAM roles | 4 skill Lambdas (email, calendar, web_fetch, file_ops), S3 files bucket |
| **MemoryStack** | DynamoDB tables with KMS encryption + per-user partitioning | 4 tables (conversations, agent_memory, audit_logs, user_preferences) |
| **CostProtectionStack** | AWS Budgets + CloudWatch alarms + kill switch Lambda | Budget alerts, SNS notifications, cost kill switch Lambda |

**Integration Model:** OrchestrationStack imports CoreStack and SkillsStack to wire the API Gateway → Step Functions → Skills pipeline. MemoryStack is imported by Lambdas via output exports. CostProtectionStack imports CoreStack to manage the API Gateway.

---

## CoreStack: API Gateway + Cognito

**File:** `/Users/leochong/Documents/projects/Lateos/infrastructure/stacks/core_stack.py`

### API Gateway Configuration

The REST API enforces three security layers at the ingress point:

**1. Throttling (Network Layer)**

- Rate limit: 100 requests/second
- Burst limit: 200 concurrent requests
- Enforced at API Gateway stage level

**2. Cognito Authentication (Identity Layer)**

- User Pool MFA enforcement (REQUIRED or OPTIONAL, configurable)
- SRP (Secure Remote Password) auth flow prevents credential interception
- OAuth 2.0 code grant for web clients
- Access token validity: 1 hour
- Refresh token validity: 30 days

**3. Request Validation (Data Layer)**

- RequestValidator validates all incoming JSON payloads
- Response format enforced via API method responses
- No public endpoints — all methods require Cognito authorization

**Code Reference (core_stack.py):**

- Lines 178-212: API Gateway RestApi with throttling and CORS
- Lines 216-222: CognitoUserPoolsAuthorizer (RULE 3)
- Lines 245-253: RequestValidator for input validation

### Cognito Security Configuration

**User Pool Policies (RULE 3: No public endpoints without authentication)**

- Self sign-up disabled (admin-only user creation)
- Email-based sign-in only (no username enumeration)
- Password policy: 16+ characters, mixed case, digits, symbols
- Temporary password validity: 1 day
- Advanced security mode: ENFORCED (anomaly detection)
- Account recovery: Email only

**Code Reference (core_stack.py):**

- Lines 120-146: UserPool with MFA and password policy

### CloudWatch Logs Encryption (RULE 8)

All API Gateway logs are encrypted with a customer-managed KMS key:

**Key Features:**

- Automatic key rotation enabled
- Regional key (no cross-region replication per ADR)
- Log retention: configurable (default 90 days)
- Removal policy: DESTROY in dev, RETAIN in prod

**Code Reference (core_stack.py):**

- Lines 53-85: KMS key creation with resource policy
- Lines 110-117: CloudWatch LogGroup with encryption

**Why KMS?** Customer-managed keys allow:

- Audit trail via CloudTrail for key usage
- Fine-grained IAM control over who can decrypt logs
- Compliance with encryption-at-rest requirements
- Instant revocation if needed

### WAF Deferral (ADR-011)

WAF v2 is implemented but disabled by default. The code exists (lines 255-334) but requires `waf_enabled: true` in `cdk.json`.

**Rationale (ADR-011):**

- WAF costs ~$8/month minimum (fixed Web ACL + rule charges)
- API Gateway throttling + Cognito provide adequate protection for Phase 1-4
- No public exposure until Phase 5 launch anyway
- Enabled by default in production, optional in dev

**When to Enable:**

- Before public GitHub release (Phase 5)
- Production deployments
- Any public-facing stage

---

## OrchestrationStack: Step Functions Pipeline

**File:** `/Users/leochong/Documents/projects/Lateos/infrastructure/stacks/orchestration_stack.py`

### Express Workflow Architecture (ADR-002)

Lateos uses **Step Functions Express Workflows** — not Standard Workflows.

**Why Express (ADR-002)?**

- Lower cost: $0.000001 per 100ms (vs. Standard: $0.25 per 1,000 state transitions)
- Perfect for short-duration chat workflows (~1-5 seconds)
- Capacity: 100,000 executions/second
- Billing: per-duration, not per-transition

**Tradeoff:** No built-in 90-day execution history. Lateos uses CloudWatch logs instead.

**Code Reference (orchestration_stack.py):**

- Lines 605-618: StateMachine definition with EXPRESS type

### Core Lambda Pipeline

The orchestration workflow is a 6-stage pipeline:

```
User Input
    ↓
[1. Validator] — Sanitize input, detect prompt injection (RULE 5)
    ↓
[2. Orchestrator] — Retrieve user context, conversation memory
    ↓
[3. Intent Classifier] — Determine user's intent (email, calendar, web, etc.)
    ↓
[4. Action Router] — Route to appropriate skill based on intent
    ↓
[5. Skill Lambda] — Execute skill (email_skill, calendar_skill, web_fetch_skill, file_ops_skill)
    ↓
[6. Output Sanitizer] — Redact secrets, apply Bedrock Guardrails (RULE 8)
    ↓
User Response
```

### Stage 1: Validator Lambda (RULE 5 - Prompt Injection Detection)

**Purpose:** Block or warn on suspected prompt injection attacks before the LLM sees the input.

**Threat Detection (ADR-014):**

- Scans for 15+ injection patterns: "ignore", "system", "ignore previous", "repeat back", "GPT", "instruction", etc.
- Threat Score = number of patterns detected
- Block if threat_score >= 2 (two or more patterns = deliberate attack)
- Warn if threat_score == 1 (possible false positive)

**Detection Code Reference (orchestration_stack.py):**

- Lines 152-172: Validator Lambda creation
- Line 157: Function description references RULE 5

**Why Threshold of 2?** Single patterns often appear legitimately ("Can you ignore the typo?" is not an injection). Two patterns together indicate deliberate attack.

### Stage 2: Orchestrator Lambda

**Purpose:** Enrich the request with user context and conversation memory.

**Actions:**

1. Fetch conversation history from DynamoDB (scoped to user_id)
2. Retrieve agent memory (short-term context for this session)
3. Build context object combining user preferences, conversation history, current request
4. Pass enriched context to intent classifier

**Data Flow:** Raw request → Context-enriched request

### Stage 3: Intent Classifier Lambda

**Purpose:** Determine what the user wants to do.

**Intents (Phase 2+):**

- `EMAIL_SEND` → email skill
- `CALENDAR_CREATE` → calendar skill
- `WEB_FETCH` → web_fetch skill
- `FILE_UPLOAD` → file_ops skill
- `GENERAL_CHAT` → fallback response

**Phase 1 Implementation:** Rule-based classifier (no LLM cost).
**Phase 3 Implementation:** Bedrock-based classifier (more natural language).

### Stage 4: Action Router Lambda

**Purpose:** Map classified intent to the correct skill Lambda.

**Logic:**

```
if intent == "EMAIL_SEND":
    skill = "email"
elif intent == "CALENDAR_CREATE":
    skill = "calendar"
elif intent == "WEB_FETCH":
    skill = "web_fetch"
elif intent == "FILE_UPLOAD":
    skill = "file_ops"
else:
    return "Skill not found"
```

### Stage 5: Skill Lambda (Dynamic Routing)

The Step Functions Choice state routes to the appropriate skill:

**Code Reference (orchestration_stack.py):**

- Lines 468-544: Choice state with skill routing conditions
- Each skill routing adds `.next(sanitize_output_task)` to pipeline

**Skill Execution Model:**

- Each skill Lambda runs in isolation with its own IAM role
- Skills cannot access each other's secrets or resources
- Timeout: 30-60 seconds per skill
- Memory: 512-1024 MB
- Reserved concurrency: 10-20 (prevents runaway costs)

### Stage 6: Output Sanitizer Lambda (RULE 8)

**Purpose:** Clean skill output before returning to user.

**Actions:**

1. **Secret Redaction:** Scan for API keys, tokens, passwords
   - Patterns: AWS key format, bearer tokens, OAuth patterns
   - Action: Replace with `[REDACTED]`
   - Log: LATEOS-006 in audit trail

2. **Bedrock Guardrails (ADR-015):** Apply content policy filtering
   - Blocks unsafe content, violence, PII exposure
   - Optional if Guardrails ID not configured (LocalStack compatible)
   - Cost: ~$0.001 per request

3. **Length Enforcement:** Prevent token explosion
   - Max response length: 4096 tokens
   - Action: Truncate with `[truncated]` suffix if exceeded

**Code Reference (orchestration_stack.py):**

- Lines 337-364: Output Sanitizer Lambda creation
- Lines 323-335: Bedrock Guardrails permission (optional)

**Why Output Layer (ADR-015)?**

- Catches both injection attacks and skill-generated harm
- Defense in depth: Pattern matching (input) + ML (output)
- Cost-optimized: Only ~1/1000th requests reach Guardrails vs. all requests

### Step Functions Execution Role (RULE 2)

**Code Reference (orchestration_stack.py):**

- Lines 367-420: StateMachine execution role with scoped permissions
- Lines 395-401: Lambda invocation scoped to specific function ARNs (not wildcard)

**Permissions Granted:**

- `lambda:InvokeFunction` only on these ARNs: validator, orchestrator, classifier, router, sanitizer, + skill Lambdas
- CloudWatch Logs permissions (required for Express Workflows logging)

---

## SkillsStack: Isolated Skill Execution

**File:** `/Users/leochong/Documents/projects/Lateos/infrastructure/stacks/skills_stack.py`

### Per-Skill IAM Role Model (ADR-016)

Each skill Lambda has a dedicated execution role with **minimum required permissions** only. This enforces RULE 2 (no wildcards) and prevents lateral movement.

**Architecture:**

```
Email Skill
├── Role: lateos-dev-email-skill
├── Can: Read lateos/dev/gmail/* secrets
├── Can: Write to audit_log table
└── Cannot: Access calendar secrets or other resources

Calendar Skill
├── Role: lateos-dev-calendar-skill
├── Can: Read lateos/dev/google_calendar/* secrets
├── Can: Write to audit_log table
└── Cannot: Access email secrets or other resources

Web Fetch Skill
├── Role: lateos-dev-web-fetch-skill
├── Can: Make HTTP requests (no AWS permissions)
├── Can: Write to audit_log table
└── Cannot: Access any secrets

File Ops Skill
├── Role: lateos-dev-file-ops-skill
├── Can: Read/write to S3 prefix lateos/dev/files/*
├── Can: Decrypt/encrypt with S3 bucket KMS key
├── Can: Write to audit_log table
└── Cannot: Access secrets or other S3 prefixes
```

### Email Skill (Gmail OAuth)

**Code Reference (skills_stack.py):**

- Lines 133-181: Email skill Lambda with scoped IAM role

**Permissions:**

```python
# Secrets Manager: Only Gmail OAuth secrets
arn:aws:secretsmanager:{region}:{account}:secret:lateos/{env}/gmail/*

# DynamoDB: Write audit logs only
arn:aws:dynamodb:{region}:{account}:table:lateos-{env}-audit-logs
```

**Security Model:**

- Gmail credentials stored in Secrets Manager
- Lambda fetches token at invocation start (warm cache for subsequent requests)
- Token refresh handled by Lambda (no credential exposure in logs)
- All email sends logged to audit table with timestamp and recipient

**Timeout:** 30 seconds
**Memory:** 512 MB
**Reserved Concurrency:** 10

### Calendar Skill (Google Calendar API)

**Code Reference (skills_stack.py):**

- Lines 183-230: Calendar skill Lambda

**Permissions:**

```python
# Secrets Manager: Only Google Calendar OAuth secrets
arn:aws:secretsmanager:{region}:{account}:secret:lateos/{env}/google_calendar/*

# DynamoDB: Write audit logs only
arn:aws:dynamodb:{region}:{account}:table:lateos-{env}-audit-logs
```

**Features:**

- Create, update, delete calendar events
- Check availability across calendars
- Handle timezone conversions
- All operations logged to audit table

### Web Fetch Skill

**Code Reference (skills_stack.py):**

- Lines 232-269: Web fetch skill Lambda

**Security Model (No Secrets Manager Access):**

- Makes HTTP/HTTPS requests to whitelisted domains
- Domain whitelist enforced in Lambda code (not IAM)
- Prevents SSRF attacks (Server-Side Request Forgery)
- Cannot access any AWS credentials
- User-configurable domain allowlist (stored in agent_memory table)

**Timeout:** 60 seconds (longer for HTTP roundtrip)
**Memory:** 512 MB
**Reserved Concurrency:** 20 (higher due to network I/O)

### File Operations Skill

**Code Reference (skills_stack.py):**

- Lines 271-340: File ops skill Lambda

**S3 Bucket Configuration:**

- Bucket name: `lateos-{env}-files`
- Encryption: KMS (customer-managed)
- Public access: BLOCKED (Block All)
- Versioning: ENABLED
- User isolation: S3 prefix `/lateos/{env}/files/{user_id}/*`

**Permissions:**

```python
# S3: Access only user-specific prefix
s3:GetObject, s3:PutObject, s3:DeleteObject, s3:ListBucket
on: lateos-{env}-files with prefix lateos/{env}/files/{user_id}/*

# KMS: Decrypt/encrypt with S3 key
kms:Decrypt, kms:GenerateDataKey
on: S3 bucket encryption key

# DynamoDB: Write audit logs only
arn:aws:dynamodb:{region}:{account}:table:lateos-{env}-audit-logs
```

**User Isolation Enforcement:**

- Lambda always uses Cognito user_id from request context
- All S3 operations prefixed with `lateos/{env}/files/{user_id}/`
- IAM policy enforces this prefix constraint (defense in depth)
- Cannot access other users' files even with malicious intent

**Timeout:** 60 seconds
**Memory:** 1024 MB (larger files require more processing)
**Reserved Concurrency:** 15

---

## MemoryStack: Data Isolation

**File:** `/Users/leochong/Documents/projects/Lateos/infrastructure/stacks/memory_stack.py`

### Four DynamoDB Tables (RULE 6: Per-User Partition Isolation)

Every table uses `user_id` as the partition key. This enforces data isolation at the database level — even a vulnerable Lambda cannot cross-query another user's data.

#### 1. Conversation History Table

**Table Name:** `lateos-{env}-conversations`

**Schema:**

```
Partition Key: user_id (String)
Sort Key:     conversation_id (String)
TTL:          ttl (automatic cleanup)
Encryption:   KMS (customer-managed)
```

**Indexes:**

- `UserTimestampIndex` — GSI for querying by user + timestamp (analytics)

**Data Stored:**

- Full conversation history with timestamps
- Message author (user or assistant)
- Metadata: intent, skill executed, cost

**Example Query:**

```python
# Always scoped to authenticated user_id
response = dynamodb.query(
    TableName='lateos-dev-conversations',
    KeyConditionExpression='user_id = :uid AND conversation_id > :cid',
    ExpressionAttributeValues={
        ':uid': cognito_sub,  # From Cognito token
        ':cid': 'conv-'
    }
)
```

**TTL:** Configurable (default: None — keep indefinitely)

#### 2. Agent Memory Table

**Table Name:** `lateos-{env}-agent-memory`

**Schema:**

```
Partition Key: user_id (String)
Sort Key:     memory_key (String)
TTL:          ttl (automatic cleanup)
Encryption:   KMS (customer-managed)
```

**Purpose:** Short-term working memory for the current session.

**Data Stored:**

- Current conversation context (summary)
- User preferences (language, timezone)
- Task state (multi-turn conversations)
- Active reminders or pending actions

**TTL:** 24 hours (session-based cleanup)

**Why Separate from Conversations?** Memory is ephemeral and session-specific. Conversations are persistent and audit-relevant.

#### 3. Audit Log Table

**Table Name:** `lateos-{env}-audit-logs`

**Schema:**

```
Partition Key: user_id (String)
Sort Key:     timestamp (String, ISO-8601)
Encryption:   KMS (customer-managed)
Streams:      NEW_IMAGE (enable downstream processing)
```

**Indexes:**

- `ActionTypeIndex` — GSI for querying by action_type + timestamp (compliance reports)

**Data Logged (RULE 8: No Plaintext Secrets):**

```json
{
  "user_id": "cognito-sub-hash",
  "timestamp": "2026-02-28T14:32:15Z",
  "request_id": "req-uuid",
  "action": "EMAIL_SEND|CALENDAR_CREATE|WEB_FETCH|FILE_UPLOAD",
  "skill": "email|calendar|web_fetch|file_ops",
  "intent_confidence": 0.98,
  "duration_ms": 1234,
  "status": "success|failed",
  "error_code": "LATEOS-007|null",
  "redacted_output": true,
  "metadata": { ... }
}
```

**Never Logged:**

- API keys, OAuth tokens, passwords
- User private data
- LLM prompts (too much PII risk)
- Skill outputs (logged separately, redacted)

**Removal Policy:** RETAIN (production compliance requirement)
**TTL:** None (audit logs are permanent)

#### 4. User Preferences Table

**Table Name:** `lateos-{env}-user-preferences`

**Schema:**

```
Partition Key: user_id (String)
Encryption:   KMS (customer-managed)
```

**Data Stored:**

- Default time zone
- Preferred language
- Skill configurations (email account, calendar)
- Notification preferences
- API quotas per skill

**Example:**

```json
{
  "user_id": "cognito-sub",
  "timezone": "America/New_York",
  "language": "en-US",
  "email_account": "user@gmail.com",
  "calendar_id": "primary",
  "web_fetch_domains": ["github.com", "docs.aws.amazon.com"],
  "email_signature": "Best,\nAlice"
}
```

### KMS Encryption (RULE 8)

All four tables use the same customer-managed KMS key:

**Code Reference (memory_stack.py):**

- Lines 54-61: KMS key creation
- Lines 77-78, 112-113, 133-134, 164-165: Table encryption configuration

**Key Features:**

- Automatic key rotation enabled
- Regional key (no cross-region replication)
- Key policy allows DynamoDB service principal to use it
- Separate keys per stack (CoreStack, OrchestrationStack, MemoryStack, SkillsStack)

**Why Separate Keys?** Blast radius containment. If one key is compromised, the blast radius is limited to that stack's resources. Also prevents circular dependencies in CDK.

### Point-in-Time Recovery (PITR)

**Code Reference (memory_stack.py):**

- Lines 79, 114, 135, 166: `point_in_time_recovery` enabled on all tables

**Capability:**

- Restore any table to any moment in the last 35 days
- Automatic daily backups
- No cost for PITR (included in on-demand billing)
- Compliance requirement for audit logs

### TTL (Time-To-Live) Strategy

**Conversation Table:** TTL = None (keep permanently for history)
**Agent Memory Table:** TTL = 86400 seconds (24 hours, auto-cleanup)
**Audit Log Table:** TTL = None (compliance requirement)
**User Preferences Table:** TTL = None (configuration is long-lived)

---

## CostProtectionStack: Kill Switch

**File:** `/Users/leochong/Documents/projects/Lateos/infrastructure/stacks/cost_protection_stack.py`

### Cost Control Model

Lateos implements **three layers of cost protection**, each with escalating severity:

**Layer 1: Budgets Alert (80% threshold)**

- Triggers SNS notification
- No action taken (informational only)
- Alert message includes cost breakdown

**Layer 2: CloudWatch Alarm (80% threshold)**

- Metric: EstimatedCharges from AWS Billing
- Triggers SNS notification
- More immediate than Budgets (updates every 6 hours)

**Layer 3: Kill Switch Lambda (100% threshold)**

- Triggered via SNS
- **Disables the entire API Gateway**
- Sends critical SNS alert
- Prevents further costs from runaway execution

### AWS Budgets Configuration

**Code Reference (cost_protection_stack.py):**

- Lines 246-290: Budget with alert subscribers

**Configuration:**

```
Budget Type:        COST
Time Unit:          MONTHLY
Budget Limit:       $10 (configurable via cdk.json)
Alert 1 (80%):      SNS notification
Alert 2 (100%):     SNS notification + kill switch trigger
Comparison:         ACTUAL (not forecasted)
```

### Kill Switch Lambda

**Code Reference (cost_protection_stack.py):**

- Lines 131-233: Kill switch Lambda implementation

**Execution:**

1. Triggered by CloudWatch alarm at 100% budget
2. Retrieves API Gateway configuration
3. Updates API Gateway description field with "DISABLED BY COST KILL SWITCH" prefix
4. Sends critical SNS notification to admin
5. Logs to CloudWatch with log retention of 1 year (audit trail)

**Security:**

- Reserved concurrency: 1 (only one invocation at a time)
- Scoped IAM role (can only modify our API Gateway)
- Permission to publish to SNS topic only
- Cannot modify other AWS services

**Permissions (RULE 2):**

```python
apigateway:PATCH, apigateway:GET
on: arn:aws:apigateway:region::/restapis/{api-id}/*

sns:Publish
on: arn:aws:sns:region:account:lateos-env-cost-alerts
```

### Cost Alert Topic (SNS)

**Code Reference (cost_protection_stack.py):**

- Lines 69-79: SNS topic creation

**Subscriptions:**

- Pre-configured for CloudWatch alarms
- Manual email subscription required in production
- SMS subscriptions optional for critical alerts

**Message Format:**

```
From: CloudWatch Alarm
Subject: [CRITICAL] Lateos Kill Switch Activated - {environment}

Body:
CRITICAL: Lateos Cost Kill Switch Activated

Environment: dev
API Gateway: {api-id}
Status: DISABLED

The monthly budget threshold has been exceeded.
API Gateway has been disabled to prevent further costs.

Action Required:
1. Review AWS Cost Explorer for cost breakdown
2. Investigate unexpected usage patterns
3. Re-enable API Gateway manually after review
```

### Metrics and Alarms

**Code Reference (cost_protection_stack.py):**

- Lines 293-314: CloudWatch Alarm for EstimatedCharges

**Alarm Configuration:**

```
Metric:             AWS/Billing::EstimatedCharges
Namespace:          AWS/Billing
Dimensions:         Currency=USD
Statistic:          Maximum
Period:             6 hours
Threshold:          80% of monthly budget
Comparison:         GREATER_THAN_THRESHOLD
Evaluation Periods: 1 (trigger on first breach)
Treat Missing Data: NOT_BREACHING (don't alarm if no data)
```

---

## Security Layers (Mapping to RULE 1-8)

Each security rule is enforced by multiple architectural components:

### RULE 1: No Secrets in Code

**Enforcement:**

- Secrets Manager only (no env vars in Lambda code)
- Fetch at module level (warm invocation cache)
- Scoped IAM policies per skill (email skill can only access gmail secrets)
- Pre-commit hook: `detect-secrets` scans all commits

**Code Reference:**

- `skills_stack.py` Lines 140-146: Email skill can only read `lateos/{env}/gmail/*` secrets
- `skills_stack.py` Lines 189-195: Calendar skill can only read `lateos/{env}/google_calendar/*` secrets

### RULE 2: No Wildcard IAM Policies

**Enforcement:**

- Every Lambda has a dedicated role (ADR-016)
- Every role has explicit ARN-scoped permissions
- No `Resource: "*"` except where AWS requires it (X-Ray, CloudWatch Logs)
- Pre-deploy check: `cdk-nag` scans for wildcards and suppressions require justification

**Code Reference:**

- `orchestration_stack.py` Lines 395-401: StateMachine role scoped to specific Lambda ARNs
- `skills_stack.py` Lines 285-296: File ops role scoped to user-specific S3 prefix
- `skills_stack.py` Lines 140-146: Email role scoped to gmail secrets only

### RULE 3: No Public Endpoints Without Cognito

**Enforcement:**

- API Gateway authorizer = Cognito User Pool (mandatory)
- All methods require Authorization header
- CORS policy restricted to `https://*.lateos.app` (not wildcard `*`)
- WAF optional in Phase 1, mandatory before public launch (ADR-011)

**Code Reference:**

- `core_stack.py` Lines 216-222: CognitoUserPoolsAuthorizer on all endpoints
- `core_stack.py` Lines 206-211: CORS restricted to lateos.app domain
- `core_stack.py` Lines 255-334: WAF implementation (disabled by default per ADR-011)

### RULE 4: No Shell Execution

**Enforcement:**

- No `os.system()`, `subprocess`, `eval()`, `exec()` in any Lambda
- Static code analysis: `bandit -r lambdas/` in CI/CD
- Code reviews mandatory for any system-level operations
- Fallback: Implement features in safe libraries (boto3, requests, json)

**Code Example (What NOT to do):**

```python
# BANNED
import subprocess
output = subprocess.run(['ls', '-la'], capture_output=True)  # RCE vector

# ALLOWED
import boto3
s3 = boto3.client('s3')
response = s3.list_objects_v2(Bucket='my-bucket')  # Safe, no shell
```

### RULE 5: Prompt Injection Detection

**Enforcement:**

- Validator Lambda scans all user input (stage 1 of pipeline)
- Threat scoring: 2+ patterns detected = block
- Bedrock Guardrails applied to output (stage 6 of pipeline)
- All blocked attempts logged to audit table

**Code Reference:**

- `orchestration_stack.py` Lines 152-172: Validator Lambda
- `orchestration_stack.py` Lines 423-429: Validator task in Step Functions

**ADR-014 Details:**

- 15+ injection patterns: "ignore", "system", "instruction", "repeat back", etc.
- Threat Score = count of detected patterns
- Score >= 2: Block with LATEOS-001 error
- Score == 1: Log warning, allow request
- All blocked requests sent to audit table

### RULE 6: Per-User Data Isolation

**Enforcement:**

- DynamoDB partition key = `user_id` (from Cognito token)
- Every query filters by user_id (application level + IAM level)
- File ops skill S3 prefix enforced: `lateos/{env}/files/{user_id}/*`
- IAM policies on S3 prevent cross-user access

**Code Reference:**

- `memory_stack.py` Lines 68-82: Conversation table with user_id partition key
- `memory_stack.py` Lines 103-117: Agent memory table with user_id partition key
- `memory_stack.py` Lines 124-138: Audit log table with user_id partition key
- `skills_stack.py` Lines 285-296: File ops role scoped to user prefix

**Query Example (Safe):**

```python
# Correct — always scoped to user
response = dynamodb.query(
    TableName='lateos-dev-conversations',
    KeyConditionExpression='user_id = :uid AND ...',
    ExpressionAttributeValues={':uid': request.context.user_id}  # From Cognito
)

# WRONG — would be blocked by IAM or filtered at application
response = dynamodb.scan(TableName='lateos-dev-conversations')  # No filter!
```

### RULE 7: Reserved Concurrency

**Enforcement:**

- Every Lambda has `reserved_concurrent_executions` set
- Prevents runaway cost from infinite loops or attacks
- Forces explicit scaling decisions
- Tuned based on expected traffic and cost per invocation

**Code Reference:**

- `orchestration_stack.py` Line 106: Orchestrator: 10 concurrent
- `orchestration_stack.py` Line 163: Validator: 10 concurrent
- `orchestration_stack.py` Line 220: Intent classifier: 10 concurrent
- `orchestration_stack.py` Line 277: Action router: 10 concurrent
- `orchestration_stack.py` Line 350: Output sanitizer: 10 concurrent
- `skills_stack.py` Line 169: Email skill: 10 concurrent
- `skills_stack.py` Line 218: Calendar skill: 10 concurrent
- `skills_stack.py` Line 257: Web fetch skill: 20 concurrent (I/O bound)
- `skills_stack.py` Line 327: File ops skill: 15 concurrent

**Concurrency Budget:**

```
Total reserved: 10+10+10+10+10 + (10+10+20+15) = 125 concurrent
Cost at Lambda pricing: ~0.0000166667 per GB-second
At 128 MB per Lambda = 1GB * 125 seconds = $0.002 per second max
Worst case (100% utilization): ~$7/month
Budget threshold: $10/month → Plenty of headroom
```

### RULE 8: No Plaintext Logging of Secrets

**Enforcement:**

- All logs structured JSON via AWS Lambda Powertools
- Sensitive fields (tokens, keys, PII) redacted manually or via patterns
- CloudWatch logs encrypted with KMS
- Output sanitizer redacts secrets before returning to user

**Code Reference:**

- `core_stack.py` Lines 53-85: CloudWatch log encryption with KMS
- `memory_stack.py` Lines 54-61: DynamoDB key encryption
- `orchestration_stack.py` Lines 561-594: Step Functions log encryption with separate KMS key

**Logging Pattern (Safe):**

```python
from aws_lambda_powertools import Logger

logger = Logger()

# Correct — structured log with field redaction
logger.info(
    "Email sent successfully",
    extra={
        "recipient": "user@example.com",  # Safe (not sensitive)
        "status": "delivered",
        "timestamp": "2026-02-28T14:32:15Z"
        # Note: OAuth token NOT in logs
    }
)

# WRONG — plaintext secrets in logs
logger.info(f"Gmail token: {oauth_token}")  # DANGEROUS
print(f"API key: {api_key}")  # DANGEROUS — also uses print()
```

---

## Local Development Architecture (LocalStack)

### How LocalStack Emulates AWS Locally

Lateos is designed to work with **LocalStack** for Phase 1-4 development:

```
LocalStack Container (Docker)
├── API Gateway → :4566 (mocked)
├── Cognito → :4566 (mocked)
├── Lambda → :4566 (mocked, uses Docker-in-Docker)
├── Step Functions → :4566 (mocked)
├── DynamoDB → :4566 (mocked, in-memory)
├── Secrets Manager → :4566 (mocked)
├── S3 → :4566 (mocked, file-backed)
├── CloudWatch → :4566 (mocked, logged to stdout)
└── KMS → :4566 (mocked, encrypts locally)

Local Development Machine
├── AWS CLI (configured for LocalStack endpoint)
├── Python 3.12 venv
├── CDK app
├── Pytest (with moto mocks for unit tests)
└── Docker (runs LocalStack + Lambda execution)
```

### Docker Compose Configuration

**File:** `docker-compose.yml` (assumed to exist)

```yaml
version: '3.8'
services:
  localstack:
    image: localstack/localstack:latest
    ports:
      - "4566:4566"
    environment:
      - SERVICES=apigateway,cognito-idp,lambda,stepfunctions,dynamodb,secretsmanager,s3,cloudwatch,kms
      - DEBUG=1
      - DATA_DIR=/tmp/localstack/data
      - DOCKER_HOST=unix:///var/run/docker.sock
    volumes:
      - "${TMPDIR}/.localstack:/tmp/localstack"
      - "/var/run/docker.sock:/var/run/docker.sock"
```

### Deployment to LocalStack

```bash
# 1. Start LocalStack
docker-compose up -d localstack

# 2. Configure AWS CLI for LocalStack
aws configure --profile localstack
# Access Key: test
# Secret Key: test
# Region: us-east-1
# Output: json

# 3. Deploy CDK to LocalStack
export AWS_PROFILE=localstack
export AWS_ENDPOINT_URL=http://localhost:4566
cdk deploy --all

# 4. Test API Gateway
curl -X POST http://localhost:4566/restapis/{api-id}/test/_user_request/agent \
  -H "Content-Type: application/json" \
  -d '{"message": "What is 2+2?"}'

# 5. View logs in LocalStack container
docker logs -f localstack
```

### Differences from Real AWS

**LocalStack Limitations (ADR-007):**

- Cognito authentication is mocked (not full OAuth flow)
- Lambda cold starts are faster (no real AWS overhead)
- Network latency not simulated
- Some advanced features require LocalStack Pro

**Workarounds:**

- Unit tests use moto (Cognito mocking)
- Integration tests use real AWS (Phase 5+)
- LocalStack Pro for Bedrock, Guardrails emulation (optional)

---

## What We Deliberately Did NOT Build (and Why)

### 1. WebSocket API (NOT built - intentionally avoided)

**What it is:** Long-lived bidirectional connection for real-time chat.

**Why we rejected it:**

- Persistent connections = persistent attack surface
- Requires managing connection state (where? DynamoDB? memory?)
- Complex to scale (sticky sessions, connection affinity)
- Higher cost than request-response model
- Clawdbot used WebSockets extensively — attack vector we want to avoid

**Lateos Alternative:** Request-response only (HTTP/HTTPS)

- User sends message → API Gateway → Step Functions → Response
- If real-time needed (Phase 7+): Implement client-side polling

### 2. Community Skill Marketplace / ClawHub (NOT built)

**What it is:** User-submitted custom skills (like Clawdbot's plugin system).

**Why we rejected it:**

- ClawHub had 20% malicious packages (documented in Clawdbot postmortem)
- Supply chain attack vector: malicious skill could steal credentials
- Requires code signing, vetting, automated testing — too complex for Phase 1
- Skill isolation would still be hard to enforce with untrusted code

**Lateos Alternative:** Controlled skill set (Phase 1-5)

- Email, Calendar, Web Fetch, File Ops — all implemented by Lateos maintainers
- No community contributions until Phase 7+ (with full security review)
- Skills are statically linked (no dynamic loading)

### 3. Container-Based Deployment (NOT considered)

**What it is:** ECS/Fargate instead of Lambda.

**Why we rejected it:**

- Containers are persistent processes (running 24/7)
- Persistent = persistent attack surface
- Clawdbot ran in containers — that's the problem we're solving
- Cost: ~$35/month minimum for Fargate, vs. ~$0.20/month for Lambda
- Cold starts not an issue for chat (humans are slow)

**Lateos Design:** Pure Lambda (ephemeral)

- Invoke → Execute → Terminate
- No persistent admin panel, no daemon, no listener port

### 4. DynamoDB Global Tables (NOT built)

**What it is:** Multi-region replication for disaster recovery.

**Why we rejected it:**

- Increases attack surface (more endpoints, more replication lag)
- Cross-region replication introduces consistency issues
- Not needed for MVP (single-region is fine)
- Can be added in Phase 6+ if demand exists

**Lateos Strategy:** Single-region (us-east-1)

- Deploy to additional regions post-launch if needed
- PITR (Point-in-Time Recovery) handles disaster recovery for now

### 5. Browser Control / Autonomous Web Automation (NOT built)

**What it is:** Automated browser (Selenium, Playwright) for web interaction.

**Why we rejected it (ADR-017 — incomplete):**

- Full computer control = Clawdbot's root attack surface
- Browser automation can be exploited to visit malicious sites, exfiltrate data
- Better solved with HITL (Human-In-The-Loop) approval gates (Phase 7)
- Web Fetch skill is safer alternative (fetch + parse, no execution)

**Lateos Alternative:** Web Fetch skill

- Fetch HTML, parse, return structured data
- No script execution, no cookie theft, no DOM manipulation

### 6. Model Fine-Tuning (NOT built)

**What it is:** Train custom LLM on Lateos-specific tasks.

**Why we rejected it:**

- Requires large labeled dataset (we don't have one yet)
- Bedrock API provides sufficient quality for MVP
- Fine-tuning adds operational complexity (retraining, versioning)
- Cost-prohibitive for MVP phase

**Lateos Strategy:** Prompt engineering + Guardrails

- Optimize prompts for Bedrock Claude 3
- Use Bedrock Guardrails for safety
- Switch to fine-tuning if needed post-launch

### 7. Kubernetes Orchestration (NOT built)

**What it is:** EKS for container orchestration.

**Why we rejected it:**

- Kubernetes = persistent infrastructure (cluster always running)
- Operational overhead (patching, node management, security groups)
- Overkill for Lambda-based workloads
- Another attack surface (Kubernetes API, RBAC misconfiguration)

**Lateos Design:** No Kubernetes

- Lambda is the orchestration platform
- Step Functions provides state machine orchestration
- No cluster to manage

---

## Future: WAF v2 (Phase 2, Deferred per ADR-011)

### Why Deferred

WAF (Web Application Firewall) is a powerful security tool but adds cost:

- Web ACL: ~$5.00/month
- Rule charges: ~$1.00/month per rule
- Total minimum: ~$8/month

For Phase 1-4 (local development), this cost is unjustified when:

- Cognito authentication protects public access
- API Gateway throttling (100 req/sec) prevents brute force
- Input validation blocks basic attacks
- No public exposure until Phase 5 anyway

### Planned Deployment (Phase 2)

When we go public, WAF will be enabled with these rules:

**Code Reference (ready but disabled):**

- `core_stack.py` Lines 255-334: WAF implementation
- Lines 48-50: `waf_enabled` flag (default False)

**Rules to Enable:**

1. **AWS Managed Rules - Core Rule Set**
   - OWASP Top 10 coverage
   - SQL injection, XSS, command injection detection

2. **AWS Managed Rules - Known Bad Inputs**
   - Log4Shell, Log4j scanner
   - Known vulnerability patterns

3. **Rate Limiting**
   - 100 requests per 5 minutes per IP
   - Blocks obvious DDoS attempts

**Production Enablement:**

```bash
# Before public GitHub release
cdk deploy --context waf_enabled=true
```

---

## ADR References

Key architectural decisions documented in DECISIONS.md:

| ADR | Decision | Status |
|-----|----------|--------|
| ADR-001 | Use Bedrock instead of direct OpenAI/Anthropic | Accepted |
| ADR-002 | Express Workflows instead of Standard Step Functions | Accepted |
| ADR-003 | DynamoDB on-demand instead of provisioned | Accepted |
| ADR-004 | MIT License | Accepted |
| ADR-005 | Python 3.12 for Lambda runtime | Accepted |
| ADR-006 | AWS CDK v2 instead of SAM/Terraform | Accepted |
| ADR-007 | LocalStack for local development | Accepted |
| ADR-008 | Reserved concurrency on all Lambdas | Accepted |
| ADR-009 | No shell execution in Lambdas | Accepted |
| ADR-010 | Multi-agent model selection (Haiku/Sonnet/Opus) | Accepted |
| ADR-011 | Defer WAF to Phase 2 | Accepted |
| ADR-012 | Domain: lateos.ai (Cloudflare) | Accepted |
| ADR-013 | Python 3.12 pin (JSII incompatibility) | Accepted |
| ADR-014 | Prompt injection threat threshold (2+ patterns) | Accepted |
| ADR-015 | Bedrock Guardrails on output layer | Accepted |
| ADR-016 | Per-skill IAM roles (one per Lambda) | Accepted |

Full details in `/Users/leochong/Documents/projects/Lateos/DECISIONS.md`

---

## Summary: Architecture in Three Bullet Points

1. **Serverless by Default**: No persistent processes, no listening ports, no admin panels. Every request is stateless and ephemeral. Lambda invokes, executes, terminates.

2. **Security at Every Layer**: Input validation (prompt injection), isolated execution (per-skill IAM roles), data isolation (per-user partition keys), output sanitization (secret redaction), and cost protection (kill switch).

3. **Observable and Auditable**: Every action logged to encrypted DynamoDB audit table with KMS encryption. CloudTrail tracks all API calls. X-Ray traces all requests. CloudWatch alarms alert on anomalies. Designed for incident response and compliance.
