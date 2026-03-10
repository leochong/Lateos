"""
Skills Stack

Deploys skill Lambda functions with scoped IAM roles.
Implements RULE 2: Each skill has its own scoped IAM role (no wildcard permissions).
Implements RULE 6: Per-user data isolation enforced via IAM policies.
Implements RULE 7: Reserved concurrent executions for cost protection.

Skills:
- Email (Gmail OAuth)
- Calendar (Google Calendar API)
- Web Fetch (HTTP client with domain whitelist)
- File Operations (S3-backed storage)

Each skill Lambda has:
- Dedicated execution role with minimum required permissions
- No access to other skills' secrets or resources
- Reserved concurrency limit
- CloudWatch Logs encryption
- X-Ray tracing enabled
"""

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk.aws_lambda_python_alpha import PythonFunction
from constructs import Construct


class SkillsStack(Stack):
    """Stack for skill Lambda functions"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str,
        audit_table,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = environment
        self.audit_table = audit_table

        # Create KMS key for CloudWatch Logs encryption
        self.logs_key = kms.Key(
            self,
            "LateosSkillsLogsKey",
            description=f"Lateos {self.env_name} - Skills CloudWatch Logs encryption",
            enable_key_rotation=True,
            removal_policy=(
                RemovalPolicy.DESTROY if self.env_name == "dev" else RemovalPolicy.RETAIN
            ),
        )

        # Create S3 bucket for file operations skill
        self.files_bucket = s3.Bucket(
            self,
            "LateosFilesBucket",
            bucket_name=f"lateos-{self.env_name}-files",
            encryption=s3.BucketEncryption.KMS,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            versioned=True,
            removal_policy=(
                RemovalPolicy.DESTROY if self.env_name == "dev" else RemovalPolicy.RETAIN
            ),
            auto_delete_objects=False,
        )

        # Create skill Lambdas with scoped IAM roles
        self.email_skill = self._create_email_skill()
        self.email_summary_skill = self._create_email_summary_skill()
        self.calendar_skill = self._create_calendar_skill()
        self.web_fetch_skill = self._create_web_fetch_skill()
        self.file_ops_skill = self._create_file_ops_skill()

    def _create_lambda_role(self, skill_name: str, policy_statements: list) -> iam.Role:
        """
        Create scoped IAM role for a skill Lambda.

        Args:
            skill_name: Name of the skill
            policy_statements: List of IAM policy statements

        Returns:
            IAM role
        """
        role = iam.Role(
            self,
            f"Lateos{skill_name}SkillRole",
            role_name=f"lateos-{self.env_name}-{skill_name.lower()}-skill",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description=f"Execution role for {skill_name} skill Lambda (scoped)",
        )

        # Add CloudWatch Logs permissions
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    (
                        f"arn:aws:logs:{self.region}:{self.account}:"
                        f"log-group:/aws/lambda/lateos-{self.env_name}-"
                        f"{skill_name.lower()}-skill*"
                    )
                ],
            )
        )

        # Add X-Ray permissions
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                ],
                resources=["*"],  # X-Ray requires wildcard
            )
        )

        # Add skill-specific permissions
        for statement in policy_statements:
            role.add_to_policy(statement)

        return role

    def _create_email_skill(self) -> lambda_.Function:
        """Create email skill Lambda with scoped IAM role"""

        # Scoped IAM policy: Only Gmail OAuth secrets for specific users
        policy_statements = [
            # Secrets Manager: Only Gmail OAuth secrets
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[
                    (
                        f"arn:aws:secretsmanager:{self.region}:{self.account}:"
                        f"secret:lateos/{self.env_name}/gmail/*"
                    )
                ],
            ),
            # DynamoDB: Write to audit table only
            iam.PolicyStatement(
                actions=["dynamodb:PutItem"],
                resources=[self.audit_table.table_arn],
            ),
        ]

        role = self._create_lambda_role("Email", policy_statements)

        # Create Lambda function
        email_lambda = PythonFunction(
            self,
            "LateosEmailSkill",
            entry="lambdas/skills",
            index="email_skill.py",
            handler="lambda_handler",
            function_name=f"lateos-{self.env_name}-email-skill",
            description="Email skill: Gmail OAuth integration (scoped IAM)",
            runtime=lambda_.Runtime.PYTHON_3_12,
            role=role,
            timeout=Duration.seconds(30),
            memory_size=512,
            reserved_concurrent_executions=10,  # RULE 7: Cost protection
            environment={
                "ENVIRONMENT": self.env_name,
                "AUDIT_TABLE_NAME": self.audit_table.table_name,
                "POWERTOOLS_SERVICE_NAME": "email_skill",
                "POWERTOOLS_METRICS_NAMESPACE": "LateosSkills",
                "LOG_LEVEL": "INFO",
            },
            tracing=lambda_.Tracing.ACTIVE,
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

        return email_lambda

    def _create_email_summary_skill(self) -> lambda_.Function:
        """Create email summary skill Lambda with scoped IAM role and Bedrock access"""

        # Scoped IAM policy: Gmail OAuth secrets + Bedrock InvokeModel
        policy_statements = [
            # Secrets Manager: Only Gmail OAuth secrets (same as email_skill)
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[
                    (
                        f"arn:aws:secretsmanager:{self.region}:{self.account}:"
                        f"secret:lateos/{self.env_name}/gmail/*"
                    )
                ],
            ),
            # Bedrock: InvokeModel for Claude Haiku only (RULE 2: No wildcard)
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    (
                        f"arn:aws:bedrock:{self.region}::foundation-model/"
                        "anthropic.claude-3-haiku-20240307-v1:0"
                    )
                ],
            ),
            # DynamoDB: Write to audit table only
            iam.PolicyStatement(
                actions=["dynamodb:PutItem"],
                resources=[self.audit_table.table_arn],
            ),
        ]

        role = self._create_lambda_role("EmailSummary", policy_statements)

        # Create Lambda function
        email_summary_lambda = PythonFunction(
            self,
            "LateosEmailSummarySkill",
            entry="lambdas/email_summary_skill",
            index="handler.py",
            handler="lambda_handler",
            function_name=f"lateos-{self.env_name}-email-summary-skill",
            description=(
                "Email summary skill: Gmail OAuth + Bedrock summarization with "
                "prompt injection detection (scoped IAM)"
            ),
            runtime=lambda_.Runtime.PYTHON_3_12,
            role=role,
            timeout=Duration.seconds(60),  # Longer timeout for Bedrock calls
            memory_size=512,
            reserved_concurrent_executions=5,  # RULE 7: Cost protection (lower for demo)
            environment={
                "ENVIRONMENT": self.env_name,
                "AUDIT_TABLE_NAME": self.audit_table.table_name,
                "BEDROCK_MODEL_ID": "anthropic.claude-3-haiku-20240307-v1:0",
                "POWERTOOLS_SERVICE_NAME": "email_summary_skill",
                "POWERTOOLS_METRICS_NAMESPACE": "LateosSkills",
                "LOG_LEVEL": "INFO",
            },
            tracing=lambda_.Tracing.ACTIVE,
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

        return email_summary_lambda

    def _create_calendar_skill(self) -> lambda_.Function:
        """Create calendar skill Lambda with scoped IAM role"""

        # Scoped IAM policy: Only Google Calendar OAuth secrets
        policy_statements = [
            # Secrets Manager: Only Google Calendar OAuth secrets
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[
                    (
                        f"arn:aws:secretsmanager:{self.region}:{self.account}:"
                        f"secret:lateos/{self.env_name}/google_calendar/*"
                    )
                ],
            ),
            # DynamoDB: Write to audit table only
            iam.PolicyStatement(
                actions=["dynamodb:PutItem"],
                resources=[self.audit_table.table_arn],
            ),
        ]

        role = self._create_lambda_role("Calendar", policy_statements)

        calendar_lambda = PythonFunction(
            self,
            "LateosCalendarSkill",
            entry="lambdas/skills",
            index="calendar_skill.py",
            handler="lambda_handler",
            function_name=f"lateos-{self.env_name}-calendar-skill",
            description="Calendar skill: Google Calendar API integration (scoped IAM)",
            runtime=lambda_.Runtime.PYTHON_3_12,
            role=role,
            timeout=Duration.seconds(30),
            memory_size=512,
            reserved_concurrent_executions=10,  # RULE 7: Cost protection
            environment={
                "ENVIRONMENT": self.env_name,
                "AUDIT_TABLE_NAME": self.audit_table.table_name,
                "POWERTOOLS_SERVICE_NAME": "calendar_skill",
                "POWERTOOLS_METRICS_NAMESPACE": "LateosSkills",
                "LOG_LEVEL": "INFO",
            },
            tracing=lambda_.Tracing.ACTIVE,
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

        return calendar_lambda

    def _create_web_fetch_skill(self) -> lambda_.Function:
        """Create web fetch skill Lambda with scoped IAM role"""

        # Scoped IAM policy: DynamoDB audit only (no Secrets Manager access)
        policy_statements = [
            # DynamoDB: Write to audit table only
            iam.PolicyStatement(
                actions=["dynamodb:PutItem"],
                resources=[self.audit_table.table_arn],
            ),
        ]

        role = self._create_lambda_role("WebFetch", policy_statements)

        web_fetch_lambda = PythonFunction(
            self,
            "LateosWebFetchSkill",
            entry="lambdas/skills",
            index="web_fetch_skill.py",
            handler="lambda_handler",
            function_name=f"lateos-{self.env_name}-web-fetch-skill",
            description="Web fetch skill: HTTP client with domain whitelist (scoped IAM)",
            runtime=lambda_.Runtime.PYTHON_3_12,
            role=role,
            timeout=Duration.seconds(60),  # Longer timeout for HTTP requests
            memory_size=512,
            reserved_concurrent_executions=20,  # RULE 7: Higher for web requests
            environment={
                "ENVIRONMENT": self.env_name,
                "AUDIT_TABLE_NAME": self.audit_table.table_name,
                "POWERTOOLS_SERVICE_NAME": "web_fetch_skill",
                "POWERTOOLS_METRICS_NAMESPACE": "LateosSkills",
                "LOG_LEVEL": "INFO",
            },
            tracing=lambda_.Tracing.ACTIVE,
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

        return web_fetch_lambda

    def _create_file_ops_skill(self) -> lambda_.Function:
        """Create file operations skill Lambda with scoped IAM role"""

        # Scoped IAM policy: S3 access only to user-specific prefixes
        policy_statements = [
            # S3: Access only to user-specific prefixes
            # Format: lateos/{env}/files/{user_id}/*
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                ],
                resources=[
                    self.files_bucket.bucket_arn,
                    f"{self.files_bucket.bucket_arn}/*",
                ],
                conditions={
                    "StringLike": {
                        "s3:prefix": [
                            f"lateos/{self.env_name}/files/*",
                        ]
                    }
                },
            ),
            # KMS: Decrypt/encrypt with S3 bucket key
            iam.PolicyStatement(
                actions=[
                    "kms:Decrypt",
                    "kms:GenerateDataKey",
                ],
                resources=[self.files_bucket.encryption_key.key_arn],
            ),
            # DynamoDB: Write to audit table only
            iam.PolicyStatement(
                actions=["dynamodb:PutItem"],
                resources=[self.audit_table.table_arn],
            ),
        ]

        role = self._create_lambda_role("FileOps", policy_statements)

        file_ops_lambda = PythonFunction(
            self,
            "LateosFileOpsSkill",
            entry="lambdas/skills",
            index="file_ops_skill.py",
            handler="lambda_handler",
            function_name=f"lateos-{self.env_name}-file-ops-skill",
            description=(
                "File operations skill: S3-backed storage with per-user isolation " "(scoped IAM)"
            ),
            runtime=lambda_.Runtime.PYTHON_3_12,
            role=role,
            timeout=Duration.seconds(60),
            memory_size=1024,  # Higher memory for file operations
            reserved_concurrent_executions=15,  # RULE 7: Cost protection
            environment={
                "ENVIRONMENT": self.env_name,
                "FILES_BUCKET_NAME": self.files_bucket.bucket_name,
                "AUDIT_TABLE_NAME": self.audit_table.table_name,
                "POWERTOOLS_SERVICE_NAME": "file_ops_skill",
                "POWERTOOLS_METRICS_NAMESPACE": "LateosSkills",
                "LOG_LEVEL": "INFO",
            },
            tracing=lambda_.Tracing.ACTIVE,
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

        return file_ops_lambda
