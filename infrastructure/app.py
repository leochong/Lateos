#!/usr/bin/env python3
"""
Lateos CDK App Entry Point

Instantiates all infrastructure stacks for the Lateos AI Personal Agent.
Stacks are deployed in dependency order.
"""

import os

import aws_cdk as cdk
from stacks.core_stack import CoreStack
from stacks.cost_protection_stack import CostProtectionStack
from stacks.memory_stack import MemoryStack
from stacks.orchestration_stack import OrchestrationStack
from stacks.skills_stack import SkillsStack

app = cdk.App()

# Get configuration from cdk.json context
environment = app.node.try_get_context("environment") or "dev"
aws_region = app.node.try_get_context("aws_region") or "us-east-1"
resource_tags = app.node.try_get_context("resource_tags") or {}

# Define stack environment
env = cdk.Environment(
    account=os.environ.get("AWS_ACCOUNT_ID", "000000000000"),
    region=aws_region,
)

# Stack 1: Core Infrastructure (API Gateway, Cognito)
core_stack = CoreStack(
    app,
    f"LateosCore{environment.capitalize()}Stack",
    env=env,
    description=(
        "Lateos core infrastructure: API Gateway, Cognito, CloudWatch Logs "
        "(WAF deferred to Phase 2)"
    ),
)

# Stack 2: Orchestration Infrastructure (Step Functions, Lambda orchestration)
# Note: Will be updated after SkillsStack to wire skills into workflow
orchestration_stack_placeholder = None

# Stack 3: Memory Infrastructure (DynamoDB tables, KMS encryption)
memory_stack = MemoryStack(
    app,
    f"LateosMemory{environment.capitalize()}Stack",
    env=env,
    description=(
        "Lateos memory infrastructure: DynamoDB tables with KMS encryption "
        "and per-user partitioning"
    ),
)

# Stack 4: Cost Protection Infrastructure (Budgets, kill switch, alarms)
cost_protection_stack = CostProtectionStack(
    app,
    f"LateosCostProtection{environment.capitalize()}Stack",
    core_stack=core_stack,
    env=env,
    description=(
        "Lateos cost protection infrastructure: AWS Budgets, kill switch "
        "Lambda, CloudWatch alarms"
    ),
)

# Stack 5: Skills Infrastructure (Email, Calendar, Web Fetch, File Ops)
skills_stack = SkillsStack(
    app,
    f"LateosSkills{environment.capitalize()}Stack",
    environment=environment,
    audit_table=memory_stack.audit_log_table,
    env=env,
    description=("Lateos skills infrastructure: Skill Lambda functions with scoped IAM roles"),
)
skills_stack.add_dependency(memory_stack)

# Stack 2 (Deferred): Orchestration with Skills Integration
orchestration_stack = OrchestrationStack(
    app,
    f"LateosOrchestration{environment.capitalize()}Stack",
    core_stack=core_stack,
    skills_stack=skills_stack,
    env=env,
    description=(
        "Lateos orchestration infrastructure: Step Functions Express "
        "Workflows, Lambda orchestration"
    ),
)
orchestration_stack.add_dependency(skills_stack)

# Add required tags to all resources
cdk.Tags.of(app).add("Project", "Lateos")
cdk.Tags.of(app).add("ManagedBy", "CDK")
cdk.Tags.of(app).add("Environment", environment)
cdk.Tags.of(app).add("Repository", "github.com/Leochong/lateos")

# Add any additional tags from cdk.json
for key, value in resource_tags.items():
    cdk.Tags.of(app).add(key, value)

app.synth()
