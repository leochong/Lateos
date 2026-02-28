# Lateos — Claude Code Kickstart Prompt

Copy and paste this entire prompt into Claude Code to begin Phase 0.
Run from the root of the lateos/ repository after cloning.

---

## PROMPT START — COPY EVERYTHING BELOW THIS LINE

This project is named **Lateos** (from Latin *lateo* — "to lie hidden, to be concealed").

**IMPORTANT TIMELINE CONTEXT:**

- Current date: February 17, 2026
- Development: February 28 - March 1, 2026 (local repo only)
- Public launch: March 1, 2026 (GitHub public + LinkedIn Wave 1)
- Strategy: Stealth build, then launch with working Phase 0 complete

**GitHub:** <https://github.com/Leochong/lateos> (will be made public March 1)  
**Project Lead:** Leo Chong — CISSP, AWS Cloud Practitioner, CCNA Security, NREMT

You are starting Phase 0 of Lateos, a security-by-design AWS serverless
AI personal agent built in direct response to the Clawdbot/Moltbot security
crisis of January 2026.

Before writing a single line of code, read the following files in full:

- CLAUDE.md (root)
- infrastructure/CLAUDE.md
- lambdas/CLAUDE.md
- tests/CLAUDE.md
- .claude/security-patterns.md

These files are your source of truth. Every decision you make must be
consistent with them.

---

## Phase 0 Objectives

Build the project foundation. No Lambda handlers yet. No CDK stacks yet.
Only the scaffolding that makes everything else safe and consistent.

Complete ALL of the following. Do not skip any item.

---

### Task 1: .gitignore

Create a comprehensive .gitignore that covers:

- .env and all .env.* variants (but NOT .env.example)
- AWS credentials: .aws/credentials, .aws/config
- Private keys: *.pem,*.key, *.p12,*_rsa, *_ecdsa,*_ed25519
- Any file with "secret", "credential", or "token" in the filename
- cdk.out/, node_modules/, **pycache**/, .pytest_cache/, htmlcov/
- IDE files: .vscode/settings.json, .idea/
- CDK context: cdk.context.json (add cdk.context.json.example instead)

After creating it, verify: `git check-ignore .env` returns `.env`.

---

### Task 2: .env.example

Create .env.example with placeholder values ONLY.
This file documents every configuration variable the project needs.
Real values are NEVER stored here — they go in AWS Secrets Manager or cdk.json.

Include sections for:

- AWS configuration (region, account — not credentials)
- CDK context variables (environment, budget)
- Secrets Manager path prefixes (just the paths, not the values)
- Bedrock model configuration
- A clearly commented note at the top explaining this file's purpose

---

### Task 3: .pre-commit-config.yaml

Create pre-commit configuration with these hooks:

- detect-secrets (with .secrets.baseline)
- gitleaks
- detect-private-key (from pre-commit-hooks)
- check-yaml
- check-json
- end-of-file-fixer
- trailing-whitespace
- black (Python formatter)
- isort (import sorter)
- bandit (security linter, fail on HIGH severity)

After creating it:

1. Run: `pre-commit run --all-files`
2. If detect-secrets finds issues, create the baseline: `detect-secrets scan > .secrets.baseline`
3. Confirm all hooks pass cleanly

---

### Task 4: cdk.json

Create cdk.json with CDK app configuration and context values.
Include:

- app entry point pointing to infrastructure/app.py
- context values: environment (default: "dev"), monthly_budget_usd (default: 10),
  aws_region, log_retention_days (default: 90),
  bedrock_model_id

NO secrets in this file. NO account IDs hardcoded.
Context values are configuration, not credentials.

---

### Task 5: requirements.txt and requirements-dev.txt

requirements.txt (CDK and shared runtime dependencies):

- aws-cdk-lib>=2.170.0
- constructs>=10.0.0
- cdk-nag>=2.28.0
- aws-lambda-powertools>=3.0.0
- boto3>=1.35.0
- pydantic>=2.0.0

requirements-dev.txt (testing and tooling):

- pytest>=8.0.0
- pytest-cov>=5.0.0
- pytest-mock>=3.14.0
- moto[all]>=5.0.0
- responses>=0.25.0
- bandit>=1.8.0
- black>=24.0.0
- isort>=5.13.0
- flake8>=7.0.0
- mypy>=1.11.0
- pre-commit>=3.8.0
- detect-secrets>=1.4.0
- aws-cdk-lib>=2.170.0  (needed for CDK assertion tests)

Pin all versions with >=. Do not use exact pins (==) — allows security patches.

---

### Task 6: GitHub Actions CI Pipeline (.github/workflows/ci.yml)

Create a CI workflow that runs on every PR to main and develop.
It must include these jobs in order:

Job 1 — secret-scan (runs first, blocks everything if fails):

- Checkout with fetch-depth: 0 (full history)
- Run gitleaks
- Run detect-secrets scan and compare to baseline
- Run trufflehog on full git history

Job 2 — security-lint (runs after secret-scan):

