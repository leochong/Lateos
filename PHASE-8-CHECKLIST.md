# Phase 8 - Post-Deployment Validation & Monitoring

**Phase:** 8
**Status:** IN PROGRESS
**Started:** 2026-03-07
**Target Completion:** TBD

---

## 🎯 Phase Overview

Validate production AWS deployment (account 080746528746) and ensure all infrastructure is operational, secure, and ready for real-world usage.

**Deployment Details:**
- AWS Account: 080746528746
- IAM User: Lateos-Admin
- Profile: lateos-prod
- Region: me-central-1
- Deployed: 2026-03-05 19:15-19:22 UTC
- Stacks: 5/5 CREATE_COMPLETE
- Lambdas: 10 functions deployed
- Tables: 4 DynamoDB tables

---

## ✅ Phase 8 Checklist

### 🔴 Critical Priority - Core Functionality

#### Task 1: Integration Tests Against Production
- [ ] Configure test environment for production AWS
  - [ ] Set AWS_PROFILE=lateos-prod in test config
  - [ ] Update test fixtures with production resource ARNs
  - [ ] Configure Bedrock permissions for test execution
- [ ] Run infrastructure tests against production
  - [ ] `pytest tests/infrastructure/ -v --aws-env=prod`
  - [ ] Verify all stacks exist and are CREATE_COMPLETE
  - [ ] Validate resource tags and naming conventions
- [ ] Run integration tests against production
  - [ ] `pytest tests/integration/ -v --aws-env=prod`
  - [ ] Test Lambda invocations
  - [ ] Test DynamoDB read/write operations
  - [ ] Verify IAM permissions are scoped correctly
- [ ] Run security tests against production
  - [ ] `pytest tests/security/ -v --aws-env=prod`
  - [ ] Validate all 21 prompt injection patterns blocked
  - [ ] Test cross-user data isolation
  - [ ] Verify secret redaction in logs
- [ ] Document test results
  - [ ] Pass/fail counts
  - [ ] Execution time
  - [ ] Any failures or warnings

**Acceptance Criteria:**
- ✅ 90%+ tests passing (some may require secrets setup)
- ✅ Zero security test failures
- ✅ All Lambda functions invocable

---

#### Task 2: API Gateway + Cognito Authentication Flow
- [ ] Create test user in Cognito User Pool
  - [ ] Pool ID: us-east-1_wXBwAxBod
  - [ ] Client ID: 25agb4frh560e49jmj2lvmln4s
  - [ ] Username: test-user@lateos.local
  - [ ] Enable MFA
- [ ] Test authentication flow
  - [ ] Sign up new user
  - [ ] Confirm email verification
  - [ ] Test MFA setup and verification
  - [ ] Generate access token and ID token
  - [ ] Test token refresh
- [ ] Test API Gateway with authentication
  - [ ] Make POST request to /agent endpoint with valid token
  - [ ] Verify 200 response with valid request
  - [ ] Test 401 response with invalid token
  - [ ] Test 403 response with expired token
  - [ ] Test 429 response (rate limiting)
- [ ] Test request validation
  - [ ] Valid request payload accepted
  - [ ] Invalid payload rejected (400 error)
  - [ ] Large payload rejected (413 error)
- [ ] Document authentication process
  - [ ] Capture example curl commands
  - [ ] Document token structure
  - [ ] Create user management guide

**Acceptance Criteria:**
- ✅ User can authenticate and get valid tokens
- ✅ API Gateway enforces Cognito authentication
- ✅ Request validation working correctly
- ✅ Rate limiting active

**API Endpoint:**
```
https://sys7fksdeg.execute-api.us-east-1.amazonaws.com/prod/
```

---

#### Task 3: Step Functions Workflow with Real Bedrock
- [ ] Get Step Functions state machine ARN
  - [ ] `aws stepfunctions list-state-machines --profile lateos-prod`
  - [ ] Confirm lateos-prod-orchestration exists
- [ ] Test workflow execution with simple request
  - [ ] Start execution with test payload
  - [ ] Monitor execution status
  - [ ] Verify all states execute successfully
  - [ ] Check execution history
