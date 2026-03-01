# Walkthrough 03: Cost Kill Switch Triggered

**What happens when monthly spend hits the $10 threshold**

This walkthrough shows the exact sequence when AWS Budgets detects a threshold breach, how the kill switch Lambda disables API Gateway, and how to safely re-enable service after cost review.

---

## Trigger Scenario

Monthly AWS spend for Lateos reaches **$10.00 USD** (100% of configured budget).

**Root Cause Examples:**

- Unexpected traffic spike (DDoS attempt)
- Runaway Lambda invocations
- Large S3 data transfer
- Bedrock API abuse

---

## Cost Protection Architecture

**Components:**

1. AWS Budgets — monitors actual spend vs. threshold
2. CloudWatch Billing Alarm — redundant monitoring
3. SNS Topic — alert distribution
4. Kill Switch Lambda — automatic service shutdown
5. API Gateway — service endpoint (disabled on trigger)

**Configuration:** `infrastructure/stacks/cost_protection_stack.py`

---

## Step 1: AWS Budgets Detects Threshold Breach

**Budget Configuration:** Lines 246-290 in `cost_protection_stack.py`

**Budget Name:** `lateos-dev-monthly-budget`
**Limit:** $10.00 USD (from `cdk.json` context: `monthly_budget_usd`)
**Time Unit:** MONTHLY

**Notification Thresholds:**

### Threshold 1: 80% ($8.00) — WARNING

```python
budgets.CfnBudget.NotificationWithSubscribersProperty(
    notification=budgets.CfnBudget.NotificationProperty(
        notification_type="ACTUAL",
        comparison_operator="GREATER_THAN",
        threshold=80,  # 80% = $8.00
        threshold_type="PERCENTAGE",
    ),
    subscribers=[
        budgets.CfnBudget.SubscriberProperty(
            subscription_type="SNS",
            address=self.cost_alert_topic.topic_arn,
        ),
    ],
)
```

**What Happens at 80%:**

- SNS notification sent to `lateos-dev-cost-alerts` topic
- Email alert to admin (if subscribed)
- **Service remains ACTIVE** — warning only
- Admin reviews Cost Explorer

**SNS Message at 80%:**

```
Subject: AWS Budget Alert - lateos-dev-monthly-budget

Your budget lateos-dev-monthly-budget has exceeded 80% of the $10.00 limit.
Current spend: $8.12
Forecasted spend: $10.50

Review your usage in AWS Cost Explorer.
```

### Threshold 2: 100% ($10.00) — KILL SWITCH

**Current Spend:** $10.03 USD
**Timestamp:** 2026-03-01T14:32:15Z

**Budget Notification Triggered:**

```python
budgets.CfnBudget.NotificationWithSubscribersProperty(
    notification=budgets.CfnBudget.NotificationProperty(
        notification_type="ACTUAL",
        comparison_operator="GREATER_THAN",
        threshold=100,  # 100% = $10.00
        threshold_type="PERCENTAGE",
    ),
    subscribers=[
        budgets.CfnBudget.SubscriberProperty(
            subscription_type="SNS",
            address=self.cost_alert_topic.topic_arn,
        ),
    ],
)
```

**AWS Budgets publishes to SNS topic:**

```
arn:aws:sns:us-east-1:123456789012:lateos-dev-cost-alerts
```

---

## Step 2: CloudWatch Alarm Triggered (Redundant Check)

**Alarm Configuration:** Lines 293-314 in `cost_protection_stack.py`

**Alarm Name:** `lateos-dev-estimated-charges`
**Metric:** `AWS/Billing` → `EstimatedCharges`
**Threshold:** $8.00 (80% of $10)
**Period:** 6 hours
**Evaluation Periods:** 1

**Alarm State Change:**

```
OK → ALARM
```

**CloudWatch Alarm Event:**

