# Lateos Infrastructure — Claude Code Context

Read the root `CLAUDE.md` first. This file adds CDK-specific context.

---

## CDK Standards for This Project

### Stack Boundaries

Each stack has a single responsibility. Do not mix concerns:

```
CoreStack           → API Gateway, WAF v2, Cognito, Route53 (if applicable)
OrchestrationStack  → Step Functions, validation Lambda, intent classifier
SkillsStack         → Skill registry, skill Lambdas, skill IAM roles
MemoryStack         → DynamoDB tables, KMS keys, audit log
IntegrationsStack   → Telegram/Slack/WhatsApp webhook Lambdas
CostProtectionStack → Budgets, kill switch, CloudWatch alarms, monitor Lambda
```

Stacks reference each other via exported values — never hardcode ARNs
across stack boundaries.

---

## AWS Security Best Practices — Current (2025-2026)

### IAM — Least Privilege, Always

```python
# CORRECT — scoped to exactly what the function needs
email_skill_role = iam.Role(self, "EmailSkillRole",
    assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
    description="Email skill Lambda — read-only Secrets Manager access",
    max_session_duration=Duration.hours(1),
)

# Grant only what is needed, scoped to exact resource
email_skill_role.add_to_policy(iam.PolicyStatement(
    sid="ReadEmailSecret",
    effect=iam.Effect.ALLOW,
    actions=["secretsmanager:GetSecretValue"],
    resources=[
        f"arn:aws:secretsmanager:{self.region}:{self.account}"
        f":secret:lateos/*/email/*"
    ],
    conditions={
        "StringEquals": {
            "secretsmanager:ResourceTag/Project": "Lateos"
        }
    }
))

# WRONG — never do this
role.add_to_policy(iam.PolicyStatement(
    actions=["secretsmanager:*"],   # ← wildcard action
    resources=["*"],                # ← wildcard resource
))
```

### IAM Permission Boundaries

Every Lambda execution role must have a permission boundary to prevent
privilege escalation even if the role policy is misconfigured:

```python
# Define a permission boundary for all Lateos Lambda roles
permission_boundary = iam.ManagedPolicy(self, "LambdaPermissionBoundary",
    managed_policy_name="LateosLambdaBoundary",
    statements=[
        iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
                "xray:PutTraceSegments",
                "xray:PutTelemetryRecords",
                "secretsmanager:GetSecretValue",
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:Query",
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
                "sns:Publish",
            ],
            resources=["*"],
        ),
        # Explicit deny for anything a Lambda should never do
        iam.PolicyStatement(
            effect=iam.Effect.DENY,
            actions=[
                "iam:*",
                "organizations:*",
                "account:*",
                "s3:DeleteBucket",
                "kms:DeleteKey",
                "cloudtrail:DeleteTrail",
                "cloudtrail:StopLogging",
                "guardduty:DeleteDetector",
                "securityhub:DeleteHub",
            ],
            resources=["*"],
        ),
    ]
)

# Apply to ALL Lambda roles
role = iam.Role(self, "SkillRole",
    assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
    permissions_boundary=permission_boundary,  # ← always include this
)
```

### KMS Key Configuration

```python
# Every KMS key follows this pattern
key = kms.Key(self, "MemoryEncryptionKey",
    description="Lateos DynamoDB memory encryption",
    enable_key_rotation=True,           # rotate annually — always on
    rotation_schedule=kms.RotationSchedule.DURATION(Duration.days(90)), # quarterly
    pending_window=Duration.days(7),    # minimum deletion window
    alias=f"lateos/{env}/memory",
    removal_policy=RemovalPolicy.RETAIN, # never auto-delete KMS keys
    policy=iam.PolicyDocument(
        statements=[
            # Key admin — only the CDK deploy role
            iam.PolicyStatement(
                sid="KeyAdministration",
                principals=[iam.ArnPrincipal(deploy_role_arn)],
                actions=["kms:*"],
                resources=["*"],
            ),
            # Key usage — only scoped Lambda roles
            iam.PolicyStatement(
                sid="KeyUsage",
                principals=[memory_lambda_role],
                actions=[
                    "kms:Decrypt",
                    "kms:GenerateDataKey",
                    "kms:DescribeKey",
                ],
                resources=["*"],
                conditions={
                    "StringEquals": {
                        "kms:ViaService": f"dynamodb.{self.region}.amazonaws.com",
                        "kms:CallerAccount": self.account,
                    }
                }
            ),
        ]
    ),
)
```