- [ ] Test with real Bedrock API call
  - [ ] Verify Bedrock permissions configured
  - [ ] Test prompt: "Hello, what can you help me with?"
  - [ ] Validate validator Lambda blocks injection attempts
  - [ ] Verify orchestrator invokes Bedrock correctly
  - [ ] Check output sanitizer redacts secrets
- [ ] Test skill routing
  - [ ] Request: "Send an email to test@example.com"
  - [ ] Verify intent classifier identifies email intent
  - [ ] Verify action router invokes email skill Lambda
  - [ ] Check conversation stored in DynamoDB
- [ ] Test error handling
  - [ ] Invalid input (should fail at validator)
  - [ ] Bedrock throttling (should retry)
  - [ ] Skill execution failure (should log and return error)
- [ ] Document workflow execution patterns
  - [ ] Average execution time
  - [ ] Token usage per request
  - [ ] Error rates by state

**Acceptance Criteria:**
- ✅ Workflow executes end-to-end successfully
- ✅ Bedrock integration working
- ✅ All states transition correctly
- ✅ Error handling and retries functional

---

### 🟡 High Priority - Operational Validation

#### Task 4: CloudWatch Logs + X-Ray Tracing
- [ ] Verify CloudWatch log groups exist
  - [ ] `/aws/lambda/lateos-prod-*` (10 log groups)
  - [ ] `/aws/apigateway/lateos-prod-api`
  - [ ] `/aws/states/lateos-prod-orchestration`
- [ ] Check Lambda execution logs
  - [ ] Review logs for each Lambda function
  - [ ] Verify structured logging format (JSON)
  - [ ] Check for errors, warnings, or stack traces
  - [ ] Validate secret redaction (RULE 8)
- [ ] Verify log encryption
  - [ ] Confirm KMS key used for encryption
  - [ ] Key ARN: (from LateosCoreProdStack outputs)
- [ ] Test X-Ray tracing
  - [ ] Enable X-Ray for Lambda functions (if not already)
  - [ ] Make API request and view trace
  - [ ] Verify all services appear in service map
  - [ ] Check latency metrics for each service
- [ ] Set up log insights queries
  - [ ] Query for errors: `fields @timestamp, @message | filter @message like /ERROR/`
  - [ ] Query for injection attempts blocked
  - [ ] Query for high-latency requests (>3s)
- [ ] Document logging patterns
  - [ ] Log retention policy (90 days per cdk.json)
  - [ ] Log format and structure
  - [ ] Common queries for troubleshooting

**Acceptance Criteria:**
- ✅ All log groups active and receiving data
- ✅ Logs are encrypted with KMS
- ✅ No secrets visible in logs
- ✅ X-Ray traces show complete request flow

---

#### Task 5: Cost Protection & Budget Alerts
- [ ] Verify AWS Budget created
  - [ ] `aws budgets describe-budgets --account-id 080746528746 --profile lateos-prod`
  - [ ] Budget name: lateos-prod-monthly-budget
  - [ ] Limit: $20/month (or value from cdk.json)
- [ ] Check budget alert configuration
  - [ ] Alert at 80% threshold
  - [ ] Alert at 100% threshold
  - [ ] SNS topic subscribed for alerts
- [ ] Verify killswitch Lambda
  - [ ] Function: lateos-prod-killswitch
  - [ ] Check IAM permissions to disable API Gateway
  - [ ] Review Lambda code for disable logic
- [ ] Test budget alert flow (non-destructive)
  - [ ] Check SNS topic subscriptions
  - [ ] Verify email/SMS configured for alerts
  - [ ] Review CloudWatch alarm for estimated charges
- [ ] Check current AWS costs
  - [ ] `aws ce get-cost-and-usage --profile lateos-prod --time-period Start=2026-03-05,End=2026-03-07 --granularity DAILY --metrics BlendedCost`
  - [ ] Review Cost Explorer for service breakdown
  - [ ] Estimate monthly run rate
