# Lateos — Phase 5.5: Documentation & Architecture Pre-Launch Plan

**Phase:** 5.5 — Pre-Public Documentation Sprint
**Trigger:** Complete after Phase 4 (Security Hardening), before Phase 5 (Launch)
**Goal:** Ensure Lateos reads as an engineered security project, not vibe-coded

---

## 🎯 Why This Phase Exists

Lateos's entire value proposition is credibility — a CISSP-led,
security-by-design AWS serverless agent built in direct response to
512 documented OpenClaw CVEs. Poor documentation or a missing
architecture diagram destroys that credibility instantly.

Every file in this phase answers one question for the reader:
*"Can I trust this?"*

The secondary goal is combating vibe coding stigma. The most common
criticism of AI-assisted coding is: "When it breaks, the developer
can't fix it because they don't understand their own code."

Every deliverable in this phase is designed to prove the opposite.

---

## 📁 Deliverables

---

### SECTION A: ARCHITECTURE & DIAGRAMS

### A1. Architecture Diagram (Code-Generated)

**File:** `docs/diagrams/lateos-architecture.py`
**Output:** `docs/diagrams/lateos-architecture.png`
**Tool:** Python `diagrams` library (pip install diagrams)

**Why code-generated?**

- Always in sync with actual infrastructure
- Version-controlled alongside code
- Regenerates automatically in CI/CD
- Looks professional and deliberate

**Diagram must show:**

- Ingestion layer: API Gateway + Cognito
- Orchestration: Step Functions state machine
- Lambda pipeline: Validator → Orchestrator → Intent Classifier →
  Action Router → Skill Executor → Output Sanitizer
- Skill Lambdas: Email, Calendar, Web Fetch, File Ops (each isolated)
- Data layer: DynamoDB (KMS encrypted), Secrets Manager, S3
- Observability: CloudWatch, CloudTrail, X-Ray
- Cost protection: Budgets → Kill Switch Lambda → SNS

### A2. Threat Model Diagram

**File:** `docs/diagrams/lateos-threat-model.py`
**Output:** `docs/diagrams/lateos-threat-model.png`

**Must map Lateos controls to OpenClaw CVEs:**

| OpenClaw CVE | Attack Vector | Lateos Control |
|---|---|---|
| CVE-2026-25253 | Broken Access Control | IAM roles + Cognito |
| Supply chain | Malicious skill packages | Controlled Lambda execution |
| Exposed ports | Direct internet access | Serverless = no open ports |
| Plaintext secrets | API keys in config files | Secrets Manager + KMS |
| No audit trail | Undetectable compromise | CloudTrail + CloudWatch |

### A3. Data Flow Diagram

**File:** `docs/diagrams/lateos-data-flow.py`
**Output:** `docs/diagrams/lateos-data-flow.png`

Shows how user data moves through the system:

- Where it is encrypted
- Where it is validated
- Where it is redacted
- Where it is persisted
- Where it is deleted

This diagram is specifically for security-conscious users and
enterprise evaluators who want to know where their data goes.

---

### SECTION B: CORE DOCUMENTATION

### B1. README.md (Full Rewrite)

**File:** `README.md`

**Structure:**

```
# Lateos — Security-by-Design AI Personal Agent

> "Lambda functions don't listen. There are no open ports."

## The Problem (OpenClaw — 512 CVEs)
## The Lateos Approach
## Architecture Overview (embed diagram)
## Security Model (8 rules summary)
## Quick Start
## Local Development
## Test Coverage Badge (from CI)
## Project Lead
## License
```

**Tone:** Technical, confident, CISSP-level. No marketing fluff.
The README should read like it was written by someone who has
actually read the CVEs and designed around them.

**Must include:** Link to full walkthrough docs so readers can
verify they understand what they're deploying.

### B2. docs/ARCHITECTURE.md

**File:** `docs/ARCHITECTURE.md`

```
# Lateos Architecture

## Design Philosophy
## Stack Overview
## CoreStack: API Gateway + Cognito
## OrchestrationStack: Step Functions Pipeline
## MemoryStack: Data Isolation
## CostProtectionStack: Kill Switch
## Security Layers (map to RULE 1-8)
## Local Development Architecture (LocalStack)
## What We Deliberately Did NOT Build (and why)
## Future: WAF (Phase 2, deferred per ADR-011)
```