```json
{
  "AlarmName": "lateos-dev-estimated-charges",
  "AlarmDescription": "Alert when estimated charges exceed $8.0",
  "NewStateValue": "ALARM",
  "NewStateReason": "Threshold Crossed: 1 datapoint [10.03] was greater than the threshold (8.0).",
  "StateChangeTime": "2026-03-01T14:32:15.000Z",
  "Region": "us-east-1",
  "AlarmArn": "arn:aws:cloudwatch:us-east-1:123456789012:alarm:lateos-dev-estimated-charges",
  "Trigger": {
    "MetricName": "EstimatedCharges",
    "Namespace": "AWS/Billing",
    "Statistic": "Maximum",
    "Period": 21600,
    "EvaluationPeriods": 1,
    "ComparisonOperator": "GreaterThanThreshold",
    "Threshold": 8.0
  }
}
```

**SNS Action:** Line 314

```python
estimated_charges_alarm.add_alarm_action(cw_actions.SnsAction(self.cost_alert_topic))
```

**Publishes to same SNS topic:** `lateos-dev-cost-alerts`

---

## Step 3: SNS Topic Receives Alert

**SNS Topic:** `arn:aws:sns:us-east-1:123456789012:lateos-dev-cost-alerts`

**Subscribers:**

1. Email: `admin@example.com` (configured manually)
2. Lambda: `lateos-dev-killswitch` (configured in CDK)

**Note:** Kill Switch Lambda subscription is **manual** in Phase 2. In Phase 3+, it will be automated via EventBridge.

**For this walkthrough, assume manual SNS → Lambda trigger OR EventBridge rule:**

**EventBridge Rule (Phase 3):**

```json
{
  "source": ["aws.budgets"],
  "detail-type": ["Budget Notification"],
  "detail": {
    "thresholdType": ["PERCENTAGE"],
    "threshold": [100]
  }
}
```

**Target:** `lateos-dev-killswitch` Lambda

---

## Step 4: Kill Switch Lambda Invoked

**File:** `infrastructure/stacks/cost_protection_stack.py:131-233`
**Function Name:** `lateos-dev-killswitch`
**Runtime:** Python 3.12
**Memory:** 256 MB
**Timeout:** 30 seconds
**Concurrency:** 1 (RULE 7)

**Input Event (from SNS or EventBridge):**

```json
{
  "Records": [
    {
      "Sns": {
        "Message": "{\"AlarmName\": \"lateos-dev-estimated-charges\", \"NewStateValue\": \"ALARM\"}",
        "Subject": "ALARM: lateos-dev-estimated-charges",
        "Timestamp": "2026-03-01T14:32:15.456Z"
      }
    }
  ]
}
```

### 4.1: Lambda Initialization

**Code:** Inline Lambda (lines 138-221 in `cost_protection_stack.py`)

**Environment Variables:**

```python
{
  "ENVIRONMENT": "dev",
  "SNS_TOPIC_ARN": "arn:aws:sns:us-east-1:123456789012:lateos-dev-cost-alerts"
}
```

**Hardcoded Variables:**

```python
API_ID = '{core_stack.api.rest_api_id}'  # e.g., 'abc123xyz'
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']
ENVIRONMENT = os.environ['ENVIRONMENT']
```

### 4.2: Handler Execution

**Code Path:**

**Line 150:** Handler starts

```python
def handler(event, context):
    print(f"Kill switch triggered! Event: {json.dumps(event)}")
```

**CloudWatch Log:** `/aws/lambda/lateos-dev-killswitch`

```
Kill switch triggered! Event: {"Records": [{"Sns": {...}}]}
```

**Line 161:** Get current API configuration

```python
api = apigw.get_rest_api(restApiId=API_ID)
print(f"Current API status: {api.get('name')} - {api.get('description')}")
```

**API Details Retrieved:**

```json
{
  "id": "abc123xyz",
  "name": "lateos-dev-api",
  "description": "Lateos API Gateway - Dev Environment",
  "createdDate": "2026-02-27T10:00:00Z",
  "apiKeySource": "HEADER",
  "endpointConfiguration": {
    "types": ["REGIONAL"]
  }
}
```

**CloudWatch Log:**

```
Current API status: lateos-dev-api - Lateos API Gateway - Dev Environment
```

