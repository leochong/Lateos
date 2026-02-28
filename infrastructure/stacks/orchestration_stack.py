"""
Lateos Orchestration Stack

Provides the serverless orchestration infrastructure:
- AWS Step Functions Express Workflows for request orchestration
- Lambda functions for core orchestration logic (placeholder scaffolds)
- Lambda execution roles with scoped permissions (RULE 2)
- Integration with CoreStack API Gateway and Cognito

Security Rules Enforced:
- RULE 2: Scoped IAM policies, no wildcards
- RULE 7: Reserved concurrency on all Lambdas
- RULE 8: Encrypted logging, no plaintext secrets
"""

from typing import TYPE_CHECKING

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
)
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct

if TYPE_CHECKING:
    from .core_stack import CoreStack


class OrchestrationStack(Stack):
    """
    Orchestration stack for Lateos.

    Provides Step Functions and Lambda functions for request processing.
    Integrates with CoreStack for API Gateway and authentication.
    """

    def __init__(
        self, scope: Construct, construct_id: str, core_stack: "CoreStack", **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Get configuration from cdk.json context
        environment = self.node.try_get_context("environment") or "dev"
        lambda_memory = self.node.try_get_context("lambda_default_memory_mb") or 512
        lambda_timeout = self.node.try_get_context("lambda_default_timeout_seconds") or 30
        lambda_concurrency = self.node.try_get_context("lambda_default_reserved_concurrency") or 10

        # Lambda execution role for orchestrator (RULE 2: scoped permissions)
        orchestrator_role = iam.Role(
            self,
            "LateosOrchestratorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Execution role for Lateos orchestrator Lambda",
            role_name=f"lateos-{environment}-orchestrator-role",
        )

        # Grant CloudWatch Logs permissions (encrypted logs)
        orchestrator_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowCloudWatchLogs",
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:"
                    f"/aws/lambda/lateos-{environment}-orchestrator:*"
                ],
            )
        )

        # Grant X-Ray tracing permissions
        orchestrator_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowXRayTracing",
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                ],
                resources=["*"],  # X-Ray requires wildcard per AWS documentation
            )
        )

        # Orchestrator Lambda (Phase 2 implementation)
        self.orchestrator_lambda = lambda_.Function(
            self,
            "LateosOrchestrator",
            function_name=f"lateos-{environment}-orchestrator",
            description="Lateos orchestration Lambda - coordinates agent request flow",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="orchestrator.handler",
            code=lambda_.Code.from_asset("lambdas/core"),
            memory_size=lambda_memory,
            timeout=Duration.seconds(lambda_timeout),
            reserved_concurrent_executions=lambda_concurrency,  # RULE 7
            role=orchestrator_role,
            tracing=lambda_.Tracing.ACTIVE,
            environment={
                "ENVIRONMENT": environment,
                "LOG_LEVEL": "INFO",
                "POWERTOOLS_SERVICE_NAME": "orchestrator",
            },
            log_retention=logs.RetentionDays.THREE_MONTHS,
        )

        # Input validator Lambda role
        validator_role = iam.Role(
            self,
            "LateosValidatorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Execution role for Lateos input validator Lambda",
            role_name=f"lateos-{environment}-validator-role",
        )

        validator_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowCloudWatchLogs",
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:"
                    f"/aws/lambda/lateos-{environment}-validator:*"
                ],
            )
        )

        validator_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowXRayTracing",
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                ],
                resources=["*"],
            )
        )

        # Input validator Lambda (Phase 2 implementation with prompt injection detection)
        self.validator_lambda = lambda_.Function(
            self,
            "LateosValidator",
            function_name=f"lateos-{environment}-validator",
            description="Lateos input validator - sanitizes and validates user input (RULE 5)",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="validator.handler",
            code=lambda_.Code.from_asset("lambdas/core"),
            memory_size=lambda_memory,
            timeout=Duration.seconds(lambda_timeout),
            reserved_concurrent_executions=lambda_concurrency,  # RULE 7
            role=validator_role,
            tracing=lambda_.Tracing.ACTIVE,
            environment={
                "ENVIRONMENT": environment,
                "LOG_LEVEL": "INFO",
                "POWERTOOLS_SERVICE_NAME": "validator",
            },
            log_retention=logs.RetentionDays.THREE_MONTHS,
        )

        # Step Functions execution role
        sfn_role = iam.Role(
            self,
            "LateosStateMachineRole",
            assumed_by=iam.ServicePrincipal("states.amazonaws.com"),
            description="Execution role for Lateos Step Functions state machine",
            role_name=f"lateos-{environment}-statemachine-role",
        )

        # Grant permission to invoke Lambda functions (scoped to our Lambdas only)
        sfn_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowInvokeLambdas",
                actions=["lambda:InvokeFunction"],
                resources=[
                    self.orchestrator_lambda.function_arn,
                    self.validator_lambda.function_arn,
                ],
            )
        )

        # Grant CloudWatch Logs permissions for Express Workflows
        sfn_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowCloudWatchLogs",
                actions=[
                    "logs:CreateLogDelivery",
                    "logs:GetLogDelivery",
                    "logs:UpdateLogDelivery",
                    "logs:DeleteLogDelivery",
                    "logs:ListLogDeliveries",
                    "logs:PutResourcePolicy",
                    "logs:DescribeResourcePolicies",
                    "logs:DescribeLogGroups",
                ],
                resources=["*"],  # Required for Step Functions logging per AWS docs
            )
        )

        # Step Functions Express Workflow (placeholder - actual workflow in Phase 2)
        # Define the workflow
        validate_task = tasks.LambdaInvoke(
            self,
            "ValidateInput",
            lambda_function=self.validator_lambda,
            output_path="$.Payload",
        )

        orchestrate_task = tasks.LambdaInvoke(
            self,
            "Orchestrate",
            lambda_function=self.orchestrator_lambda,
            output_path="$.Payload",
        )

        # Simple linear workflow: Validate → Orchestrate
        workflow_definition = validate_task.next(orchestrate_task)

        # Create log group for state machine
        # Note: Using separate KMS key to avoid circular dependency with CoreStack
        from aws_cdk import RemovalPolicy  # noqa: E402
        from aws_cdk import aws_kms as kms  # noqa: E402

        sfn_log_key = kms.Key(
            self,
            "LateosStateMachineLogKey",
            description="Lateos Step Functions log encryption key",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.RETAIN,
            alias=f"alias/lateos/{environment}/sfn-logs",
        )

        # Grant CloudWatch Logs permission to use the key
        sfn_log_key.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowCloudWatchLogsEncryption",
                principals=[iam.ServicePrincipal(f"logs.{self.region}.amazonaws.com")],
                actions=[
                    "kms:Encrypt",
                    "kms:Decrypt",
                    "kms:ReEncrypt*",
                    "kms:GenerateDataKey*",
                    "kms:CreateGrant",
                    "kms:DescribeKey",
                ],
                resources=["*"],
                conditions={
                    "ArnLike": {
                        "kms:EncryptionContext:aws:logs:arn": (
                            f"arn:aws:logs:{self.region}:{self.account}:"
                            f"log-group:/aws/vendedlogs/states/"
                            f"lateos-{environment}-workflow"
                        )
                    }
                },
            )
        )

        sfn_log_group = logs.LogGroup(
            self,
            "LateosStateMachineLogGroup",
            log_group_name=f"/aws/vendedlogs/states/lateos-{environment}-workflow",
            encryption_key=sfn_log_key,
            retention=logs.RetentionDays.THREE_MONTHS,
        )

        # Create the state machine (Express Workflow for low latency)
        self.state_machine = sfn.StateMachine(
            self,
            "LateosStateMachine",
            state_machine_name=f"lateos-{environment}-workflow",
            definition_body=sfn.DefinitionBody.from_chainable(workflow_definition),
            state_machine_type=sfn.StateMachineType.EXPRESS,
            role=sfn_role,
            logs=sfn.LogOptions(
                destination=sfn_log_group,
                level=sfn.LogLevel.ALL,
                include_execution_data=True,
            ),
            tracing_enabled=True,
        )

        # Add API Gateway integration
        # Create /agent POST endpoint that triggers orchestrator
        agent_resource = core_stack.api.root.add_resource("agent")

        # API Gateway role to invoke Lambda
        api_lambda_role = iam.Role(
            self,
            "LateosApiLambdaRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
            description="API Gateway role to invoke orchestrator Lambda",
        )

        api_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=[self.orchestrator_lambda.function_arn],
            )
        )

        # Lambda integration for orchestrator
        orchestrator_integration = apigw.LambdaIntegration(
            self.orchestrator_lambda,
            credentials_role=api_lambda_role,
            proxy=True,
        )

        # Add POST /agent endpoint (Cognito-protected)
        agent_resource.add_method(
            "POST",
            orchestrator_integration,
            authorizer=core_stack.authorizer,
            request_validator=core_stack.request_validator,
        )

        # Outputs
        CfnOutput(
            self,
            "StateMachineArn",
            value=self.state_machine.state_machine_arn,
            description="Step Functions state machine ARN",
            export_name=f"lateos-{environment}-statemachine-arn",
        )

        CfnOutput(
            self,
            "OrchestratorFunctionArn",
            value=self.orchestrator_lambda.function_arn,
            description="Orchestrator Lambda function ARN",
            export_name=f"lateos-{environment}-orchestrator-arn",
        )

        CfnOutput(
            self,
            "ValidatorFunctionArn",
            value=self.validator_lambda.function_arn,
            description="Validator Lambda function ARN",
            export_name=f"lateos-{environment}-validator-arn",
        )