The "What We Deliberately Did NOT Build" section is as important
as what was built. It shows architectural judgement.

### B3. docs/SECURITY-MODEL.md

**File:** `docs/SECURITY-MODEL.md`

```
# Lateos Security Model

## RULE 1–8 Reference
## OpenClaw CVE Mapping
## Threat Model
## What Lateos Does NOT Protect Against (honest limitations)
## Responsible Disclosure (link to SECURITY.md)
## Pentest Scope (link to PENTEST-GUIDE.md)
```

The "What Lateos Does NOT Protect Against" section is critical.
It shows intellectual honesty and builds more trust than omitting it.

### B4. docs/ADR/ (Individual ADR Files)

**Directory:** `docs/ADR/`

Move all ADRs from DECISIONS.md into individual files:

```
docs/ADR/
├── ADR-001-zero-trust-serverless.md
├── ADR-002-step-functions-orchestration.md
├── ADR-003-kms-encryption.md
...
├── ADR-011-waf-deferral.md
├── ADR-012-domain-lateos-ai.md
├── ADR-013-python-312-pin.md
```

Each file uses standard ADR template:

- Status, Context, Decision, Consequences, **Alternatives Considered**

The "Alternatives Considered" field is critical — it proves you
evaluated options rather than just accepting the first suggestion.

### B5. docs/API.md

**File:** `docs/API.md`

OpenAPI/Swagger spec for the POST /agent endpoint.
Request schema, response schema, error codes, auth requirements.

### B6. CONTRIBUTING.md (Finalize)

**File:** `CONTRIBUTING.md`

- Security-first contribution guidelines
- How to submit a pentest finding
- ADR process for architectural changes
- Code review requirements
- No secrets policy

---

### SECTION C: WALKTHROUGHS (Anti-Vibe-Coding Core)

**Directory:** `docs/WALKTHROUGHS/`

These are the most important anti-vibe-coding deliverables.
A vibe coder cannot write these — you must understand the system
to trace a real request through it with line-level accuracy.

Each walkthrough traces a specific scenario end-to-end showing:

- Exact code path (Lambda → function → line reference)
- Data structure at each stage (what the JSON looks like)
- What CloudWatch logs emit at that moment
- What could go wrong at each step and why

### C1. 01-user-sends-message.md

Full request trace from user input to response:

```
User input → API Gateway → Cognito auth check →
Validator Lambda (injection scan) →
Orchestrator Lambda (context extraction) →
Step Functions state machine →
Intent Classifier → Action Router →
Skill Lambda → Output Sanitizer → Response
```

Show the actual JSON payload at each stage.

### C2. 02-prompt-injection-blocked.md

Trace a real injection attempt through the system:

```
Malicious input → Validator Lambda →
Pattern matching (which of the 15+ patterns triggered) →
Threat score calculation (2+ = block) →
LATEOS-001 error emitted →
CloudWatch log entry →
Request blocked, sanitized error returned to user
```

### C3. 03-cost-kill-switch-triggered.md

What happens when spend hits the $10 threshold:

```
CloudWatch billing alarm triggers →
SNS notification sent →
Kill Switch Lambda invoked →
API Gateway stage disabled →
Developer notified →
How to re-enable after review
```

### C4. 04-secret-redaction.md

How RULE 8 catches and redacts secrets in output:

```
Skill Lambda returns response containing API key →
Output Sanitizer scans for secret patterns →
Redaction applied ([REDACTED]) →
LATEOS-006 log entry emitted →
Clean response returned to user
```

### C5. 05-new-skill-execution.md

End-to-end trace of the email skill:

```
Intent classified as EMAIL_SEND →
Action Router invokes email skill Lambda →
IAM role scope verified (can only access SES, nothing else) →
Secrets Manager retrieves OAuth token →
Email sent → Audit log written to DynamoDB →
Output sanitized → Response returned
```

### C6. 06-local-development-debug.md

How to debug a failing Lambda locally without AI assistance:

```
How to reproduce the error in LocalStack →
How to read the structured JSON logs →
How to use the error code catalog →
Common failure patterns and fixes →
How to write a test that prevents regression
```