### Secrets Manager Configuration

```python
# All secrets follow this pattern
secret = secretsmanager.Secret(self, "TelegramSecret",
    secret_name=f"lateos/{env}/telegram",
    description="Telegram bot credentials for Lateos",
    generate_secret_string=secretsmanager.SecretStringGenerator(
        secret_string_template=json.dumps({"bot_token": "REPLACE_ME"}),
        generate_string_key="rotation_placeholder",
        exclude_characters=" %+~`#$&*()|[]{}:;<>?!'/@\"\\",
    ),
    encryption_key=secrets_key,
    removal_policy=RemovalPolicy.RETAIN,
)

# Resource policy — deny access from outside the account
secret.add_to_resource_policy(iam.PolicyStatement(
    sid="DenyExternalAccess",
    effect=iam.Effect.DENY,
    principals=[iam.AnyPrincipal()],
    actions=["secretsmanager:*"],
    resources=["*"],
    conditions={
        "StringNotEquals": {
            "aws:PrincipalAccount": self.account,
        }
    }
))
```

### WAF v2 Configuration

```python
# WAF v2 with managed rule groups — never build WAF rules from scratch
waf = wafv2.CfnWebACL(self, "AgentWAF",
    scope="REGIONAL",
    default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
        cloud_watch_metrics_enabled=True,
        metric_name="LateosWAF",
        sampled_requests_enabled=True,
    ),
    rules=[
        # AWS Managed Rules — always include these
        _waf_managed_rule("AWSManagedRulesCommonRuleSet", priority=1),
        _waf_managed_rule("AWSManagedRulesKnownBadInputsRuleSet", priority=2),
        _waf_managed_rule("AWSManagedRulesSQLiRuleSet", priority=3),
        _waf_managed_rule("AWSManagedRulesAmazonIpReputationList", priority=4),

        # Rate limiting — per IP, per 5 minutes
        wafv2.CfnWebACL.RuleProperty(
            name="RateLimitPerIP",
            priority=10,
            action=wafv2.CfnWebACL.RuleActionProperty(block={}),
            statement=wafv2.CfnWebACL.StatementProperty(
                rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                    limit=100,  # 100 requests per 5 minutes per IP
                    aggregate_key_type="IP",
                )
            ),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="RateLimitPerIP",
                sampled_requests_enabled=True,
            ),
        ),
    ],
)

def _waf_managed_rule(name: str, priority: int):
    return wafv2.CfnWebACL.RuleProperty(
        name=name,
        priority=priority,
        override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
        statement=wafv2.CfnWebACL.StatementProperty(
            managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                vendor_name="AWS",
                name=name,
            )
        ),
        visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
            cloud_watch_metrics_enabled=True,
            metric_name=name,
            sampled_requests_enabled=True,
        ),
    )
```

### S3 Bucket Configuration

```python
# Every S3 bucket follows this pattern — no public access ever
bucket = s3.Bucket(self, "AgentFileBucket",
    bucket_name=f"lateos-{env}-files-{self.account}",
    encryption=s3.BucketEncryption.KMS,
    encryption_key=files_key,
    block_public_access=s3.BlockPublicAccess.BLOCK_ALL,  # always
    enforce_ssl=True,                    # deny HTTP requests
    versioning_enabled=True,             # enable versioning
    object_lock_enabled=False,           # enable for audit logs
    server_access_logs_bucket=access_log_bucket,
    lifecycle_rules=[
        s3.LifecycleRule(
            id="DeleteOldVersions",
            noncurrent_version_expiration=Duration.days(30),
            noncurrent_versions_to_retain=3,
        )
    ],
    removal_policy=RemovalPolicy.RETAIN,
    auto_delete_objects=False,           # never auto-delete in CDK
)