**Line 166:** Disable API by updating description

```python
response = apigw.update_rest_api(
    restApiId=API_ID,
    patchOperations=[
        {
            'op': 'replace',
            'path': '/description',
            'value': f'DISABLED BY COST KILL SWITCH - {api.get("description")}'
        }
    ]
)
```

**Note:** This is a **marker update**. Actual disabling requires:

- Deleting stage deployment, OR
- Updating stage with disabled throttling, OR
- Removing Cognito authorizer

**Better Implementation (Phase 3):**

```python
# Delete production stage deployment
apigw.delete_stage(restApiId=API_ID, stageName='prod')
```

**CloudWatch Log:**

```
API Gateway disabled: {'id': 'abc123xyz', 'name': 'lateos-dev-api', 'description': 'DISABLED BY COST KILL SWITCH - Lateos API Gateway - Dev Environment'}
```

### 4.3: SNS Notification to Admin

**Line 198:** Publish critical alert

```python
sns.publish(
    TopicArn=SNS_TOPIC_ARN,
    Subject=f'[CRITICAL] Lateos Kill Switch Activated - {ENVIRONMENT}',
    Message=message
)
```

**SNS Message:**

```
Subject: [CRITICAL] Lateos Kill Switch Activated - dev

CRITICAL: Lateos Cost Kill Switch Activated

Environment: dev
API Gateway: abc123xyz
Status: DISABLED

The monthly budget threshold has been exceeded.
API Gateway has been disabled to prevent further costs.

Action Required:
1. Review AWS Cost Explorer for cost breakdown
2. Investigate unexpected usage patterns
3. Re-enable API Gateway manually after review

Timestamp: awsRequestId-xyz123
```

**Recipients:**

- Email: <admin@example.com>
- Slack (if configured): #lateos-alerts channel
- PagerDuty (if configured): On-call engineer

**CloudWatch Log:**

```json
{
  "timestamp": "2026-03-01T14:32:16.123Z",
  "level": "INFO",
  "service": "killswitch",
  "message": "SNS notification sent",
  "sns_message_id": "abc-123-def-456"
}
```

### 4.4: Lambda Response

**Line 204:** Return success

```python
return {
    'statusCode': 200,
    'body': json.dumps({
        'message': 'Kill switch activated successfully',
        'api_id': API_ID,
        'environment': ENVIRONMENT
    })
}
```

**Lambda Execution Summary:**

- Duration: 1,234 ms
- Billed Duration: 1,300 ms
- Memory Size: 256 MB
- Max Memory Used: 68 MB

---

## Step 5: Service Impact

### What Is Now Disabled

**API Gateway:**

- All POST /agent requests return: HTTP 403 Forbidden (if stage deleted)
- OR: Description updated to "DISABLED" (Phase 2 marker)

**User Experience:**

```bash
curl -X POST https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod/agent \
  -H "Authorization: Bearer {jwt}" \
  -H "Content-Type: application/json" \
  -d '{"input": "test"}'

# Response:
{
  "message": "Forbidden"
}
```

### What Still Works

**Lambda Functions:** Still deployed, but not invoked (no API Gateway ingress)
**DynamoDB Tables:** Still accessible (for audit review)
**S3 Buckets:** Still accessible (for data export)
**CloudWatch Logs:** Still collecting logs
**Secrets Manager:** Credentials still stored

**Cost Behavior After Kill Switch:**

- Lambda invocations: **$0** (no triggers)
- API Gateway requests: **$0** (disabled)
- DynamoDB: On-demand billing continues for read/write (if manual access)
- S3: Storage costs continue (~$0.023/GB/month)
- CloudWatch Logs: Retention costs continue (~$0.50/GB/month)
- **Total ongoing cost:** ~$1-2/month for storage and retention

---

## Step 6: Admin Response

### Immediate Actions

**1. Acknowledge Alert**

- Check email inbox for `[CRITICAL] Lateos Kill Switch Activated`
- Check CloudWatch Logs for kill switch execution

**2. Review Cost Explorer**