This walkthrough directly addresses the vibe coding criticism.
It proves the developer knows how to diagnose and fix problems
without reaching for AI assistance every time.

---

### SECTION D: OBSERVABILITY & ERROR CATALOG

### D1. docs/OBSERVABILITY.md

**File:** `docs/OBSERVABILITY.md`

```
# Lateos Observability Guide

## Log Architecture
## JSON Log Schema (every Lambda emits this format)
## Error Code Catalog (LATEOS-001 through LATEOS-XXX)
## CloudWatch Dashboard Setup
## CloudTrail Audit Trail
## X-Ray Tracing
## Runbooks for Common Failures
## Alerting Configuration
```

### D2. Error Code Catalog

**File:** `lambdas/shared/error_codes.py`

Every Lambda must emit structured JSON logs with a Lateos error code:

```
LATEOS-001 — Prompt injection detected (threat score threshold exceeded)
LATEOS-002 — Cognito token validation failed
LATEOS-003 — Step Functions execution timeout
LATEOS-004 — DynamoDB write throttled
LATEOS-005 — Cost kill switch triggered
LATEOS-006 — Secret redaction applied to output
LATEOS-007 — Skill Lambda IAM permission denied
LATEOS-008 — Bedrock Guardrails content policy blocked
LATEOS-009 — Secrets Manager retrieval failed
LATEOS-010 — Input validation failed (non-injection)
LATEOS-011 — Intent classification confidence below threshold
LATEOS-012 — Action router: no handler found for intent
LATEOS-013 — Output sanitizer: response exceeded length limit
LATEOS-014 — KMS decryption failed
LATEOS-015 — CloudTrail audit write failed
```

Each error code in the catalog must document:

- What triggered it
- What the system did in response
- How to investigate it
- How to fix the root cause

### D3. Structured Log Schema

Every Lambda must emit this JSON structure:

```json
{
  "timestamp": "ISO-8601",
  "request_id": "uuid",
  "user_id": "cognito-sub (hashed)",
  "lateos_code": "LATEOS-XXX",
  "level": "INFO|WARN|ERROR",
  "component": "validator|orchestrator|intent_classifier|...",
  "message": "human readable",
  "duration_ms": 42,
  "metadata": {}
}
```

---

### SECTION E: CODE QUALITY EVIDENCE

### E1. Test Coverage Report

**File:** `docs/COVERAGE.md`
**Generated by:** pytest-cov in CI

Publish the actual coverage report. Not just "tests pass" —
show the percentage, which lines are covered, which are not,
and why the uncovered lines are acceptable.

Minimum acceptable: 80% (enforced in CI already per Phase 0).

### E2. Complexity & Quality Metrics

**File:** `docs/CODE-QUALITY.md`

Run and publish results from:

- `radon cc` — cyclomatic complexity (all functions should be < 10)
- `radon mi` — maintainability index
- `bandit` — security linting (already in CI)
- `pylint` score

A vibe coder's code typically has high cyclomatic complexity
because AI generates deeply nested conditionals. Publishing
low complexity scores is a deliberate credibility signal.

### E3. Dependency Audit

**File:** `docs/DEPENDENCY-AUDIT.md`

Run `pip-audit` and publish results. Document:

- Every production dependency and why it's needed
- Known CVEs (if any) and mitigation
- Update policy

Most vibe-coded projects have no idea what's in their
dependency tree. Publishing this audit proves you do.

### E4. CHANGELOG.md

**File:** `CHANGELOG.md`
**Format:** Keep a Changelog (keepachangelog.com)

Document every phase as a release:

```
## [0.2.0] - 2026-02-27 — Phase 2: Agent Pipeline
## [0.1.0] - 2026-02-27 — Phase 1: Core Infrastructure
## [0.0.1] - 2026-02-27 — Phase 0: Local Environment
```

A real changelog proves iterative development with intentional
versioning — not a single dump of AI-generated code.

---

### SECTION F: COMPREHENSION PROOF

These documents cannot be authentically AI-generated.
They require genuine understanding of the system and the
decisions made while building it.

### F1. docs/TRADE-OFFS.md

**File:** `docs/TRADE-OFFS.md`

Documents every major architectural trade-off and what was
sacrificed. This is one of the most powerful anti-vibe-coding
documents — it proves architectural judgement.

