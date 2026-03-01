#!/usr/bin/env python3
"""
Lateos Architecture Diagram Generator

Generates lateos-architecture.png showing the complete AWS serverless architecture.
This diagram is code-generated to ensure it stays in sync with the actual CDK stacks.
"""

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.cost import CostExplorer
from diagrams.aws.database import Dynamodb
from diagrams.aws.general import User
from diagrams.aws.integration import StepFunctions
from diagrams.aws.management import Cloudtrail, Cloudwatch
from diagrams.aws.network import APIGateway
from diagrams.aws.security import IAM, KMS, Cognito, SecretsManager
from diagrams.aws.storage import S3

# Diagram configuration
graph_attr = {
    "fontsize": "14",
    "bgcolor": "white",
    "pad": "0.5",
}

with Diagram(
    "Lateos - Security-by-Design AI Personal Agent",
    filename="docs/diagrams/lateos-architecture",
    show=False,
    direction="TB",
    graph_attr=graph_attr,
):
    # User
    user = User("User")

    # Ingestion Layer
    with Cluster("Ingestion Layer (CoreStack)"):
        cognito = Cognito("Cognito User Pool\n(MFA enforced)")
        api_gateway = APIGateway("API Gateway\n(100 req/s burst)\nPOST /agent")

    # Orchestration Layer
    with Cluster("Orchestration Layer (OrchestrationStack)"):
        stepfunctions_workflow = StepFunctions("Step Functions\nExpress Workflow\n(5-min timeout)")

        validator = Lambda("Validator\nLambda")
        orchestrator = Lambda("Orchestrator\nLambda")
        intent_classifier = Lambda("Intent Classifier\nLambda")
        action_router = Lambda("Action Router\nLambda")
        output_sanitizer = Lambda("Output Sanitizer\nLambda")

    # Skills Layer
    with Cluster("Skills Layer (SkillsStack)"):
        email_skill = Lambda("Email Skill\nGmail OAuth")
        calendar_skill = Lambda("Calendar Skill\nGoogle Calendar")
        web_fetch_skill = Lambda("Web Fetch Skill\nHTTP + whitelist")
        file_ops_skill = Lambda("File Ops Skill\nS3 per-user")

    # Data Layer
    with Cluster("Data Layer (MemoryStack)"):
        kms_memory = KMS("KMS Key\n(MemoryStack)")
        with Cluster("DynamoDB Tables (KMS encrypted)"):
            conversations_table = Dynamodb("conversations\n(user_id partition)")
            memory_table = Dynamodb("agent_memory\n(user_id partition)")
            audit_table = Dynamodb("audit_logs\n(user_id partition)")
            prefs_table = Dynamodb("user_preferences\n(user_id partition)")

        secrets_mgr = SecretsManager("Secrets Manager\nOAuth tokens\nper-user")
        s3_files = S3("S3 Bucket\nKMS encrypted\nper-user prefix")

    # Cost Protection Layer
    with Cluster("Cost Protection (CostProtectionStack)"):
        budget = CostExplorer("AWS Budget\n$10/month")
        kill_switch = Lambda("Kill Switch\nLambda")
        alarm = Cloudwatch("CloudWatch\nAlarm")

    # Observability Layer
    with Cluster("Observability"):
        cloudwatch_logs = Cloudwatch("CloudWatch Logs\nKMS encrypted")
        cloudtrail = Cloudtrail("CloudTrail\nFull audit trail")

    # Security Layer
    with Cluster("Security Controls"):
        kms_core = KMS("KMS Key\n(CoreStack)")
        iam_roles = IAM("Scoped IAM Roles\n1 per Lambda")

    # Request flow
    user >> Edge(label="1. HTTPS + JWT") >> api_gateway
    api_gateway >> Edge(label="2. Auth check") >> cognito
    cognito >> Edge(label="3. Start exec") >> stepfunctions_workflow

    # Pipeline flow
    stepfunctions_workflow >> Edge(label="4. Validate") >> validator
    validator >> Edge(label="5. Extract context") >> orchestrator
    orchestrator >> Edge(label="6. Classify") >> intent_classifier
    intent_classifier >> Edge(label="7. Route") >> action_router

    # Skill routing (branching)
    action_router >> Edge(label="8a. EMAIL") >> email_skill
    action_router >> Edge(label="8b. CALENDAR") >> calendar_skill
    action_router >> Edge(label="8c. WEB") >> web_fetch_skill
    action_router >> Edge(label="8d. FILE") >> file_ops_skill

    # Skills merge back
    email_skill >> Edge(label="9. Result") >> output_sanitizer
    calendar_skill >> Edge(label="9. Result") >> output_sanitizer
    web_fetch_skill >> Edge(label="9. Result") >> output_sanitizer
    file_ops_skill >> Edge(label="9. Result") >> output_sanitizer

    # Response flow
    output_sanitizer >> Edge(label="10. Sanitized") >> stepfunctions_workflow
    stepfunctions_workflow >> Edge(label="11. Response") >> api_gateway
    api_gateway >> Edge(label="12. 200 OK") >> user

    # Data access patterns
    orchestrator >> Edge(label="RULE 6: user_id scoped") >> audit_table
    email_skill >> Edge(label="RULE 1: OAuth token") >> secrets_mgr
    calendar_skill >> Edge(label="RULE 1: OAuth token") >> secrets_mgr
    file_ops_skill >> Edge(label="RULE 6: per-user prefix") >> s3_files

    # Encryption
    conversations_table >> Edge(style="dashed", label="encrypted") >> kms_memory
    memory_table >> Edge(style="dashed", label="encrypted") >> kms_memory
    audit_table >> Edge(style="dashed", label="encrypted") >> kms_memory
    prefs_table >> Edge(style="dashed", label="encrypted") >> kms_memory
    s3_files >> Edge(style="dashed", label="encrypted") >> kms_memory
    cloudwatch_logs >> Edge(style="dashed", label="encrypted") >> kms_core

    # Cost protection flow
    alarm >> Edge(label="Budget exceeded") >> kill_switch
    kill_switch >> Edge(label="Disable stage") >> api_gateway

    # Observability
    stepfunctions_workflow >> Edge(style="dotted", label="logs") >> cloudwatch_logs
    validator >> Edge(style="dotted", label="audit") >> cloudtrail
    orchestrator >> Edge(style="dotted", label="audit") >> cloudtrail

    # IAM enforcement
    email_skill >> Edge(style="dashed", label="RULE 2: scoped") >> iam_roles
    calendar_skill >> Edge(style="dashed", label="RULE 2: scoped") >> iam_roles
    web_fetch_skill >> Edge(style="dashed", label="RULE 2: scoped") >> iam_roles
    file_ops_skill >> Edge(style="dashed", label="RULE 2: scoped") >> iam_roles

print("✓ Architecture diagram generated: docs/diagrams/lateos-architecture.png")
