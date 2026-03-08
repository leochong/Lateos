# Lateos

**Security-By-Design AI Personal Agent Platform**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![AWS CDK](https://img.shields.io/badge/AWS-CDK-orange.svg)](https://aws.amazon.com/cdk/)
[![Security: Bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)

---

## 📋 Table of Contents

- [What is Lateos?](#what-is-lateos)
- [Why Lateos Exists](#why-lateos-exists)
- [Quick Start](#quick-start)
- [Architecture Overview](#architecture-overview)
- [Security Rules](#security-rules)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

---

## What is Lateos?

Lateos is an **open-source AI personal agent** built on AWS serverless architecture with **security as the foundational design principle**. Unlike traditional AI agents that bolt on security as an afterthought, Lateos eliminates entire classes of vulnerabilities through architectural choices.

**Key Features:**

- 🔒 **Serverless-first**: No listening processes = no remote code execution surface
- 🛡️ **8 Immutable Security Rules** enforced by CI/CD
- 🔍 **Prompt injection detection** with 21 patterns and 43 test cases
- 🔐 **Scoped IAM roles**: One role per skill Lambda, no wildcards
- 💰 **Cost protection**: Reserved concurrency + kill switch prevents runaway bills
- 📖 **Open source**: MIT licensed, full transparency

**Official Website:** [lateos.ai](https://lateos.ai)

**Repository:** [github.com/leochong/Lateos](https://github.com/leochong/Lateos)

---

## Why Lateos Exists

In **January 2026**, the **OpenClaw security crisis** (also known as Clawdbot/Moltbot) exposed systemic failures in AI agent security:

- **1,247 API keys** leaked from exposed admin panels
- **$50,000+ in fraud** from stolen Anthropic credentials
- **892 instances** with command injection vulnerabilities
- **Remote code execution** via unsanitized WebSocket inputs
- **Supply chain attacks** via unsigned community skills

**Lateos was created to prove AI agents can be secure from day one.**

Every OpenClaw/Moltbot CVE is **architecturally eliminated** in Lateos:

| OpenClaw Vulnerability | Root Cause | Lateos Prevention |
|------------------------|------------|-------------------|
| **CVE-2026-25253 (RCE)** | WebSocket server with no sanitization | No WebSocket server (API Gateway only) |
| **CVE-2026-24763 (Container escape)** | Privileged Docker containers | Serverless Lambda (Firecracker microVMs) |
| **CVE-2026-25593 (Command injection)** | Shell execution in skills | RULE 4: No shell execution (banned) |
| **CVE-2026-25475 (Token theft)** | Plaintext secrets in env vars | RULE 1: Secrets Manager only |
| **ClawHavoc (Supply chain)** | Unsigned community skills | No skill marketplace (CDK-deployed only) |
| **ClawJacked (Auth bypass)** | Localhost trust | API Gateway + Cognito (no localhost) |

**Full CVE analysis:** [docs/CVE-CHECKLIST.md](docs/CVE-CHECKLIST.md)

---

## Quick Start

### Prerequisites

- **Python 3.12** (required for Lambda runtime and CDK)
- **AWS CDK v2** (`npm install -g aws-cdk`)
- **Docker** (for LocalStack testing)
- **AWS Account** (for deployment - not required for local development)

### Local Development Setup

```bash
# Clone the repository
git clone https://github.com/leochong/Lateos.git
cd Lateos

# Create Python 3.12 virtual environment
python3.12 -m venv .venv312
source .venv312/bin/activate

# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Install pre-commit hooks (enforces security rules)
pre-commit install
pre-commit install --hook-type commit-msg

# Verify setup
cdk synth          # Should synthesize all 5 stacks
pytest tests/ -v   # Run test suite (59 tests pass, 12 skipped, 7 errors when LocalStack not running)
```

### Deploy to LocalStack (Recommended First Step)

```bash
# Start LocalStack
docker-compose up -d

# Bootstrap and deploy all stacks to LocalStack
cdklocal bootstrap
cdklocal deploy --all

# Verify deployment
aws --endpoint-url=http://localhost:4566 dynamodb list-tables
aws --endpoint-url=http://localhost:4566 lambda list-functions
```

### Deploy to AWS

> ⚠️ **WARNING:** Review [LAUNCH-CHECKLIST.md](LAUNCH-CHECKLIST.md) before deploying to production.

```bash
# Configure AWS credentials
aws configure --profile lateos-prod

# Run account baseline security check
python scripts/verify_account_baseline.py --profile lateos-prod

# Deploy all stacks
cdk deploy --all --profile lateos-prod --require-approval never

# Verify deployment
aws stepfunctions list-state-machines --profile lateos-prod
```

**Deployment guide:** [docs/deployment-guide.md](docs/deployment-guide.md)

---

## Architecture Overview

Lateos uses **AWS Step Functions Express Workflows** to orchestrate a pipeline of Lambda functions, each with scoped IAM roles and reserved concurrency.

```
┌─────────────────────────────────────┐
│           User Request              │
│      (Cognito JWT Required)         │
└──────────────────┬──────────────────┘
                   │
┌──────────────────▼──────────────────┐
│       API Gateway (REST API)        │
│  - Cognito Authorizer (MFA enforced)│
│  - Throttling: 100 req/s burst      │
│  - Request validation: max 4KB body │
└──────────────────┬──────────────────┘
                   │
┌──────────────────▼──────────────────┐
│  Step Functions Express Workflow    │
│       (5-minute timeout)            │
└──────────────────┬──────────────────┘
                   │
         ┌─────────▼─────────┐
         │  VALIDATOR Lambda │
         │  - 21 inj patterns│
         │  - Threat score≥2 │
         │    = block        │
         │  - Concurrency: 10│
         └─────────┬─────────┘
                   │ [sanitized_message]
         ┌─────────▼─────────┐
         │ ORCHESTRATOR      │
         │  - Extract user_id│
         │  - Audit log      │
         │  - Concurrency: 10│
         └─────────┬─────────┘
                   │ [user_context]
         ┌─────────▼─────────┐
         │ INTENT CLASSIFIER │
         │  - Rule-based     │
         │  - Future: Bedrock│
         │  - Concurrency: 10│
         └─────────┬─────────┘
                   │ [intent]
         ┌─────────▼─────────┐
         │  ACTION ROUTER    │
         │  - Routes skills  │
         │  - Built-in: help │
         │  - Concurrency: 10│
         └─────────┬─────────┘
                   │
         ┌─────────▼─────────┐
         │   Choice State    │
         │  (Skill Routing)  │
         └──┬──┬──┬──┬───────┘
            │  │  │  │
          EMAIL CAL WEB FILE
          SKILL SKL FET OPS
            │  │  │  │
          Gmail GCal HTTP S3
          OAuth API  req  per-user
                          isolation
            └──┴──┴──┴───────┐
                   │ [skill_result]
         ┌─────────▼─────────┐
         │ OUTPUT SANITIZER  │
         │  - RULE 8: Redact │
         │  - Bedrock Guards │
         │  - Concurrency: 10│
         └─────────┬─────────┘
                   │ [sanitized_response]
┌──────────────────▼──────────────────┐
│       User Response (200 OK)        │
└─────────────────────────────────────┘

Supporting Infrastructure:
  DynamoDB Tables (KMS encrypted):
    - conversations      (user_id partition)
    - agent_memory       (user_id partition)
    - audit_logs         (user_id partition)
    - user_preferences   (user_id partition)

  Cost Protection:
    - AWS Budgets: $10/month threshold
    - Kill switch Lambda (disables API Gateway)
    - CloudWatch alarms + SNS alerts

  Secrets Manager:
    - lateos/{env}/gmail/{user_id}
    - lateos/{env}/google_calendar/{user_id}
    - (per-user OAuth tokens, automatic rotation)
```

**Detailed architecture:** [docs/architecture.md](docs/architecture.md)

---

## Security Rules

Lateos enforces **8 Immutable Security Rules** via pre-commit hooks and CI/CD:

```
RULE 1: No secrets in code, environment variables, or config files.
        ALL secrets go through AWS Secrets Manager. No exceptions.

RULE 2: No wildcard (*) actions or resources in any IAM policy.
        Every Lambda has a scoped execution role. Period.

RULE 3: No public S3 buckets, no public endpoints without Cognito.
        (WAF deferred to Phase 2 per ADR-011)

RULE 4: No shell execution in any Lambda or skill.
        os.system(), subprocess, eval(), exec() are banned.

RULE 5: All user input is sanitized for prompt injection before
        touching the LLM. Never pass raw user input to Bedrock.

RULE 6: No cross-user data access. Every DynamoDB query is scoped
        to the authenticated user_id partition key. No exceptions.

RULE 7: Every Lambda has reserved_concurrent_executions set.
        No function can scale to infinity and run up costs.

RULE 8: No plaintext logging of tokens, passwords, API keys, or PII.
        Use structured logging with field redaction.
```

**Enforcement:**

- **Pre-commit hooks**: `detect-secrets`, `gitleaks`, `bandit` (security linter)
- **CI/CD pipeline**: Fails on any security rule violation
- **Tests**: 43 prompt injection test cases, 73-test security regression suite

**Full threat model:** [docs/threat-model.md](docs/threat-model.md)

---

## Documentation

### Security

- **[SECURITY.md](SECURITY.md)** — Vulnerability reporting policy, security features
- **[PENTEST-GUIDE.md](PENTEST-GUIDE.md)** — Penetration testing guide
- **[docs/CVE-CHECKLIST.md](docs/CVE-CHECKLIST.md)** — OpenClaw CVE mapping
- **[docs/threat-model.md](docs/threat-model.md)** — Threat analysis and mitigations

### Development

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — Security-first contribution guidelines
- **[docs/architecture.md](docs/architecture.md)** — Detailed system architecture
- **[docs/deployment-guide.md](docs/deployment-guide.md)** — AWS deployment steps
- **[DECISIONS.md](DECISIONS.md)** — Architectural Decision Records (ADRs 001-016)

### Operations

- **[LAUNCH-CHECKLIST.md](LAUNCH-CHECKLIST.md)** — Pre-launch verification checklist
- **[STATUS.md](STATUS.md)** — Current build status and phase progress

---

## Contributing

We welcome contributions! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting PRs.

**Security researchers:** See [PENTEST-GUIDE.md](PENTEST-GUIDE.md) for testing guidelines.

**Reporting security vulnerabilities:** See [SECURITY.md](SECURITY.md) — do NOT open public issues.

---

## License

[MIT License](LICENSE)

---

## Contact

- **General questions:** [GitHub Discussions](https://github.com/leochong/Lateos/discussions)
- **Bugs:** [GitHub Issues](https://github.com/leochong/Lateos/issues)
- **Security:** [security@lateos.ai](mailto:security@lateos.ai) (see [SECURITY.md](SECURITY.md))
- **Project lead:** Leo Chong (CISSP, AWS Cloud Practitioner, CCNA Security, NREMT)
- **Email:** [leo@lateos.ai](mailto:leo@lateos.ai)

---

*Built with assistance from Claude AI by Anthropic.*

*Lateos proves AI agents can be secure by design. Every line of code prioritizes security over convenience.*
