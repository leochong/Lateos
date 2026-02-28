"""
Lateos Memory Stack

Provides the persistent storage infrastructure for agent memory and audit logs:
- DynamoDB tables with KMS encryption
- Per-user partition key isolation (RULE 6)
- Point-in-time recovery enabled
- TTL for ephemeral data
- Audit log table for compliance

Security Rules Enforced:
- RULE 1: No secrets in environment variables (use Secrets Manager)
- RULE 2: Scoped IAM policies, no wildcards
- RULE 6: User_id partition key for data isolation
- RULE 8: KMS encryption for data at rest
"""

from aws_cdk import (
    CfnOutput,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_kms as kms
from constructs import Construct


class MemoryStack(Stack):
    """
    Memory and storage stack for Lateos.

    Provides DynamoDB tables for agent memory, conversation history, and audit logs.
    All tables use KMS encryption and per-user partitioning.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Get configuration from cdk.json context
        environment = self.node.try_get_context("environment") or "dev"
        billing_mode_str = self.node.try_get_context("dynamodb_billing_mode") or "PAY_PER_REQUEST"
        pitr_enabled = self.node.try_get_context("dynamodb_point_in_time_recovery")
        if pitr_enabled is None:
            pitr_enabled = True

        # Map billing mode string to enum
        billing_mode = (
            dynamodb.BillingMode.PAY_PER_REQUEST
            if billing_mode_str == "PAY_PER_REQUEST"
            else dynamodb.BillingMode.PROVISIONED
        )

        # KMS key for DynamoDB table encryption (RULE 8)
        self.dynamodb_key = kms.Key(
            self,
            "LateosDynamoDbKey",
            description="Lateos DynamoDB table encryption key",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.RETAIN,  # Never delete encryption keys
            alias=f"alias/lateos/{environment}/dynamodb",
        )

        # Conversation Memory Table (RULE 6: user_id partition key)
        self.conversation_table = dynamodb.Table(
            self,
            "LateosConversationTable",
            table_name=f"lateos-{environment}-conversations",
            partition_key=dynamodb.Attribute(
                name="user_id",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="conversation_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=billing_mode,
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=self.dynamodb_key,
            point_in_time_recovery=pitr_enabled,
            removal_policy=RemovalPolicy.RETAIN if environment == "prod" else RemovalPolicy.DESTROY,
            time_to_live_attribute="ttl",  # Automatic cleanup of old conversations
        )

        # Add GSI for querying by timestamp (optional, for analytics)
        self.conversation_table.add_global_secondary_index(
            index_name="UserTimestampIndex",
            partition_key=dynamodb.Attribute(
                name="user_id",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="created_at",
                type=dynamodb.AttributeType.STRING,
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # Agent Memory Table (short-term working memory)
        self.agent_memory_table = dynamodb.Table(
            self,
            "LateosAgentMemoryTable",
            table_name=f"lateos-{environment}-agent-memory",
            partition_key=dynamodb.Attribute(
                name="user_id",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="memory_key",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=billing_mode,
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=self.dynamodb_key,
            point_in_time_recovery=pitr_enabled,
            removal_policy=RemovalPolicy.RETAIN if environment == "prod" else RemovalPolicy.DESTROY,
            time_to_live_attribute="ttl",  # TTL for ephemeral memory
        )

        # Audit Log Table (RULE 8: encrypted audit trail)
        self.audit_log_table = dynamodb.Table(
            self,
            "LateosAuditLogTable",
            table_name=f"lateos-{environment}-audit-logs",
            partition_key=dynamodb.Attribute(
                name="user_id",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=billing_mode,
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=self.dynamodb_key,
            point_in_time_recovery=pitr_enabled,
            removal_policy=RemovalPolicy.RETAIN,  # Always retain audit logs
            stream=dynamodb.StreamViewType.NEW_IMAGE,  # Enable streams for audit processing
        )

        # Add GSI for querying by action type (for audit analytics)
        self.audit_log_table.add_global_secondary_index(
            index_name="ActionTypeIndex",
            partition_key=dynamodb.Attribute(
                name="action_type",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING,
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # User Preferences Table
        self.user_preferences_table = dynamodb.Table(
            self,
            "LateosUserPreferencesTable",
            table_name=f"lateos-{environment}-user-preferences",
            partition_key=dynamodb.Attribute(
                name="user_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=billing_mode,
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=self.dynamodb_key,
            point_in_time_recovery=pitr_enabled,
            removal_policy=RemovalPolicy.RETAIN,  # Retain user preferences
        )

        # Outputs
        CfnOutput(
            self,
            "ConversationTableName",
            value=self.conversation_table.table_name,
            description="Conversation history table name",
            export_name=f"lateos-{environment}-conversation-table",
        )

        CfnOutput(
            self,
            "ConversationTableArn",
            value=self.conversation_table.table_arn,
            description="Conversation history table ARN",
            export_name=f"lateos-{environment}-conversation-table-arn",
        )

        CfnOutput(
            self,
            "AgentMemoryTableName",
            value=self.agent_memory_table.table_name,
            description="Agent memory table name",
            export_name=f"lateos-{environment}-agent-memory-table",
        )

        CfnOutput(
            self,
            "AgentMemoryTableArn",
            value=self.agent_memory_table.table_arn,
            description="Agent memory table ARN",
            export_name=f"lateos-{environment}-agent-memory-table-arn",
        )

        CfnOutput(
            self,
            "AuditLogTableName",
            value=self.audit_log_table.table_name,
            description="Audit log table name",
            export_name=f"lateos-{environment}-audit-log-table",
        )

        CfnOutput(
            self,
            "AuditLogTableArn",
            value=self.audit_log_table.table_arn,
            description="Audit log table ARN",
            export_name=f"lateos-{environment}-audit-log-table-arn",
        )

        CfnOutput(
            self,
            "UserPreferencesTableName",
            value=self.user_preferences_table.table_name,
            description="User preferences table name",
            export_name=f"lateos-{environment}-user-preferences-table",
        )

        CfnOutput(
            self,
            "UserPreferencesTableArn",
            value=self.user_preferences_table.table_arn,
            description="User preferences table ARN",
            export_name=f"lateos-{environment}-user-preferences-table-arn",
        )

        CfnOutput(
            self,
            "DynamoDbKeyArn",
            value=self.dynamodb_key.key_arn,
            description="DynamoDB KMS encryption key ARN",
            export_name=f"lateos-{environment}-dynamodb-key-arn",
        )