- [ ] Document cost protection system
  - [ ] How to manually trigger killswitch
  - [ ] How to re-enable after killswitch
  - [ ] Cost monitoring best practices

**Acceptance Criteria:**
- ✅ AWS Budget configured and active
- ✅ SNS alerts configured
- ✅ Killswitch Lambda can disable API Gateway
- ✅ Current costs within expected range

---

#### Task 6: Per-Skill Lambda Testing
- [ ] Test Email Skill (lateos-prod-email-skill)
  - [ ] Invoke directly with test payload
  - [ ] Verify Gmail OAuth integration (requires secrets)
  - [ ] Test send email functionality
  - [ ] Test read email functionality
  - [ ] Test search email functionality
  - [ ] Check CloudWatch logs for execution
  - [ ] Verify IAM role scoped to SES/Gmail only
- [ ] Test Calendar Skill (lateos-prod-calendar-skill)
  - [ ] Invoke directly with test payload
  - [ ] Verify Google Calendar API integration (requires secrets)
  - [ ] Test create event functionality
  - [ ] Test list events functionality
  - [ ] Test update event functionality
  - [ ] Test delete event functionality
  - [ ] Verify IAM role scoped to Calendar API only
- [ ] Test Web Fetch Skill (lateos-prod-web-fetch-skill)
  - [ ] Invoke with test URL (whitelisted domain)
  - [ ] Test HTTP GET request
  - [ ] Test domain whitelist enforcement
  - [ ] Test rate limiting (max requests per minute)
  - [ ] Verify IAM role has no S3/DynamoDB access
- [ ] Test File Operations Skill (lateos-prod-file-ops-skill)
  - [ ] Invoke with test user_id
  - [ ] Test upload file to S3
  - [ ] Test download file from S3
  - [ ] Test list files for user
  - [ ] Test delete file
  - [ ] Verify per-user isolation (RULE 6)
  - [ ] Verify IAM role scoped to specific S3 prefix
- [ ] Document skill test results
  - [ ] Which skills work without additional setup
  - [ ] Which skills require OAuth/API keys in Secrets Manager
  - [ ] Execution time for each skill
  - [ ] Memory usage and cold start metrics

**Acceptance Criteria:**
- ✅ All 4 skill Lambdas invocable
- ✅ IAM roles properly scoped (no wildcards)
- ✅ Skills requiring secrets fail gracefully
- ✅ Per-user isolation verified for file-ops

---

### 🟢 Medium Priority - Documentation & Operations

#### Task 7: DynamoDB Encryption + Access Patterns
- [ ] Verify DynamoDB tables exist
  - [ ] lateos-prod-agent-memory
  - [ ] lateos-prod-audit-logs
  - [ ] lateos-prod-conversations
  - [ ] lateos-prod-user-preferences
- [ ] Check table encryption
  - [ ] `aws dynamodb describe-table --table-name lateos-prod-conversations --profile lateos-prod`
  - [ ] Verify SSEDescription shows KMS encryption
  - [ ] Confirm KMS key ARN
- [ ] Verify table configuration
  - [ ] Billing mode: PAY_PER_REQUEST (on-demand)
  - [ ] Point-in-time recovery: ENABLED
  - [ ] Partition key: user_id (for data isolation)
- [ ] Test access patterns
  - [ ] Write test record to conversations table
  - [ ] Query by user_id (should succeed)
  - [ ] Query by different user_id (should return empty)
  - [ ] Test cross-user query attempt (should fail/return nothing)
  - [ ] Delete test records
- [ ] Test audit logging
  - [ ] Make API request
  - [ ] Verify audit log entry created in audit-logs table
  - [ ] Check timestamp, user_id, action fields
- [ ] Document data model
  - [ ] Schema for each table
  - [ ] Primary key and sort key patterns
  - [ ] GSI (Global Secondary Index) if any
  - [ ] Access patterns and query examples

**Acceptance Criteria:**
- ✅ All 4 tables encrypted with KMS
- ✅ Point-in-time recovery enabled
- ✅ Per-user data isolation verified (RULE 6)
- ✅ Audit logging functional