- Setup Python 3.12
- Install bandit
- Run: bandit -r lambdas/ infrastructure/ -ll --exit-zero (warn only at this stage)
- Run: bandit -r lambdas/ infrastructure/ -lll (fail on HIGH severity)

Job 3 — cdk-security (runs after secret-scan):

- Setup Python 3.12
- Install requirements.txt
- Run: cdk synth
- Run cdk-nag checks (fail on CRITICAL or HIGH findings)

Job 4 — unit-tests (runs after security-lint and cdk-security):

- Setup Python 3.12
- Install requirements.txt and requirements-dev.txt
- Run: pytest tests/ --cov=lambdas --cov=infrastructure --cov-report=xml --cov-fail-under=80
- Upload coverage report as artifact

All jobs must pass before PR can merge.
Use GitHub Actions secrets for any AWS credentials (NEVER hardcode them).

---

### Task 7: SECURITY.md

Create SECURITY.md with:

1. Supported versions table
2. How to report a vulnerability (private GitHub issue, NOT public)
3. Response timeline (acknowledge within 48h, patch within 14 days for CRITICAL)
4. The "If a secret was accidentally committed" incident response steps
   (from .claude/security-patterns.md — the 5-step process)
5. The Clawdbot CVE table from root CLAUDE.md showing what Lateos prevents
6. Security contact information placeholder

---

### Task 8: README.md

Create a professional README.md with:

1. Project headline: "Lateos — The AI personal agent that enterprise
   security teams won't hate"

2. Brief paragraph explaining the Clawdbot/Moltbot problem it solves

3. Architecture overview (text-based diagram using ASCII, not an image)

4. Key security features bullet list (reference the 8 rules from CLAUDE.md)

5. Prerequisites section:
   - AWS account with baseline security services enabled
   - AWS CLI configured
   - Python 3.12+
   - Node.js 18+ (for CDK)
   - Docker (for Lambda bundling)

6. Quick start (placeholder for now — will be filled in Phase 5):

   ```
   git clone https://github.com/Leochong/lateos.git
   cd lateos
   pip install -r requirements.txt -r requirements-dev.txt
   pre-commit install
   # More steps coming in Phase 5
   ```

7. Credits section including:
   "Architecture and design developed with assistance from Claude AI by Anthropic.
   Full design conversation publicly available at: [LINK TO CONVERSATION]"
   And the lead developer's name and background

8. License badge (MIT) and contributing link

---

### Task 9: Verify Account Baseline Script (scripts/verify_account_baseline.py)

Create a Python script that checks the AWS account has required security
services enabled before allowing deployment.

It must check and report on:

- CloudTrail: enabled and logging to S3
- GuardDuty: detector exists and is enabled
- Security Hub: enabled
- IAM Access Analyzer: analyzer exists
- S3 Block Public Access: enabled at account level
- Root account: no active access keys
- Billing alerts: enabled

Output a clear PASS/FAIL report for each check.
Exit code 0 if all pass, exit code 1 if any fail.
This script will be called by the deploy workflow before cdk deploy runs.

---

### Task 10: Phase 0 Test — Smoke Tests (tests/infrastructure/**init**.py + test_phase0.py)

Create tests/infrastructure/test_phase0.py with these baseline checks:

- test_env_example_exists_and_has_no_real_values()
- test_dotenv_not_committed()
- test_gitignore_covers_secrets()
- test_requirements_files_exist()
- test_no_pinned_versions_with_security_vulnerabilities() — check that
  requirements use >= not hardcoded old versions
- test_precommit_config_exists()
- test_github_workflows_exist()
- test_security_md_exists()

Run them: `pytest tests/infrastructure/test_phase0.py -v`
All must pass before Phase 0 is considered complete.

---

## Completion Criteria for Phase 0

Before marking Phase 0 done, verify ALL of the following:

```bash
# 1. Pre-commit hooks pass on all files
pre-commit run --all-files

# 2. No secrets detected
detect-secrets scan --baseline .secrets.baseline
gitleaks detect --no-git

# 3. Phase 0 tests pass
pytest tests/infrastructure/test_phase0.py -v

# 4. CDK synthesizes (even with empty stacks placeholder)
cdk synth

# 5. CI workflow is valid YAML
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"

# 6. .env is gitignored
git check-ignore .env && echo "PASS: .env is ignored"

# 7. README exists and has credits section
grep -i "anthropic" README.md && echo "PASS: Credits found"
```

If any check fails, fix it before proceeding to Phase 1.

---

## What Phase 0 Does NOT Include

Do not build any of the following yet — they belong to later phases:

- Lambda handler code (Phase 1-2)
- CDK stacks with real resources (Phase 1)
- Skill implementations (Phase 2)
- Messaging integrations (Phase 4)
- Deployment to real AWS (Phase 5)

Phase 0 is purely scaffolding, tooling, and CI/CD pipeline.
The goal is that every future contribution is safe from day one.

---

## Final Note

This project is open source and the development conversation with Claude
is being made public so the community can learn from the design process.
Every decision made here — including this prompt — will be visible.

Build it as if a senior security engineer and a thousand open source
contributors are watching. Because eventually they will be.

## PROMPT END
