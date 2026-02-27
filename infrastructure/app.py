#!/usr/bin/env python3
"""
Lateos CDK App Entry Point

This is a placeholder for Phase 0. Actual CDK stacks will be added in Phase 1.
For now, this file allows `cdk synth` to run and validate the CDK configuration.
"""

import aws_cdk as cdk

# Phase 0: Placeholder app
# Phase 1+: Import and instantiate actual stacks

app = cdk.App()

# Get configuration from cdk.json context
environment = app.node.try_get_context("environment") or "dev"
aws_region = app.node.try_get_context("aws_region") or "us-east-1"

# Placeholder: No stacks yet
# In Phase 1, we'll add:
# - CoreStack (API Gateway, Cognito, WAF)
# - MemoryStack (DynamoDB, KMS)
# - OrchestrationStack (Step Functions, Lambdas)
# - SkillsStack (Skill Lambdas)
# - IntegrationsStack (Messaging integrations)
# - CostProtectionStack (Budgets, kill switch)

# Add required tags to all resources
cdk.Tags.of(app).add("Project", "Lateos")
cdk.Tags.of(app).add("ManagedBy", "CDK")
cdk.Tags.of(app).add("Environment", environment)
cdk.Tags.of(app).add("Repository", "github.com/Leochong/lateos")

app.synth()