# Deny non-SSL and non-account access via bucket policy
bucket.add_to_resource_policy(iam.PolicyStatement(
    sid="DenyNonSSL",
    effect=iam.Effect.DENY,
    principals=[iam.AnyPrincipal()],
    actions=["s3:*"],
    resources=[bucket.bucket_arn, f"{bucket.bucket_arn}/*"],
    conditions={"Bool": {"aws:SecureTransport": "false"}},
))
```

### DynamoDB Configuration

```python
# All DynamoDB tables follow this pattern
table = dynamodb.Table(self, "MemoryTable",
    table_name=f"lateos-{env}-memory",
    partition_key=dynamodb.Attribute(
        name="user_id",
        type=dynamodb.AttributeType.STRING,
    ),
    sort_key=dynamodb.Attribute(
        name="timestamp",
        type=dynamodb.AttributeType.STRING,
    ),
    billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
    encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
    encryption_key=memory_key,
    point_in_time_recovery=True,        # always enable PITR
    deletion_protection=True,           # never accidentally delete
    removal_policy=RemovalPolicy.RETAIN,
    time_to_live_attribute="expires_at", # TTL for retention policy
    stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,  # for audit
)

# Prevent table scans that could expose cross-user data
# (enforced via IAM condition on Lambda roles)
```

### CloudTrail Configuration

```python
# CloudTrail with S3 Object Lock for tamper-proof audit
trail_bucket = s3.Bucket(self, "CloudTrailBucket",
    encryption=s3.BucketEncryption.S3_MANAGED,
    block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
    enforce_ssl=True,
    object_lock_enabled=True,           # immutable audit logs
    object_lock_default_retention=s3.ObjectLockRetention.governance(
        duration=s3.ObjectLockRetentionDays(365)
    ),
    lifecycle_rules=[
        s3.LifecycleRule(
            id="TransitionToIA",
            transitions=[
                s3.Transition(
                    storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                    transition_after=Duration.days(90),
                )
            ],
        )
    ],
)

trail = cloudtrail.Trail(self, "AgentTrail",
    trail_name="lateos-audit-trail",
    bucket=trail_bucket,
    send_to_cloud_watch_logs=True,
    cloud_watch_log_group=trail_log_group,
    include_global_service_events=True,
    is_multi_region_trail=True,         # capture events in all regions
    enable_file_validation=True,        # detect log tampering
    management_events=cloudtrail.ReadWriteType.ALL,
)

# Log all S3 data events (reads and writes)
trail.add_s3_event_selector(
    s3_selector=[cloudtrail.S3EventSelector(bucket=files_bucket)],
    read_write_type=cloudtrail.ReadWriteType.ALL,
)
```

### GuardDuty and Security Hub

```python
# GuardDuty — enable with all protection plans
guardduty.CfnDetector(self, "GuardDutyDetector",
    enable=True,
    finding_publishing_frequency="FIFTEEN_MINUTES",
    features=[
        guardduty.CfnDetector.CFNFeatureConfigurationProperty(
            name="S3_DATA_EVENTS",
            status="ENABLED",
        ),
        guardduty.CfnDetector.CFNFeatureConfigurationProperty(
            name="LAMBDA_NETWORK_LOGS",
            status="ENABLED",
        ),
        guardduty.CfnDetector.CFNFeatureConfigurationProperty(
            name="RUNTIME_MONITORING",
            status="ENABLED",
        ),
    ],
)