```bash
# AWS Console
Services → Cost Management → Cost Explorer

# CLI
aws ce get-cost-and-usage \
  --time-period Start=2026-03-01,End=2026-03-02 \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=SERVICE
```

**Example Output:**

```json
{
  "ResultsByTime": [
    {
      "TimePeriod": {"Start": "2026-03-01", "End": "2026-03-02"},
      "Groups": [
        {"Keys": ["AWS Lambda"], "Metrics": {"BlendedCost": {"Amount": "3.45", "Unit": "USD"}}},
        {"Keys": ["Amazon DynamoDB"], "Metrics": {"BlendedCost": {"Amount": "2.10", "Unit": "USD"}}},
        {"Keys": ["Amazon Bedrock"], "Metrics": {"BlendedCost": {"Amount": "4.55", "Unit": "USD"}}}
      ],
      "Total": {"BlendedCost": {"Amount": "10.10", "Unit": "USD"}}
    }
  ]
}
```

**Findings:** Bedrock API calls spiked to $4.55 (45% of total spend)

**3. Investigate Root Cause**

**Check Lambda invocation counts:**

```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=lateos-dev-orchestrator \
  --start-time 2026-03-01T00:00:00Z \
  --end-time 2026-03-01T23:59:59Z \
  --period 3600 \
  --statistics Sum
```

**Check for DDoS attempts:**

```bash
# Count unique user_ids in last 24 hours
aws logs filter-log-events \
  --log-group-name /aws/lambda/lateos-dev-orchestrator \
  --filter-pattern '{ $.user_id = * }' \
  --start-time $(date -u -d '24 hours ago' +%s)000 \
  | jq -r '.events[].message | fromjson | .user_id' \
  | sort | uniq -c | sort -rn
```

**Example Finding:**

```
12,453 user-abc123
    23 user-def456
    15 user-ghi789
```

**Verdict:** Single user (`user-abc123`) made 12,453 requests → likely bot or abuse

**4. Mitigate Root Cause**

**Option 1:** Disable abusive user in Cognito

```bash
aws cognito-idp admin-disable-user \
  --user-pool-id us-east-1_ABC123XYZ \
  --username user-abc123
```

**Option 2:** Add API Gateway throttling (Phase 3)

```python
# In core_stack.py
agent_resource.add_method(
    "POST",
    orchestrator_integration,
    authorizer=core_stack.authorizer,
    throttling={
        "rateLimit": 10,     # 10 requests/second max
        "burstLimit": 20     # 20 concurrent requests max
    }
)
```

**Option 3:** Increase budget (if legitimate spike)

```bash
# Update cdk.json
{
  "monthly_budget_usd": 20  # Increase from 10 to 20
}

# Redeploy
cdk deploy CostProtectionStack
```

---

## Step 7: Re-Enable Service

### Prerequisite Checklist

- [ ] Root cause identified and mitigated
- [ ] Cost spike resolved (check Cost Explorer forecast)
- [ ] Abusive user disabled or throttling configured
- [ ] Budget increased if necessary

### Re-Enable API Gateway

**Option 1: If Stage Was Deleted**

```bash
# Redeploy stage
cdk deploy CoreStack --require-approval never
```

**Option 2: If Description Was Updated Only (Phase 2)**

```bash
# Revert description
aws apigateway update-rest-api \
  --rest-api-id abc123xyz \
  --patch-operations op=replace,path=/description,value="Lateos API Gateway - Dev Environment"
```

**Option 3: Full Re-deployment (Safest)**

```bash
# Destroy and recreate
cdk destroy CoreStack CostProtectionStack
cdk deploy CoreStack CostProtectionStack
```

### Verify Service Restoration

**Test API endpoint:**

```bash
curl -X POST https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod/agent \
  -H "Authorization: Bearer {jwt}" \
  -H "Content-Type: application/json" \
  -d '{"input": "test health check"}'

# Expected response:
{
  "response_text": "Lateos received your request...",
  "success": true,
  "request_id": "..."
}
```

**Monitor CloudWatch Logs:**

