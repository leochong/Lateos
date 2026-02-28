# Lateos — Complete Project Tree

```
lateos/
│
├── CLAUDE.md                                    ← Root Claude Code context (already built)
├── README.md                                    ← Public-facing project intro
├── CONTRIBUTING.md                              ← Contributor guidelines
├── CODE_OF_CONDUCT.md                           ← Community standards
├── SECURITY.md                                  ← Vulnerability disclosure + incident response
├── CHANGELOG.md                                 ← Keep a Changelog format
├── LICENSE                                      ← MIT
│
├── .env.example                                 ← Template only, never real values
├── .gitignore                                   ← Covers .env, *.pem, .aws/, cdk.out/, etc.
├── .pre-commit-config.yaml                      ← detect-secrets + gitleaks hooks
├── cdk.json                                     ← CDK context (env, budget, region — no secrets)
├── requirements.txt                             ← CDK + shared Python deps
├── requirements-dev.txt                         ← pytest, moto, bandit, black, isort, mypy
│
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                               ← PR gate: tests + security + coverage
│   │   ├── security.yml                         ← Gitleaks + Trufflehog + detect-secrets
│   │   └── deploy.yml                           ← Deploy to AWS on merge to main
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   ├── feature_request.md
│   │   └── security_vulnerability.md            ← Private disclosure template
│   └── PULL_REQUEST_TEMPLATE.md
│
├── .claude/                                     ← Claude Code context and agents
│   ├── security-patterns.md                     ← Security quick reference (already built)
│   ├── agents/                                  ← Subagent definitions (all already built)
│   │   ├── orchestrator.md                      ← sonnet — coordinates pipeline
│   │   ├── explore-agent.md                     ← haiku — read-only codebase search
│   │   ├── iac-agent.md                         ← sonnet — CDK infrastructure
│   │   ├── lambda-agent.md                      ← sonnet — Lambda handlers
│   │   ├── tests-agent.md                       ← haiku — test writing
│   │   ├── security-audit-agent.md              ← opus  — final security gate
│   │   ├── docs-agent.md                        ← haiku — documentation
│   │   └── file-ops-agent.md                    ← haiku — scaffolding + formatting
│   └── commands/
│       └── README.md                            ← Custom slash command definitions (already built)
│
├── infrastructure/
│   ├── CLAUDE.md                                ← CDK context + AWS security patterns (already built)
│   ├── CLAUDE.agent.md                          ← IaC agent scoped role + handoff contract
│   ├── app.py                                   ← CDK app entry point, tags all resources
│   ├── requirements.txt                         ← aws-cdk-lib, cdk-nag, constructs
│   │
│   ├── stacks/
│   │   ├── __init__.py
│   │   ├── core_stack.py                        ← API Gateway, WAF v2, Cognito, CloudTrail
│   │   ├── orchestration_stack.py               ← Step Functions, validation Lambda, Bedrock
│   │   ├── skills_stack.py                      ← Skill registry, skill Lambdas, IAM roles
│   │   ├── memory_stack.py                      ← DynamoDB, KMS keys, audit log table
│   │   ├── integrations_stack.py                ← Telegram, Slack, WhatsApp webhooks
│   │   └── cost_protection_stack.py             ← Budgets, kill switch, CloudWatch alarms
│   │
│   └── constructs/
│       ├── __init__.py
│       ├── secure_lambda.py                     ← Reusable Lambda construct with all defaults
│       ├── secure_table.py                      ← Reusable DynamoDB construct with KMS + PITR
│       ├── permission_boundary.py               ← Shared permission boundary for all roles
│       └── cost_alarm.py                        ← Reusable CloudWatch alarm set per Lambda
│
├── lambdas/
│   ├── CLAUDE.md                                ← Lambda context + handler patterns (already built)
│   ├── CLAUDE.agent.md                          ← Lambda agent scoped role + handoff contract
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── input_validation.py                  ← Prompt injection detection pipeline
│   │   ├── intent_classifier.py                 ← Risk scoring, high-risk confirmation
│   │   ├── orchestration_handler.py             ← Step Functions entry Lambda
│   │   └── memory_handler.py                    ← DynamoDB read/write with user partition
│   │
│   ├── skills/
│   │   ├── __init__.py
│   │   ├── email/
│   │   │   ├── __init__.py
│   │   │   ├── email_skill.py
│   │   │   └── requirements.txt
│   │   ├── calendar/
│   │   │   ├── __init__.py
│   │   │   ├── calendar_skill.py
│   │   │   └── requirements.txt
│   │   ├── web_search/
│   │   │   ├── __init__.py
│   │   │   ├── web_search_skill.py
│   │   │   └── requirements.txt
│   │   └── reminders/
│   │       ├── __init__.py
│   │       ├── reminders_skill.py
│   │       └── requirements.txt
│   │
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── telegram/
│   │   │   ├── __init__.py
│   │   │   └── telegram_handler.py              ← Webhook signature validation + routing
│   │   ├── slack/
│   │   │   ├── __init__.py
│   │   │   └── slack_handler.py
│   │   └── whatsapp/
│   │       ├── __init__.py
│   │       └── whatsapp_handler.py
│   │
│   ├── cost_protection/
│   │   ├── __init__.py
│   │   ├── kill_switch.py                       ← Throttles API + Lambdas at 100% budget
│   │   ├── cost_monitor.py                      ← Hourly anomaly detection
│   │   └── resume_agent.py                      ← Explicit confirmation required to restart
│   │
│   └── shared/
│       ├── __init__.py
│       ├── sanitizer.py                         ← Input sanitization + injection detection
│       ├── bedrock_client.py                    ← Bedrock invocation with guardrails
│       ├── secrets.py                           ← Secrets Manager fetch with LRU cache
│       ├── errors.py                            ← LateosError hierarchy + @safe_handler
│       └── requirements.txt                     ← aws-lambda-powertools, boto3
│
├── tests/
│   ├── CLAUDE.md                                ← Testing context + standards (already built)
│   ├── CLAUDE.agent.md                          ← Tests agent scoped role + handoff contract
│   ├── conftest.py                              ← Shared fixtures: moto, lambda_context, etc.
│   │
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_input_validation.py             ← 20+ injection pattern parametrized tests
│   │   ├── test_intent_classifier.py            ← Risk scoring assertions
│   │   ├── test_memory_handler.py               ← DynamoDB moto tests
│   │   ├── test_audit_log.py                    ← Append-only audit assertions
│   │   ├── test_email_skill.py
│   │   ├── test_calendar_skill.py
│   │   ├── test_web_search_skill.py
│   │   ├── test_reminders_skill.py
│   │   ├── test_telegram_handler.py             ← Webhook signature validation tests
│   │   ├── test_slack_handler.py
│   │   ├── test_whatsapp_handler.py
│   │   ├── test_kill_switch.py                  ← Budget breach → throttle assertions
│   │   └── test_cost_monitor.py
│   │
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── test_core_stack.py                   ← Cognito MFA, WAF rules assertions
│   │   ├── test_iam_policies.py                 ← No wildcards, permission boundaries
│   │   ├── test_kms_config.py                   ← Rotation enabled assertions
│   │   ├── test_lambda_config.py                ← Timeouts, concurrency, DLQ, ARM64
│   │   ├── test_resource_tagging.py             ← Project=Lateos on all resources
│   │   └── test_removal_policies.py             ← RETAIN on all data resources
│   │
│   └── security/
│       ├── __init__.py
│       ├── test_clawdbot_regression.py          ← Explicit CVE regression tests (living doc)
│       ├── test_no_secrets_leaked.py            ← Scans all source files for secret patterns
│       ├── test_iam_least_privilege.py          ← No wildcards in any policy
│       ├── test_cross_user_isolation.py         ← Memory partition isolation
│       └── test_injection_patterns.py           ← Full injection pattern test suite
│
├── docs/
│   ├── architecture.md                          ← System diagram + component descriptions
│   ├── threat-model.md                          ← Attack vectors + mitigations
│   ├── cost-estimation.md                       ← Per-service breakdown, ~$3-8/month
│   ├── deployment-guide.md                      ← Prerequisites, one-command deploy
│   ├── skill-development-guide.md               ← How to build and publish a skill
│   └── adrs/
│       ├── ADR-001-bedrock-over-direct-api.md
│       ├── ADR-002-express-workflows.md
│       ├── ADR-003-dynamodb-on-demand.md
│       ├── ADR-004-mit-license.md
│       └── ADR-005-python-over-nodejs.md
│
└── scripts/
    ├── verify_account_baseline.py               ← Checks GuardDuty, CloudTrail, etc. before deploy
    ├── multi_agent_feature.sh                   ← Runs full agent pipeline for a feature
    ├── rotate_secrets.sh                        ← Manually triggers Secrets Manager rotation
    └── wipe_user_data.sh                        ← GDPR data deletion helper
```

---

## File Count Summary

| Directory | Files | Status |
|-----------|-------|--------|
| `.claude/agents/` | 8 | ✅ Built |
| `.claude/` | 2 | ✅ Built |
| `infrastructure/CLAUDE.md` | 1 | ✅ Built |
| `lambdas/CLAUDE.md` | 1 | ✅ Built |
| `tests/CLAUDE.md` | 1 | ✅ Built |
| `CLAUDE.md` (root) | 1 | ✅ Built |
| Everything else | ~65 | 🔲 To be built |

## What Phase 0 Needs Created First

```
lateos/
├── CLAUDE.md                    ✅ done
├── .env.example                 ← Phase 0
├── .gitignore                   ← Phase 0
├── .pre-commit-config.yaml      ← Phase 0
├── cdk.json                     ← Phase 0
├── requirements.txt             ← Phase 0
├── requirements-dev.txt         ← Phase 0
├── .github/workflows/ci.yml     ← Phase 0
├── .claude/ (all files)         ✅ done
├── infrastructure/CLAUDE.md     ✅ done
├── lambdas/CLAUDE.md            ✅ done
└── tests/CLAUDE.md              ✅ done
```
