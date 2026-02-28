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

from typing import TYPE_CHECKING, Optional

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct

if TYPE_CHECKING:
    from .core_stack import CoreStack
    from .skills_stack import SkillsStack


class OrchestrationStack(Stack):
    """
    Orchestration stack for Lateos.

    Provides Step Functions and Lambda functions for request processing.
    Integrates with CoreStack for API Gateway and authentication.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        core_stack: "CoreStack",
        skills_stack: Optional["SkillsStack"] = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.skills_stack = skills_stack

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
            log_retention=logs.RetentionDays.ONE_MONTH,
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
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

        # Intent classifier Lambda role
        intent_classifier_role = iam.Role(
            self,
            "LateosIntentClassifierRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Execution role for Lateos intent classifier Lambda",
            role_name=f"lateos-{environment}-intent-classifier-role",
        )

        intent_classifier_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowCloudWatchLogs",
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:"
                    f"/aws/lambda/lateos-{environment}-intent-classifier:*"
                ],
            )
        )

        intent_classifier_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowXRayTracing",
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                ],
                resources=["*"],
            )
        )

        # Intent classifier Lambda
        self.intent_classifier_lambda = lambda_.Function(
            self,
            "LateosIntentClassifier",
            function_name=f"lateos-{environment}-intent-classifier",
            description="Lateos intent classifier - determines user intent from validated input",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="intent_classifier.handler",
            code=lambda_.Code.from_asset("lambdas/core"),
            memory_size=lambda_memory,
            timeout=Duration.seconds(lambda_timeout),
            reserved_concurrent_executions=lambda_concurrency,  # RULE 7
            role=intent_classifier_role,
            tracing=lambda_.Tracing.ACTIVE,
            environment={
                "ENVIRONMENT": environment,
                "LOG_LEVEL": "INFO",
                "POWERTOOLS_SERVICE_NAME": "intent-classifier",
            },
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

        # Action router Lambda role
        action_router_role = iam.Role(
            self,
            "LateosActionRouterRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Execution role for Lateos action router Lambda",
            role_name=f"lateos-{environment}-action-router-role",
        )

        action_router_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowCloudWatchLogs",
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:"
                    f"/aws/lambda/lateos-{environment}-action-router:*"
                ],
            )
        )

        action_router_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowXRayTracing",
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                ],
                resources=["*"],
            )
        )

        # Action router Lambda
        self.action_router_lambda = lambda_.Function(
            self,
            "LateosActionRouter",
            function_name=f"lateos-{environment}-action-router",
            description="Lateos action router - routes classified intents to appropriate skills",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="action_router.handler",
            code=lambda_.Code.from_asset("lambdas/core"),
            memory_size=lambda_memory,
            timeout=Duration.seconds(lambda_timeout),
            reserved_concurrent_executions=lambda_concurrency,  # RULE 7
            role=action_router_role,
            tracing=lambda_.Tracing.ACTIVE,
            environment={
                "ENVIRONMENT": environment,
                "LOG_LEVEL": "INFO",
                "POWERTOOLS_SERVICE_NAME": "action-router",
            },
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

        # Output sanitizer Lambda role
        output_sanitizer_role = iam.Role(
            self,
            "LateosOutputSanitizerRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Execution role for Lateos output sanitizer Lambda",
            role_name=f"lateos-{environment}-output-sanitizer-role",
        )

        output_sanitizer_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowCloudWatchLogs",
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:"
                    f"/aws/lambda/lateos-{environment}-output-sanitizer:*"
                ],
            )
        )

        output_sanitizer_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowXRayTracing",
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                ],
                resources=["*"],
            )
        )

        # Output sanitizer Lambda
        self.output_sanitizer_lambda = lambda_.Function(
            self,
            "LateosOutputSanitizer",
            function_name=f"lateos-{environment}-output-sanitizer",
            description=(
                "Lateos output sanitizer - sanitizes skill outputs before user delivery (RULE 8)"
            ),
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="output_sanitizer.handler",
            code=lambda_.Code.from_asset("lambdas/core"),
            memory_size=lambda_memory,
            timeout=Duration.seconds(lambda_timeout),
            reserved_concurrent_executions=lambda_concurrency,  # RULE 7
            role=output_sanitizer_role,
            tracing=lambda_.Tracing.ACTIVE,
            environment={
                "ENVIRONMENT": environment,
                "LOG_LEVEL": "INFO",
                "POWERTOOLS_SERVICE_NAME": "output-sanitizer",
            },
            log_retention=logs.RetentionDays.ONE_MONTH,
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
        lambda_arns = [
            self.orchestrator_lambda.function_arn,
            self.validator_lambda.function_arn,
            self.intent_classifier_lambda.function_arn,
            self.action_router_lambda.function_arn,
            self.output_sanitizer_lambda.function_arn,
        ]

        # Add skill Lambda ARNs if skills_stack is provided
        if self.skills_stack is not None:
            if hasattr(self.skills_stack, "email_skill"):
                lambda_arns.append(self.skills_stack.email_skill.function_arn)
            if hasattr(self.skills_stack, "calendar_skill"):
                lambda_arns.append(self.skills_stack.calendar_skill.function_arn)
            if hasattr(self.skills_stack, "web_fetch_skill"):
                lambda_arns.append(self.skills_stack.web_fetch_skill.function_arn)
            if hasattr(self.skills_stack, "file_ops_skill"):
                lambda_arns.append(self.skills_stack.file_ops_skill.function_arn)

        sfn_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowInvokeLambdas",
                actions=["lambda:InvokeFunction"],
                resources=lambda_arns,
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

        # Step Functions Express Workflow - Complete request processing pipeline
        # Step 1: Validate user input (prompt injection detection)
        validate_task = tasks.LambdaInvoke(
            self,
            "ValidateInput",
            lambda_function=self.validator_lambda,
            output_path="$.Payload",
            comment="Validate and sanitize user input (RULE 5)",
        )

        # Step 2: Orchestrate request (user context, memory retrieval)
        orchestrate_task = tasks.LambdaInvoke(
            self,
            "Orchestrate",
            lambda_function=self.orchestrator_lambda,
            output_path="$.Payload",
            comment="Retrieve user context and conversation memory",
        )

        # Step 3: Classify user intent
        classify_intent_task = tasks.LambdaInvoke(
            self,
            "ClassifyIntent",
            lambda_function=self.intent_classifier_lambda,
            output_path="$.Payload",
            comment="Classify user intent using Bedrock",
        )

        # Step 4: Route to appropriate action
        route_action_task = tasks.LambdaInvoke(
            self,
            "RouteAction",
            lambda_function=self.action_router_lambda,
            output_path="$.Payload",
            comment="Determine which skill to invoke based on intent",
        )

        # Step 5: Choice state - route to appropriate skill Lambda
        # Default fallback if no skills_stack or skill not found
        skill_not_found = sfn.Fail(
            self,
            "SkillNotFound",
            error="SkillNotAvailable",
            cause="Requested skill is not available or not configured",
        )

        # Build choice conditions and skill invocation tasks
        choice = sfn.Choice(
            self, "RouteToSkill", comment="Route to appropriate skill based on action"
        )

        # Step 6: Output sanitizer (final step after skill execution)
        sanitize_output_task = tasks.LambdaInvoke(
            self,
            "SanitizeOutput",
            lambda_function=self.output_sanitizer_lambda,
            output_path="$.Payload",
            comment="Sanitize skill output before delivery (RULE 8)",
        )

        # Add skill routing only if skills_stack is provided
        if self.skills_stack is not None:
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

            # Calendar skill routing
            if hasattr(self.skills_stack, "calendar_skill"):
                calendar_skill_task = tasks.LambdaInvoke(
                    self,
                    "InvokeCalendarSkill",
                    lambda_function=self.skills_stack.calendar_skill,
                    output_path="$.Payload",
                    comment="Execute calendar skill",
                )
                calendar_skill_task.next(sanitize_output_task)
                choice.when(
                    sfn.Condition.string_equals("$.skill", "calendar"),
                    calendar_skill_task,
                )

            # Web fetch skill routing
            if hasattr(self.skills_stack, "web_fetch_skill"):
                web_fetch_skill_task = tasks.LambdaInvoke(
                    self,
                    "InvokeWebFetchSkill",
                    lambda_function=self.skills_stack.web_fetch_skill,
                    output_path="$.Payload",
                    comment="Execute web fetch skill",
                )
                web_fetch_skill_task.next(sanitize_output_task)
                choice.when(
                    sfn.Condition.string_equals("$.skill", "web_fetch"),
                    web_fetch_skill_task,
                )

            # File ops skill routing
            if hasattr(self.skills_stack, "file_ops_skill"):
                file_ops_skill_task = tasks.LambdaInvoke(
                    self,
                    "InvokeFileOpsSkill",
                    lambda_function=self.skills_stack.file_ops_skill,
                    output_path="$.Payload",
                    comment="Execute file operations skill",
                )
                file_ops_skill_task.next(sanitize_output_task)
                choice.when(
                    sfn.Condition.string_equals("$.skill", "file_ops"),
                    file_ops_skill_task,
                )

        # Default fallback if skill not found
        choice.otherwise(skill_not_found)

        # Build the complete workflow chain
        # Validate → Orchestrate → ClassifyIntent → RouteAction
        # → Choice (skill routing) → SanitizeOutput
        workflow_definition = (
            validate_task.next(orchestrate_task)
            .next(classify_intent_task)
            .next(route_action_task)
            .next(choice)
        )

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
            retention=logs.RetentionDays.ONE_MONTH,
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

        CfnOutput(
            self,
            "IntentClassifierFunctionArn",
            value=self.intent_classifier_lambda.function_arn,
            description="Intent classifier Lambda function ARN",
            export_name=f"lateos-{environment}-intent-classifier-arn",
        )

        CfnOutput(
            self,
            "ActionRouterFunctionArn",
            value=self.action_router_lambda.function_arn,
            description="Action router Lambda function ARN",
            export_name=f"lateos-{environment}-action-router-arn",
        )

        CfnOutput(
            self,
            "OutputSanitizerFunctionArn",
            value=self.output_sanitizer_lambda.function_arn,
            description="Output sanitizer Lambda function ARN",
            export_name=f"lateos-{environment}-output-sanitizer-arn",
        )