---

#### Task 8: Production Deployment Documentation
- [ ] Create PRODUCTION-DEPLOYMENT.md
  - [ ] Document deployment date and time
  - [ ] List all stacks deployed
  - [ ] Document all resources created
  - [ ] Include resource ARNs and IDs
- [ ] Document deployment process
  - [ ] Prerequisites (AWS account setup)
  - [ ] CDK commands used
  - [ ] Bootstrap process
  - [ ] Stack deployment order
  - [ ] Deployment duration (7 minutes)
- [ ] Document configuration
  - [ ] cdk.json context values
  - [ ] Environment variables (none, using Secrets Manager)
  - [ ] Secrets required (list in Secrets Manager)
  - [ ] Region and account details
- [ ] Document endpoints and identifiers
  - [ ] API Gateway URL
  - [ ] Cognito User Pool ID and Client ID
  - [ ] Step Functions state machine ARN
  - [ ] DynamoDB table names
  - [ ] Lambda function names
- [ ] Document post-deployment verification
  - [ ] Checklist for validating deployment
  - [ ] How to verify each service
  - [ ] Smoke test procedures
- [ ] Add to git and commit
  - [ ] Create docs/PRODUCTION-DEPLOYMENT.md
  - [ ] Update STATUS.md with completion
  - [ ] Commit with message: "docs: Phase 8 production deployment documentation"

**Acceptance Criteria:**
- ✅ Complete deployment documentation exists
- ✅ Future deployments can follow this process
- ✅ All resource identifiers documented
- ✅ Committed to git repository

---

#### Task 9: Production Operations Runbook
- [ ] Create PRODUCTION-RUNBOOK.md
  - [ ] Document common operational tasks
  - [ ] Include troubleshooting procedures
  - [ ] Provide incident response guide
- [ ] Document user management procedures
  - [ ] How to create new Cognito user
  - [ ] How to reset user password
  - [ ] How to enable/disable MFA
  - [ ] How to delete user
- [ ] Document Lambda operations
  - [ ] How to view Lambda logs
  - [ ] How to update Lambda code
  - [ ] How to adjust Lambda memory/timeout
  - [ ] How to test Lambda manually
- [ ] Document monitoring procedures
  - [ ] How to check system health
  - [ ] Key CloudWatch metrics to monitor
  - [ ] How to set up custom alarms
  - [ ] How to view X-Ray traces
- [ ] Document incident response
  - [ ] High error rate (>5%)
  - [ ] API Gateway throttling (429 errors)
  - [ ] Lambda timeout errors
  - [ ] Bedrock quota exceeded
  - [ ] Cost alarm triggered
  - [ ] Security alert (GuardDuty finding)
- [ ] Document rollback procedures
  - [ ] How to roll back to previous Lambda version
  - [ ] How to roll back entire stack
  - [ ] How to disable specific feature
- [ ] Document cost management
  - [ ] How to check current costs
  - [ ] How to trigger killswitch manually
  - [ ] How to re-enable after killswitch
  - [ ] How to optimize costs
- [ ] Document secrets management
  - [ ] How to rotate secrets in Secrets Manager
  - [ ] How to add new OAuth credentials
  - [ ] How to update API keys
- [ ] Add to git and commit
  - [ ] Create docs/PRODUCTION-RUNBOOK.md
  - [ ] Update STATUS.md
  - [ ] Commit with message: "docs: Phase 8 production operations runbook"

**Acceptance Criteria:**
- ✅ Comprehensive runbook covers common scenarios
- ✅ Incident response procedures documented
- ✅ Operations team can use without prior knowledge
- ✅ Committed to git repository

---

