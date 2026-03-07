# Lateos Production Operations Runbook

**Environment:** Production (lateos-prod)
**AWS Account:** 080746528746
**Region:** us-east-1
**Last Updated:** 2026-03-08

---

## Table of Contents

1. [User Management](#user-management)
2. [Lambda Operations](#lambda-operations)
3. [Monitoring & Health Checks](#monitoring--health-checks)
4. [Incident Response](#incident-response)
5. [Cost Management](#cost-management)
6. [Secrets Management](#secrets-management)
7. [Rollback Procedures](#rollback-procedures)
8. [Emergency Contacts](#emergency-contacts)

---

## User Management

### Create New Cognito User

```bash
aws cognito-idp admin-create-user \
  --profile lateos-prod \
  --user-pool-id us-east-1_wXBwAxBod \
  --username user@example.com \
  --temporary-password 'TempPassword123!@#' \
  --user-attributes Name=email,Value=user@example.com Name=email_verified,Value=true \
  --message-action SUPPRESS
```

**Note:** User will be required to change password on first login.

### Set Permanent Password

```bash
aws cognito-idp admin-set-user-password \
  --profile lateos-prod \
  --user-pool-id us-east-1_wXBwAxBod \
  --username [UUID-from-creation] \
  --password 'NewPassword123!@#' \
  --permanent
```

### Enable/Disable MFA for User

```bash
# Enable MFA (required by default)
aws cognito-idp admin-set-user-mfa-preference \
  --profile lateos-prod \
  --user-pool-id us-east-1_wXBwAxBod \
  --username user@example.com \
  --software-token-mfa-settings Enabled=true,PreferredMfa=true

# Disable MFA (not recommended in production)
aws cognito-idp admin-set-user-mfa-preference \
  --profile lateos-prod \
  --user-pool-id us-east-1_wXBwAxBod \
  --username user@example.com \
  --software-token-mfa-settings Enabled=false
```

### Reset User Password

```bash
aws cognito-idp admin-reset-user-password \
  --profile lateos-prod \
  --user-pool-id us-east-1_wXBwAxBod \
  --username user@example.com
```

### Delete User

```bash
aws cognito-idp admin-delete-user \
  --profile lateos-prod \
  --user-pool-id us-east-1_wXBwAxBod \
  --username user@example.com
```

### List All Users

```bash
aws cognito-idp list-users \
  --profile lateos-prod \
  --user-pool-id us-east-1_wXBwAxBod \
  --query 'Users[*].{Username:Username, Email:Attributes[?Name==`email`].Value|[0], Status:UserStatus}' \
  --output table
```

---

## Lambda Operations

### View Lambda Logs

```bash
# Get recent logs for a specific Lambda
aws logs tail /aws/lambda/lateos-prod-orchestrator \
  --profile lateos-prod \
  --follow

# Get logs for specific time range
aws logs filter-log-events \
  --profile lateos-prod \
  --log-group-name /aws/lambda/lateos-prod-orchestrator \
  --start-time $(date -u -d '1 hour ago' +%s)000 \
  --query 'events[*].message' \
  --output text
```

### Invoke Lambda Manually for Testing

```bash
# Test validator Lambda
aws lambda invoke \
  --profile lateos-prod \
  --function-name lateos-prod-validator \
  --payload '{"user_input": "What is the weather today?"}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/response.json

cat /tmp/response.json
```

### Update Lambda Code

```bash
# Make code changes in lambdas/
# Then redeploy the stack
cdk deploy LateosOrchestrationProdStack --profile lateos-prod
```

### Adjust Lambda Memory/Timeout

Edit `infrastructure/stacks/orchestration_stack.py`:

```python
# Example: Increase orchestrator memory
self.orchestrator_lambda = aws_lambda.Function(
    self, "OrchestratorLambda",
    memory_size=1024,  # Changed from 512
    timeout=Duration.seconds(120),  # Changed from 60
    # ...
)
```

Then deploy:

```bash
cdk deploy LateosOrchestrationProdStack --profile lateos-prod
```

### View Lambda Configuration

```bash
aws lambda get-function-configuration \
  --profile lateos-prod \
  --function-name lateos-prod-orchestrator \
  --query '{Memory:MemorySize, Timeout:Timeout, Runtime:Runtime, Handler:Handler}' \
  --output table
```

### Check Lambda Execution Role Permissions

```bash
# Get role ARN
aws lambda get-function-configuration \
  --profile lateos-prod \
  --function-name lateos-prod-orchestrator \
  --query 'Role' \
  --output text

# List attached policies
aws iam list-attached-role-policies \
  --profile lateos-prod \
  --role-name lateos-prod-orchestrator-role

# Get inline policy document
aws iam get-role-policy \
  --profile lateos-prod \
  --role-name lateos-prod-orchestrator-role \
  --policy-name [PolicyName]
```

---

## Monitoring & Health Checks

### Check System Health

```bash
# Verify all stacks are healthy
aws cloudformation list-stacks \
  --profile lateos-prod \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query 'StackSummaries[?starts_with(StackName, `Lateos`)].{Name:StackName, Status:StackStatus}' \
  --output table

# Check Lambda error rates (last hour)
aws cloudwatch get-metric-statistics \
  --profile lateos-prod \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=lateos-prod-orchestrator \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum \
  --output table
```

### Key Metrics to Monitor

**Lambda Invocations:**
```bash
aws cloudwatch get-metric-statistics \
  --profile lateos-prod \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=lateos-prod-orchestrator \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

**Lambda Duration (p99):**
```bash
aws cloudwatch get-metric-statistics \
  --profile lateos-prod \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=lateos-prod-orchestrator \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum \
  --output table
```

**API Gateway Requests:**
```bash
aws cloudwatch get-metric-statistics \
  --profile lateos-prod \
  --namespace AWS/ApiGateway \
  --metric-name Count \
  --dimensions Name=ApiName,Value=lateos-prod-api \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

**DynamoDB Read/Write Capacity:**
```bash
aws cloudwatch get-metric-statistics \
  --profile lateos-prod \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedReadCapacityUnits \
  --dimensions Name=TableName,Value=lateos-prod-conversations \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

### View X-Ray Traces

```bash
# List recent traces
aws xray get-trace-summaries \
  --profile lateos-prod \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date -u +%s) \
  --query 'TraceSummaries[*].{Id:Id, Duration:Duration, Http:Http}' \
  --output table

# Get specific trace details
aws xray batch-get-traces \
  --profile lateos-prod \
  --trace-ids [TRACE_ID]
```

### Set Up CloudWatch Alarms

```bash
# High error rate alarm (>5% for 5 minutes)
aws cloudwatch put-metric-alarm \
  --profile lateos-prod \
  --alarm-name lateos-prod-high-error-rate \
  --alarm-description "Alert when Lambda error rate exceeds 5%" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=lateos-prod-orchestrator

# API Gateway latency alarm (>3s)
aws cloudwatch put-metric-alarm \
  --profile lateos-prod \
  --alarm-name lateos-prod-high-latency \
  --alarm-description "Alert when API latency exceeds 3 seconds" \
  --metric-name Latency \
  --namespace AWS/ApiGateway \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 3000 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=ApiName,Value=lateos-prod-api
```

---

## Incident Response

### High Error Rate (>5%)

**Symptoms:**
- Lambda error metrics spike
- CloudWatch alarm triggered
- User reports of failures

**Diagnosis:**
1. Check CloudWatch Logs for recent errors:
   ```bash
   aws logs filter-log-events \
     --profile lateos-prod \
     --log-group-name /aws/lambda/lateos-prod-orchestrator \
     --filter-pattern "ERROR" \
     --start-time $(date -u -d '1 hour ago' +%s)000
   ```

2. Check X-Ray for failed traces

3. Review recent deployments (if error started after deployment)

**Resolution:**
- If code bug: Roll back to previous version
- If dependency issue: Check Lambda layer compatibility
- If AWS service issue: Check AWS Service Health Dashboard

### API Gateway Throttling (429 Errors)

**Symptoms:**
- Users receiving 429 errors
- High request rate in metrics

**Diagnosis:**
```bash
aws cloudwatch get-metric-statistics \
  --profile lateos-prod \
  --namespace AWS/ApiGateway \
  --metric-name 4XXError \
  --dimensions Name=ApiName,Value=lateos-prod-api \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Sum
```

**Resolution:**
- Review throttling settings in API Gateway
- Consider increasing rate limits (if legitimate traffic)
- Implement client-side retry with exponential backoff

### Lambda Timeout Errors

**Symptoms:**
- Lambda execution exceeds timeout
- Task timed out messages in logs

**Diagnosis:**
1. Check average duration:
   ```bash
   aws cloudwatch get-metric-statistics \
     --profile lateos-prod \
     --namespace AWS/Lambda \
     --metric-name Duration \
     --dimensions Name=FunctionName,Value=lateos-prod-orchestrator \
     --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
     --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
     --period 300 \
     --statistics Average,Maximum
   ```

2. Review logs for slow operations (database queries, API calls)

**Resolution:**
- Increase Lambda timeout (up to 15 minutes for standard, 5 minutes for Express Step Functions)
- Optimize slow code paths
- Consider async processing for long operations

### Bedrock Quota Exceeded

**Symptoms:**
- ThrottlingException in orchestrator logs
- Bedrock API calls failing

**Diagnosis:**
```bash
aws logs filter-log-events \
  --profile lateos-prod \
  --log-group-name /aws/lambda/lateos-prod-orchestrator \
  --filter-pattern "ThrottlingException" \
  --start-time $(date -u -d '1 hour ago' +%s)000
```

**Resolution:**
- Request quota increase via AWS Service Quotas
- Implement exponential backoff retry logic
- Consider rate limiting at application layer

### Cost Alarm Triggered

**Symptoms:**
- SNS alert received
- Budget threshold exceeded

**Diagnosis:**
```bash
# Check recent costs
aws ce get-cost-and-usage \
  --profile lateos-prod \
  --time-period Start=$(date -u -d '7 days ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=SERVICE \
  --output table
```

**Resolution:**
- Identify cost driver (Lambda invocations, DynamoDB, data transfer)
- Manually trigger killswitch if needed (see Cost Management section)
- Investigate anomalous usage patterns
- Optimize high-cost resources

### Security Alert (GuardDuty Finding)

**Symptoms:**
- GuardDuty finding notification
- Unusual activity detected

**Diagnosis:**
```bash
aws guardduty list-findings \
  --profile lateos-prod \
  --detector-id [DETECTOR_ID] \
  --finding-criteria '{"Criterion":{"service.archived":{"Eq":["false"]}}}' \
  --max-results 10
```

**Resolution:**
1. Review finding details
2. Rotate compromised credentials immediately
3. Review CloudTrail for suspicious activity
4. Follow incident response playbook
5. Consider temporary service shutdown if breach suspected

---

## Cost Management

### Check Current Costs

```bash
# Daily costs for last 7 days
aws ce get-cost-and-usage \
  --profile lateos-prod \
  --time-period Start=$(date -u -d '7 days ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost \
  --output table

# Cost breakdown by service
aws ce get-cost-and-usage \
  --profile lateos-prod \
  --time-period Start=$(date -u -d '7 days ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=SERVICE \
  --output table
```

### Manually Trigger Killswitch

**⚠️ WARNING: This will disable the API Gateway and stop all incoming requests.**

```bash
# Invoke killswitch Lambda
aws lambda invoke \
  --profile lateos-prod \
  --function-name lateos-prod-killswitch \
  --payload '{"action": "disable"}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/killswitch-response.json

cat /tmp/killswitch-response.json
```

### Re-enable After Killswitch

```bash
# Manually re-enable API Gateway stage
aws apigateway update-stage \
  --profile lateos-prod \
  --rest-api-id sys7fksdeg \
  --stage-name prod \
  --patch-operations op=replace,path=/*/throttle/rateLimit,value=10000

# Verify stage is active
aws apigateway get-stage \
  --profile lateos-prod \
  --rest-api-id sys7fksdeg \
  --stage-name prod \
  --query '{DeploymentId:deploymentId, CreatedDate:createdDate}' \
  --output table
```

### Optimize Costs

**Reduce Lambda Memory (if over-provisioned):**
```bash
# Check current memory usage in CloudWatch
aws cloudwatch get-metric-statistics \
  --profile lateos-prod \
  --namespace AWS/Lambda \
  --metric-name MemoryUtilization \
  --dimensions Name=FunctionName,Value=lateos-prod-orchestrator \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Maximum
```

**Reduce Log Retention:**
```bash
# Set retention to 7 days for non-critical logs
aws logs put-retention-policy \
  --profile lateos-prod \
  --log-group-name /aws/lambda/lateos-prod-validator \
  --retention-in-days 7
```

---

## Secrets Management

### List All Secrets

```bash
aws secretsmanager list-secrets \
  --profile lateos-prod \
  --query 'SecretList[?starts_with(Name, `lateos/prod`)].{Name:Name, LastChanged:LastChangedDate}' \
  --output table
```

### Create New Secret

```bash
aws secretsmanager create-secret \
  --profile lateos-prod \
  --name lateos/prod/telegram \
  --description "Telegram bot token for production" \
  --secret-string '{"bot_token":"YOUR_BOT_TOKEN_HERE"}'
```

### Update Existing Secret

```bash
aws secretsmanager update-secret \
  --profile lateos-prod \
  --secret-id lateos/prod/telegram \
  --secret-string '{"bot_token":"NEW_BOT_TOKEN_HERE"}'
```

### Rotate Secret

```bash
# Manual rotation (update and test)
aws secretsmanager update-secret \
  --profile lateos-prod \
  --secret-id lateos/prod/slack \
  --secret-string '{"signing_secret":"NEW_SECRET","bot_token":"NEW_TOKEN"}'

# Test integration after rotation
# Invoke relevant Lambda to verify new credentials work
```

### View Secret Value (Use with Caution)

```bash
aws secretsmanager get-secret-value \
  --profile lateos-prod \
  --secret-id lateos/prod/telegram \
  --query 'SecretString' \
  --output text
```

**⚠️ Never log secret values. Use only for troubleshooting in secure terminal.**

### Delete Secret

```bash
# Schedule deletion (30-day recovery window)
aws secretsmanager delete-secret \
  --profile lateos-prod \
  --secret-id lateos/prod/old-secret \
  --recovery-window-in-days 30

# Force immediate deletion (no recovery)
aws secretsmanager delete-secret \
  --profile lateos-prod \
  --secret-id lateos/prod/old-secret \
  --force-delete-without-recovery
```

---

## Rollback Procedures

### Roll Back Lambda to Previous Version

```bash
# List Lambda versions
aws lambda list-versions-by-function \
  --profile lateos-prod \
  --function-name lateos-prod-orchestrator \
  --query 'Versions[*].{Version:Version, Modified:LastModified}' \
  --output table

# Update alias to point to previous version
aws lambda update-alias \
  --profile lateos-prod \
  --function-name lateos-prod-orchestrator \
  --name prod \
  --function-version [PREVIOUS_VERSION]
```

### Roll Back Entire Stack

```bash
# Option 1: Redeploy from previous commit
git checkout [PREVIOUS_COMMIT_SHA]
cdk deploy LateosOrchestrationProdStack --profile lateos-prod

# Option 2: Use CloudFormation stack update with previous template
aws cloudformation update-stack \
  --profile lateos-prod \
  --stack-name LateosOrchestrationProdStack \
  --use-previous-template
```

### Disable Specific Feature

```bash
# Example: Disable a skill Lambda by removing invoke permissions
aws lambda remove-permission \
  --profile lateos-prod \
  --function-name lateos-prod-email-skill \
  --statement-id AllowStepFunctionsInvoke

# Or update Step Functions state machine to skip the skill
```

---

## Emergency Contacts

**Project Lead:** Leo (@leochong)
**Repository:** https://github.com/leochong/Lateos
**AWS Account ID:** 080746528746

**Escalation Path:**
1. Check CloudWatch Logs and Metrics
2. Review incident response procedures above
3. If unable to resolve, contact project lead
4. For security incidents, follow SECURITY.md reporting procedures

**AWS Support:**
- Developer Support: Available via AWS Console
- Severity: Use appropriate severity level (Critical for outages)

---

## Appendix: Quick Reference Commands

```bash
# System health check
aws cloudformation list-stacks --profile lateos-prod --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --query 'StackSummaries[?starts_with(StackName, `Lateos`)].StackName' --output table

# Recent Lambda errors
aws logs filter-log-events --profile lateos-prod --log-group-name /aws/lambda/lateos-prod-orchestrator --filter-pattern "ERROR" --start-time $(date -u -d '1 hour ago' +%s)000 --query 'events[*].message' --output text

# Current costs
aws ce get-cost-and-usage --profile lateos-prod --time-period Start=$(date -u -d '7 days ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) --granularity DAILY --metrics BlendedCost --output table

# List Cognito users
aws cognito-idp list-users --profile lateos-prod --user-pool-id us-east-1_wXBwAxBod --query 'Users[*].Username' --output table

# Test API Gateway (expect 401)
curl -X POST https://sys7fksdeg.execute-api.us-east-1.amazonaws.com/prod/agent -H "Content-Type: application/json" -d '{"user_input":"test"}'
```

---

**Document Version:** 1.0
**Last Updated:** 2026-03-08
**Phase:** 8 - Post-Deployment Validation & Monitoring