```
# Lateos Architectural Trade-offs

## Serverless vs. Container
Gained: No persistent attack surface
Gave up: Cold start latency, persistent connections

## Step Functions Express vs. Standard
Gained: Cost (Express billed by duration not transitions)
Gave up: 90-day execution history retention

## Rule-based intent classification (Phase 2) vs. Bedrock
Gained: Zero AI cost, deterministic behavior, fully testable
Gave up: Natural language flexibility (addressed in Phase 3)

## KMS per-stack vs. shared KMS key
Gained: No circular dependencies, blast radius isolation
Gave up: Slight cost increase ($1/key/month)
```

### F2. docs/WHAT-WE-REJECTED.md

**File:** `docs/WHAT-WE-REJECTED.md`

Architectural approaches evaluated and deliberately rejected:

```
# Approaches Evaluated and Rejected

## Rejected: ECS/Fargate instead of Lambda
Reason: Persistent containers = persistent attack surface.
        OpenClaw runs on persistent processes. That's the problem.

## Rejected: API keys instead of Cognito JWT
Reason: Static API keys can't be revoked per-session.

## Rejected: Single Lambda monolith
Reason: One IAM role = OpenClaw's model.
        Skill isolation requires separate execution contexts.

## Rejected: Community skill registry
Reason: ClawHub had 20% malicious packages.
        We control what executes. No community plugins.

## Rejected: DynamoDB Global Tables
Reason: Cross-region replication increases attack surface.
        Single-region for MVP, re-evaluate post security audit.
```

### F3. docs/LESSONS-LEARNED.md

**File:** `docs/LESSONS-LEARNED.md`
**Author:** Leo Chong (written by hand — not AI generated)

Claude Code will create this file with headers only.
Leo writes the content in his own words.

This is the most human document in the project. It documents
real problems encountered during development and how they were
actually solved. It cannot be faked.

```
# Lessons Learned Building Lateos

## The Python 3.14 / JSII incompatibility
## The constructs/ directory naming conflict
## Why WAF was deferred
## What I'd do differently next time
```

---

## 🚀 Phase 5.5 Claude Code Kickstart Prompt

```
Read STATUS.md, DECISIONS.md, CLAUDE.md, and
PHASE-5.5-DOCS-PLAN.md first.

Current phase: Phase 5.5 — Pre-Launch Documentation Sprint
Environment: source .venv312/bin/activate
Mode: LOCAL DEVELOPMENT — no AWS deployment

Do NOT rush. Quality over speed.
This phase proves Lateos is engineered, not vibe-coded.

SECTION A — DIAGRAMS:
A1. pip install diagrams
    Create docs/diagrams/lateos-architecture.py
    Generate lateos-architecture.png
    Must exactly match actual CDK stacks

A2. Create docs/diagrams/lateos-threat-model.py
    Map every OpenClaw CVE to a specific Lateos control
    Generate lateos-threat-model.png

A3. Create docs/diagrams/lateos-data-flow.py
    Show where data is encrypted, validated, redacted, persisted
    Generate lateos-data-flow.png

SECTION B — CORE DOCS:
B1. Full rewrite of README.md
    Embed architecture diagram
    CISSP-level technical tone, no marketing language
    Link to WALKTHROUGHS/ directory

B2. Create docs/ARCHITECTURE.md
    Document every stack with ADR references
    Include "What We Deliberately Did NOT Build" section

B3. Create docs/SECURITY-MODEL.md
    All 8 rules, CVE mapping
    MUST include honest limitations section

B4. Convert all ADRs from DECISIONS.md to individual files
    in docs/ADR/ — add "Alternatives Considered" to each

B5. Create docs/API.md with OpenAPI spec for POST /agent

B6. Finalize CONTRIBUTING.md with security-first guidelines

SECTION C — WALKTHROUGHS:
Create docs/WALKTHROUGHS/ directory.
Write all 6 walkthrough files.
CRITICAL: Reference actual function names and line numbers.
Do NOT write generic descriptions.
Show real JSON payloads at each pipeline stage.

C1. 01-user-sends-message.md
C2. 02-prompt-injection-blocked.md
C3. 03-cost-kill-switch-triggered.md
C4. 04-secret-redaction.md
C5. 05-new-skill-execution.md
C6. 06-local-development-debug.md

SECTION D — OBSERVABILITY:
D1. Create lambdas/shared/error_codes.py
    Implement LATEOS-001 through LATEOS-015
    Each code: trigger, system response, investigation steps, fix
D2. Verify every Lambda imports and uses error_codes.py
D3. Verify every Lambda emits structured JSON logs
    matching schema in PHASE-5.5-DOCS-PLAN.md
D4. Create docs/OBSERVABILITY.md

SECTION E — CODE QUALITY:
E1. Run: pytest --cov=lambdas --cov-report=term-missing
    Create docs/COVERAGE.md with results
E2. pip install radon
    Run: radon cc lambdas/ -s
    Run: radon mi lambdas/
    Create docs/CODE-QUALITY.md with results
E3. pip install pip-audit
    Run: pip-audit
    Create docs/DEPENDENCY-AUDIT.md
E4. Create CHANGELOG.md covering Phase 0 through current

SECTION F — COMPREHENSION PROOF:
F1. Create docs/TRADE-OFFS.md
    Every major trade-off: what was gained, what was sacrificed

F2. Create docs/WHAT-WE-REJECTED.md
    Architectural approaches evaluated and rejected with rationale

F3. Create docs/LESSONS-LEARNED.md with headers ONLY:
    - The Python 3.14 / JSII incompatibility
    - The constructs/ directory naming conflict
    - Why WAF was deferred
    - What I'd do differently next time
    Leave all content blank. Leo writes this by hand.
    Do NOT generate content for this file.

FINAL CHECKS:
- Run cdk synth — must still pass
- Verify all 3 diagrams generate correctly
- Verify LATEOS-001 through LATEOS-015 all implemented
- Verify coverage report shows 80%+ minimum
- Update STATUS.md for Phase 5.5 completion
- git commit -m "docs: Phase 5.5 - pre-launch documentation sprint"
```