# Security Hub — enable foundational standards
securityhub.CfnHub(self, "SecurityHub",
    enable_default_standards=True,  # AWS Foundational Security Best Practices
)
```

### Lambda Configuration

```python
# All Lambdas follow this pattern
function = lambda_.Function(self, "SkillEmailHandler",
    function_name=f"lateos-{env}-skill-email",
    runtime=lambda_.Runtime.PYTHON_3_12,
    handler="email_skill.handler",
    code=lambda_.Code.from_asset("lambdas/skills/email"),
    role=email_skill_role,              # explicit role, not auto-generated
    timeout=Duration.seconds(30),       # always explicit, never default
    memory_size=256,                    # right-size for the function
    reserved_concurrent_executions=10,  # always set — cost protection
    tracing=lambda_.Tracing.ACTIVE,     # X-Ray tracing always on
    layers=[powertools_layer, shared_layer],
    environment={
        # Never secrets here — only configuration
        "ENVIRONMENT": env,
        "SECRET_NAME": f"lateos/{env}/email",
        "LOG_LEVEL": "INFO",
        "POWERTOOLS_SERVICE_NAME": "skill-email",
    },
    dead_letter_queue_enabled=True,     # always enable DLQ
    architecture=lambda_.Architecture.ARM_64,  # Graviton2 — cheaper + faster
    logging_format=lambda_.LoggingFormat.JSON,  # structured logging
    system_log_level=lambda_.SystemLogLevel.WARN,
    application_log_level=lambda_.ApplicationLogLevel.INFO,
    retry_attempts=0,                   # Step Functions handles retry logic
)

# VPC config only for skills that need private resources
# Most Lambdas do NOT need VPC (adds cold start, costs NAT)
# Only add VPC if the function needs to reach a private resource
```

---

## cdk-nag Rules — Required Passing

All CDK stacks must pass these cdk-nag checks. Any suppressions
must be explicitly justified in code with a comment:

```python
from cdk_nag import AwsSolutionsChecks, NagSuppressions

# Apply globally in app.py
cdk.Aspects.of(app).add(AwsSolutionsChecks(verbose=True))

# If suppression is genuinely necessary (rare), document it:
NagSuppressions.add_resource_suppressions(
    construct=my_construct,
    suppressions=[{
        "id": "AwsSolutions-IAM4",
        "reason": "AWSLambdaBasicExecutionRole is acceptable here because "
                  "this function only writes CloudWatch logs and has no "
                  "other permissions. Custom policy would be identical.",
    }],
)
```

**Never suppress without a reason string. PRs with empty reason strings
will be rejected.**

---

## Resource Tagging — Required on All Resources

```python
# In app.py — applies to everything
from aws_cdk import Tags, App

app = App()
env = app.node.try_get_context("environment") or "dev"

Tags.of(app).add("Project", "Lateos")
Tags.of(app).add("Environment", env)
Tags.of(app).add("ManagedBy", "CDK")
Tags.of(app).add("Repository", "github.com/yourusername/lateos")
Tags.of(app).add("SecurityContact", "security@yourdomain.com")
```

Missing tags on any resource will fail the CDK unit tests.

---

## Removal Policies

```python
# Production resources — always RETAIN
# Nothing with user data should ever be auto-deleted by CDK

RemovalPolicy.RETAIN    # DynamoDB tables, S3 buckets, KMS keys, secrets
RemovalPolicy.DESTROY   # ONLY for dev/test CloudWatch log groups, temp queues

# Never use RemovalPolicy.DESTROY on anything that holds user data
# This is tested in test_infrastructure_removal_policies.py
```

---

## Cross-Stack References

```python
# Export from producing stack
self.api_gateway_id = api.rest_api_id
CfnOutput(self, "ApiGatewayId",
    value=api.rest_api_id,
    export_name=f"Lateos-{env}-ApiGatewayId",
)

# Import in consuming stack — never hardcode ARNs
api_id = Fn.import_value(f"Lateos-{env}-ApiGatewayId")
```

---

*Keep this file updated when adding new stacks or changing AWS service patterns.*
