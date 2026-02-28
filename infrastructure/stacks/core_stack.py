"""
Lateos Core Stack

Provides the foundational security and API infrastructure:
- API Gateway REST API with request validation and throttling
- Cognito User Pool with MFA enforcement
- CloudWatch Log Groups with KMS encryption
- AWS WAF Web ACL (optional, deferred to Phase 2 per ADR-011)

Security Rules Enforced:
- RULE 2: Scoped IAM policies, no wildcards
- RULE 3: No public endpoints without Cognito (WAF deferred to Phase 2)
- RULE 8: Encrypted logging, no plaintext secrets
"""

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_logs as logs
from aws_cdk import aws_wafv2 as wafv2
from constructs import Construct


class CoreStack(Stack):
    """
    Core infrastructure stack for Lateos.

    Provides API Gateway with throttling, Cognito authentication, and optional WAF.
    WAF is disabled by default (Phase 1) and will be enabled in Phase 2 per ADR-011.
    All resources follow security-by-design principles.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Get configuration from cdk.json context
        environment = self.node.try_get_context("environment") or "dev"
        cognito_mfa_setting = self.node.try_get_context("cognito_mfa") or "REQUIRED"
        log_retention_days = self.node.try_get_context("log_retention_days") or 90
        # WAF disabled by default per ADR-011 (deferred to Phase 2 for cost optimization)
        waf_enabled = self.node.try_get_context("waf_enabled")
        if waf_enabled is None:
            waf_enabled = False

        # KMS key for CloudWatch Logs encryption (RULE 8)
        self.log_encryption_key = kms.Key(
            self,
            "LateosLogEncryptionKey",
            description="Lateos CloudWatch Logs encryption key",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.RETAIN,  # Never delete encryption keys
            alias=f"alias/lateos/{environment}/logs",
        )

        # Grant CloudWatch Logs permission to use the key
        self.log_encryption_key.add_to_resource_policy(
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
                            f"log-group:/aws/lateos/{environment}/*"
                        )
                    }
                },
            )
        )

        # CloudWatch Log Group for API Gateway (encrypted)
        # Map log_retention_days to valid RetentionDays enum
        retention_mapping = {
            1: logs.RetentionDays.ONE_DAY,
            3: logs.RetentionDays.THREE_DAYS,
            5: logs.RetentionDays.FIVE_DAYS,
            7: logs.RetentionDays.ONE_WEEK,
            14: logs.RetentionDays.TWO_WEEKS,
            30: logs.RetentionDays.ONE_MONTH,
            60: logs.RetentionDays.TWO_MONTHS,
            90: logs.RetentionDays.THREE_MONTHS,
            120: logs.RetentionDays.FOUR_MONTHS,
            150: logs.RetentionDays.FIVE_MONTHS,
            180: logs.RetentionDays.SIX_MONTHS,
            365: logs.RetentionDays.ONE_YEAR,
            400: logs.RetentionDays.THIRTEEN_MONTHS,
            545: logs.RetentionDays.EIGHTEEN_MONTHS,
            731: logs.RetentionDays.TWO_YEARS,
            1827: logs.RetentionDays.FIVE_YEARS,
        }
        # Default to THREE_MONTHS if not found in mapping
        retention = retention_mapping.get(log_retention_days, logs.RetentionDays.THREE_MONTHS)

        self.api_log_group = logs.LogGroup(
            self,
            "LateosApiLogGroup",
            log_group_name=f"/aws/lateos/{environment}/api-gateway",
            encryption_key=self.log_encryption_key,
            retention=retention,
            removal_policy=RemovalPolicy.DESTROY if environment == "dev" else RemovalPolicy.RETAIN,
        )

        # Cognito User Pool with MFA enforcement (RULE 3)
        self.user_pool = cognito.UserPool(
            self,
            "LateosUserPool",
            user_pool_name=f"lateos-{environment}-users",
            self_sign_up_enabled=False,  # Admin-only user creation
            sign_in_aliases=cognito.SignInAliases(
                email=True,
                username=False,  # Email is the username
            ),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=16,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
                temp_password_validity=Duration.days(1),
            ),
            mfa=cognito.Mfa.REQUIRED if cognito_mfa_setting == "REQUIRED" else cognito.Mfa.OPTIONAL,
            mfa_second_factor=cognito.MfaSecondFactor(
                sms=True,
                otp=True,  # TOTP (time-based one-time password)
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            advanced_security_mode=cognito.AdvancedSecurityMode.ENFORCED,
            removal_policy=RemovalPolicy.RETAIN,  # Never delete user data
        )

        # Cognito User Pool Client
        self.user_pool_client = cognito.UserPoolClient(
            self,
            "LateosUserPoolClient",
            user_pool=self.user_pool,
            user_pool_client_name=f"lateos-{environment}-client",
            generate_secret=True,  # OAuth client secret
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,  # Secure Remote Password
                custom=False,  # No custom auth for security
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=True,
                    implicit_code_grant=False,  # Not secure
                ),
                scopes=[
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.PROFILE,
                ],
            ),
            access_token_validity=Duration.hours(1),
            id_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(30),
            prevent_user_existence_errors=True,
        )

        # API Gateway REST API
        self.api = apigw.RestApi(
            self,
            "LateosApi",
            rest_api_name=f"lateos-{environment}-api",
            description="Lateos AI Personal Agent API",
            deploy=True,
            deploy_options=apigw.StageOptions(
                stage_name=environment,
                throttling_rate_limit=100,  # requests per second
                throttling_burst_limit=200,  # concurrent requests
                logging_level=apigw.MethodLoggingLevel.INFO,
                access_log_destination=apigw.LogGroupLogDestination(self.api_log_group),
                access_log_format=apigw.AccessLogFormat.json_with_standard_fields(
                    caller=True,
                    http_method=True,
                    ip=True,
                    protocol=True,
                    request_time=True,
                    resource_path=True,
                    response_length=True,
                    status=True,
                    user=True,
                ),
                tracing_enabled=True,  # X-Ray tracing
                metrics_enabled=True,
            ),
            cloud_watch_role=True,  # Allow API Gateway to write logs
            endpoint_types=[apigw.EndpointType.REGIONAL],
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=["https://*.lateos.app"],  # Update with actual domain
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key"],
                max_age=Duration.hours(1),
            ),
        )

        # Cognito Authorizer for API Gateway (RULE 3: no public endpoints)
        # Note: Authorizer will be attached when OrchestrationStack adds API methods
        self.authorizer = apigw.CognitoUserPoolsAuthorizer(
            self,
            "LateosApiAuthorizer",
            cognito_user_pools=[self.user_pool],
            authorizer_name=f"lateos-{environment}-authorizer",
            identity_source="method.request.header.Authorization",
        )

        # Create a placeholder root resource to satisfy CDK (methods added in OrchestrationStack)
        self.api.root.add_method(
            "GET",
            apigw.MockIntegration(
                integration_responses=[
                    {
                        "statusCode": "200",
                        "responseTemplates": {
                            "application/json": (
                                '{"message": "Lateos API - Add methods in ' 'OrchestrationStack"}'
                            )
                        },
                    }
                ],
                passthrough_behavior=apigw.PassthroughBehavior.NEVER,
                request_templates={"application/json": '{"statusCode": 200}'},
            ),
            method_responses=[{"statusCode": "200"}],
            authorizer=self.authorizer,
        )

        # Request Validator for API Gateway (input validation)
        self.request_validator = apigw.RequestValidator(
            self,
            "LateosRequestValidator",
            rest_api=self.api,
            request_validator_name=f"lateos-{environment}-validator",
            validate_request_body=True,
            validate_request_parameters=True,
        )

        # WAF Web ACL for API Gateway (RULE 3)
        if waf_enabled:
            self.web_acl = wafv2.CfnWebACL(
                self,
                "LateosWebAcl",
                scope="REGIONAL",
                default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
                visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                    cloud_watch_metrics_enabled=True,
                    metric_name=f"lateos-{environment}-waf",
                    sampled_requests_enabled=True,
                ),
                name=f"lateos-{environment}-waf",
                description="WAF for Lateos API Gateway",
                rules=[
                    # AWS Managed Rules: Core Rule Set
                    wafv2.CfnWebACL.RuleProperty(
                        name="AWSManagedRulesCommonRuleSet",
                        priority=1,
                        statement=wafv2.CfnWebACL.StatementProperty(
                            managed_rule_group_statement=(
                                wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                                    vendor_name="AWS",
                                    name="AWSManagedRulesCommonRuleSet",
                                )
                            )
                        ),
                        override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
                        visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                            cloud_watch_metrics_enabled=True,
                            metric_name="AWSManagedRulesCommonRuleSetMetric",
                            sampled_requests_enabled=True,
                        ),
                    ),
                    # AWS Managed Rules: Known Bad Inputs
                    wafv2.CfnWebACL.RuleProperty(
                        name="AWSManagedRulesKnownBadInputsRuleSet",
                        priority=2,
                        statement=wafv2.CfnWebACL.StatementProperty(
                            managed_rule_group_statement=(
                                wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                                    vendor_name="AWS",
                                    name="AWSManagedRulesKnownBadInputsRuleSet",
                                )
                            )
                        ),
                        override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
                        visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                            cloud_watch_metrics_enabled=True,
                            metric_name="AWSManagedRulesKnownBadInputsRuleSetMetric",
                            sampled_requests_enabled=True,
                        ),
                    ),
                    # Rate limiting: 100 requests per 5 minutes per IP
                    wafv2.CfnWebACL.RuleProperty(
                        name="RateLimitRule",
                        priority=3,
                        statement=wafv2.CfnWebACL.StatementProperty(
                            rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                                limit=100,
                                aggregate_key_type="IP",
                            )
                        ),
                        action=wafv2.CfnWebACL.RuleActionProperty(block={}),
                        visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                            cloud_watch_metrics_enabled=True,
                            metric_name="RateLimitRuleMetric",
                            sampled_requests_enabled=True,
                        ),
                    ),
                ],
            )

            # Associate WAF with API Gateway
            wafv2.CfnWebACLAssociation(
                self,
                "LateosWebAclAssociation",
                resource_arn=self.api.deployment_stage.stage_arn,
                web_acl_arn=self.web_acl.attr_arn,
            )

        # Outputs
        CfnOutput(
            self,
            "UserPoolId",
            value=self.user_pool.user_pool_id,
            description="Cognito User Pool ID",
            export_name=f"lateos-{environment}-user-pool-id",
        )

        CfnOutput(
            self,
            "UserPoolClientId",
            value=self.user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID",
            export_name=f"lateos-{environment}-user-pool-client-id",
        )

        CfnOutput(
            self,
            "ApiUrl",
            value=self.api.url,
            description="API Gateway URL",
            export_name=f"lateos-{environment}-api-url",
        )

        CfnOutput(
            self,
            "LogEncryptionKeyArn",
            value=self.log_encryption_key.key_arn,
            description="KMS key ARN for log encryption",
            export_name=f"lateos-{environment}-log-encryption-key-arn",
        )