#### Task 10: CloudWatch Monitoring Dashboards
- [ ] Create CloudWatch Dashboard: lateos-prod-overview
  - [ ] API Gateway metrics
    - [ ] Request count (per minute)
    - [ ] 4xx error rate
    - [ ] 5xx error rate
    - [ ] Latency (p50, p95, p99)
  - [ ] Lambda metrics
    - [ ] Invocations (all functions)
    - [ ] Errors (all functions)
    - [ ] Duration (average per function)
    - [ ] Throttles
    - [ ] Concurrent executions
  - [ ] DynamoDB metrics
    - [ ] Read capacity consumed
    - [ ] Write capacity consumed
    - [ ] ConditionalCheckFailedRequests
    - [ ] UserErrors
  - [ ] Step Functions metrics
    - [ ] Executions started
    - [ ] Executions succeeded
    - [ ] Executions failed
    - [ ] Execution duration
- [ ] Create CloudWatch Dashboard: lateos-prod-security
  - [ ] Validator Lambda metrics
    - [ ] Injection attempts blocked
    - [ ] Threat score distribution
  - [ ] Output Sanitizer metrics
    - [ ] Secrets redacted count
    - [ ] Guardrails violations
  - [ ] Cognito metrics
    - [ ] Authentication attempts
    - [ ] Failed authentications
    - [ ] MFA challenges
  - [ ] API Gateway auth failures (401/403)
- [ ] Create CloudWatch Dashboard: lateos-prod-costs
  - [ ] Estimated charges (daily)
  - [ ] Lambda invocations count
  - [ ] DynamoDB read/write units consumed
  - [ ] Bedrock API calls count
  - [ ] Data transfer out (GB)
  - [ ] Budget percentage used
- [ ] Set up CloudWatch Alarms
  - [ ] High error rate (>5% for 5 minutes)
  - [ ] API Gateway latency >3s
  - [ ] Lambda duration >10s
  - [ ] Step Functions failure rate >10%
  - [ ] DynamoDB throttling events
  - [ ] Estimated charges >$15
- [ ] Document dashboard access
  - [ ] Dashboard URLs
  - [ ] How to customize dashboards
  - [ ] How to add new metrics
  - [ ] How to export dashboard JSON
- [ ] Export dashboard as code
  - [ ] Create infrastructure/dashboards/lateos-prod-dashboards.json
  - [ ] Add to git repository
  - [ ] Document deployment via CDK (future enhancement)

**Acceptance Criteria:**
- ✅ 3 dashboards created (overview, security, costs)
- ✅ Key metrics visible at a glance
- ✅ CloudWatch alarms configured
- ✅ Dashboard JSON exported and committed

---

## 📊 Phase 8 Progress Summary

**Started:** 2026-03-07
**Status:** IN PROGRESS

| Category | Tasks | Completed | Percentage |
|----------|-------|-----------|------------|
| 🔴 Critical | 3 | 0 | 0% |
| 🟡 High Priority | 3 | 0 | 0% |
| 🟢 Medium Priority | 4 | 0 | 0% |
| **Total** | **10** | **0** | **0%** |

---

## 🎯 Success Criteria

Phase 8 is complete when:

- ✅ All integration tests passing (>90%)
- ✅ API Gateway + Cognito authentication working end-to-end
- ✅ Step Functions workflow executes with real Bedrock
- ✅ CloudWatch logs and X-Ray tracing operational
- ✅ Cost protection verified and budget alerts working
- ✅ All 4 skill Lambdas tested individually
- ✅ DynamoDB encryption and per-user isolation verified
- ✅ Production deployment documentation complete
- ✅ Production operations runbook created
- ✅ CloudWatch monitoring dashboards set up

---

## 🚀 Next Phase

**Phase 9:** Integration Development (Telegram, Slack, WhatsApp, Web UI)

Once Phase 8 validation is complete, we'll build the messaging integrations to make Lateos accessible to end users.

---

## 📝 Notes

- Some tests may require OAuth credentials and API keys to be added to AWS Secrets Manager
- Bedrock quota may need to be requested if not already available in me-central-1 region
- Cost estimates will be visible after 6-12 hours of operation
- X-Ray tracing may need to be explicitly enabled for Lambda functions

---

**Last Updated:** 2026-03-07
**Owner:** Leo (@leochong)
**Phase:** 8 - Post-Deployment Validation & Monitoring