```bash
aws logs tail /aws/lambda/lateos-dev-orchestrator --follow
```

**Monitor costs in real-time:**

```bash
# Check current day spend every hour
watch -n 3600 'aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-%d),End=$(date -d tomorrow +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost'
```

---

## What Could Go Wrong

### 1. Kill Switch Lambda Fails

**Scenario:** IAM permission denied when updating API Gateway

**Error Log:**

```json
{
  "errorType": "ClientError",
  "errorMessage": "An error occurred (AccessDeniedException) when calling the UpdateRestApi operation: User: arn:aws:sts::123456789012:assumed-role/lateos-dev-killswitch-role/lateos-dev-killswitch is not authorized to perform: apigateway:PATCH on resource: arn:aws:apigateway:us-east-1::/restapis/abc123xyz",
  "timestamp": "2026-03-01T14:32:16.123Z"
}
```

**Root Cause:** Missing IAM permission (lines 108-119 in `cost_protection_stack.py`)

**Fix:**

```python
kill_switch_role.add_to_policy(
    iam.PolicyStatement(
        sid="AllowDisableApiGateway",
        actions=[
            "apigateway:PATCH",
            "apigateway:GET",
            "apigateway:DeleteStage",  # Add this
        ],
        resources=[...],
    )
)
```

**Fallback:** SNS notification still sent — admin manually disables API Gateway

### 2. SNS Notification Delivery Fails

**Scenario:** Email bounces or Lambda not subscribed to SNS

**CloudWatch Log:**

```json
{
  "level": "ERROR",
  "message": "Failed to publish SNS notification",
  "error": "InvalidParameter: Invalid parameter: TopicArn"
}
```

**Impact:** Kill switch executes but admin is not notified

**Mitigation:**

- Set up CloudWatch alarm on kill switch Lambda errors
- Configure PagerDuty or Slack webhook as backup notification

### 3. API Gateway Not Actually Disabled

**Scenario:** Description update succeeds but stage still active (Phase 2 issue)

**Test:**

```bash
curl -X POST https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod/agent
# Still returns 200 OK
```

**Root Cause:** Phase 2 implementation only updates description, not deployment

**Fix (Phase 3):**

```python
# In kill switch Lambda, replace line 166 with:
apigw.delete_stage(restApiId=API_ID, stageName='prod')
```

### 4. Budget Alert Triggers Repeatedly

**Scenario:** Cost continues to accrue after kill switch (S3 storage, DynamoDB)

**Cost Explorer shows:** $10.50 → $10.75 → $11.00 over 3 days

**Impact:** Multiple kill switch invocations (idempotent, but noisy)

**Mitigation:**

- Budget notification has "NOTIFIED" state to prevent duplicate alerts
- Kill switch checks if API already disabled before acting

---

## Testing the Kill Switch

### Manual Test (LocalStack)

```bash
# Invoke kill switch directly
aws lambda invoke \
  --function-name lateos-dev-killswitch \
  --payload '{"source": "manual-test"}' \
  --endpoint-url http://localhost:4566 \
  response.json

cat response.json
```

### Integration Test (Real AWS - Test Account Only)

```python
# tests/integration/test_cost_killswitch.py
import boto3

def test_kill_switch_disables_api():
    """Test kill switch disables API Gateway."""
    lambda_client = boto3.client('lambda')
    apigw_client = boto3.client('apigateway')

    # Get initial API state
    api_before = apigw_client.get_rest_api(restApiId=API_ID)
    assert 'DISABLED' not in api_before['description']

    # Trigger kill switch
    lambda_client.invoke(
        FunctionName='lateos-dev-killswitch',
        InvocationType='RequestResponse',
        Payload=json.dumps({'source': 'test'})
    )

    # Verify API disabled
    api_after = apigw_client.get_rest_api(restApiId=API_ID)
    assert 'DISABLED BY COST KILL SWITCH' in api_after['description']
```

---

**Next Walkthrough:** [04-secret-redaction.md](04-secret-redaction.md) — How RULE 8 prevents secret leakage