---

## ✅ Phase 5.5 Definition of Done

**Section A — Diagrams**

- [ ] Architecture diagram matches actual CDK stacks
- [ ] Threat model maps every OpenClaw CVE to a Lateos control
- [ ] Data flow diagram shows all encryption and redaction points

**Section B — Core Docs**

- [ ] README.md reads as written by a security engineer
- [ ] ARCHITECTURE.md has "What We Deliberately Did NOT Build"
- [ ] SECURITY-MODEL.md has honest limitations section
- [ ] All ADRs in docs/ADR/ with Alternatives Considered
- [ ] API.md in OpenAPI format
- [ ] CONTRIBUTING.md finalized

**Section C — Walkthroughs**

- [ ] All 6 walkthroughs reference actual function names and lines
- [ ] Real JSON payloads shown at each pipeline stage
- [ ] Debug walkthrough explains how to fix without AI assistance

**Section D — Observability**

- [ ] LATEOS-001 through LATEOS-015 in error_codes.py
- [ ] All Lambdas emit structured JSON logs
- [ ] OBSERVABILITY.md complete

**Section E — Code Quality**

- [ ] Coverage 80%+ minimum
- [ ] Complexity metrics published (functions < cyclomatic 10)
- [ ] Dependency audit clean
- [ ] CHANGELOG.md covers Phase 0 through current

**Section F — Comprehension Proof**

- [ ] TRADE-OFFS.md covers every major architectural decision
- [ ] WHAT-WE-REJECTED.md covers evaluated alternatives
- [ ] LESSONS-LEARNED.md exists with blank content for Leo

**Final**

- [ ] cdk synth passes after docs sprint
- [ ] All diagrams committed to repo
- [ ] STATUS.md updated

---

## 📊 Updated Phase Sequence

```
Phase 0   — Local Environment        ✅ COMPLETE
Phase 1   — Core Infrastructure      ✅ COMPLETE
Phase 2   — Agent Pipeline           ✅ COMPLETE
Phase 3   — Skill Lambdas            🔄 NEXT
Phase 4   — Security Hardening       ⬜
Phase 5.5 — Documentation Sprint     ⬜ PRE-LAUNCH
Phase 5   — Public Launch            ⬜ FINAL
```

---

*Created: 2026-02-27*
*Author: Leo Chong*
*Lateos: github.com/Leochong/lateos | lateos.ai*
