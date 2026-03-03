# Lateos Architectural Decision Records (ADRs)

This document logs all significant architectural and design decisions made during the development of Lateos, maintaining a historical record of why choices were made and what tradeoffs were accepted.

**Format:** Each ADR follows the template at the end of this file.

---

## ADR-001: Use Bedrock Instead of Direct Anthropic/OpenAI API

**Date:** 2026-02-26
**Status:** Accepted
**Context:** Need LLM capabilities while maintaining security boundary
**Decision:** Use Amazon Bedrock with Claude 3 models
**Reasoning:**

- Keeps all data within AWS security perimeter
- No data leaves VPC boundary
- Unified IAM-based access control
- Regional data residency guarantees

**Tradeoffs:**

- Model selection limited to Bedrock-available models
- Slightly higher latency than direct API
- Model version updates controlled by AWS schedule

**Alternatives Considered:**

- Direct Anthropic API (rejected: data leaves AWS)
- OpenAI API (rejected: data leaves AWS, less secure)
- Self-hosted LLM (rejected: operational complexity, security patching burden)

---

## ADR-002: Express Workflows Over Standard Step Functions

**Date:** 2026-02-26
**Status:** Accepted
**Context:** Need orchestration for multi-step agent workflows
**Decision:** Use Step Functions Express Workflows
**Reasoning:**

- Lower cost for high-frequency, short-duration executions
- Up to 100,000 executions/second capacity
- 5-minute max execution time fits our use case
- Per-request billing aligns with usage pattern

**Tradeoffs:**

- No built-in execution history (must use CloudWatch)
- 5-minute max duration (not an issue for chat responses)
- No visual debugging in Console (history not retained)

**Alternatives Considered:**

- Standard Workflows (rejected: higher cost, unnecessary durability)
- Lambda-only orchestration (rejected: complex state management)
- SQS + Lambda chain (rejected: harder to visualize and debug)

---

## ADR-003: DynamoDB On-Demand Over Provisioned Capacity

**Date:** 2026-02-26
**Status:** Accepted
**Context:** Need scalable, low-latency storage for agent memory
**Decision:** Use DynamoDB with on-demand billing mode
**Reasoning:**

- Eliminates capacity planning complexity
- Auto-scales to handle unpredictable traffic spikes
- Pay only for actual requests
- No risk of throttling during viral growth

**Tradeoffs:**

- Slightly higher per-request cost at sustained high scale
- Cannot reserve capacity for cost savings

**Alternatives Considered:**

- Provisioned capacity (rejected: requires forecasting, throttling risk)
- Aurora Serverless (rejected: higher cost, unnecessary SQL features)
- S3 (rejected: not suitable for low-latency key-value access)

---

## ADR-004: MIT License

**Date:** 2026-02-26
**Status:** Accepted
**Context:** Open source licensing strategy
**Decision:** Release under MIT License
**Reasoning:**

- Maximum adoption, minimal friction for integrators
- Commercial use permitted without copyleft concerns
- Simple, well-understood license
- Aligns with AWS SDK licensing

**Tradeoffs:**

- Commercial users can fork without contributing back
- No patent protection clause (unlike Apache 2.0)

**Alternatives Considered:**

- Apache 2.0 (rejected: added complexity, patent clause unnecessary)
- GPL v3 (rejected: viral copyleft reduces adoption)
- AGPL (rejected: too restrictive for cloud services)

---

## ADR-005: Python for Lambda Runtime, Not Node.js

**Date:** 2026-02-26
**Status:** Accepted
**Context:** Choose runtime for Lambda functions
**Decision:** Python 3.12 for all Lambda functions
**Reasoning:**

- Broader contributor base in security/ML community
- Type hints provide safety without compilation step
- Rich ecosystem for AWS SDK (boto3), data processing
- Easier to read and audit for security
- Better async/await support than older Node.js

**Tradeoffs:**

- Slightly slower cold starts than Node.js (~50-100ms)
- Larger deployment package sizes
- GIL limitations (not relevant for our I/O-bound workloads)

**Alternatives Considered:**

- Node.js (rejected: smaller security community, callback hell)
- Go (rejected: higher barrier to entry for contributors)
- Rust (rejected: excessive complexity for business logic)

---

## ADR-006: AWS CDK Over SAM, Terraform, or CloudFormation

**Date:** 2026-02-26
**Status:** Accepted
**Context:** Infrastructure as Code framework selection
**Decision:** Use AWS CDK v2 with Python
**Reasoning:**

- Higher-level abstractions reduce boilerplate
- Type checking catches errors before deployment
- Reusable constructs for consistent patterns
- Native AWS service support, no lag for new features
- Python CDK aligns with Lambda runtime choice

**Tradeoffs:**

- Synthesized CloudFormation can be hard to debug
- Smaller community than Terraform
- Learning curve for CDK-specific patterns

**Alternatives Considered:**

- SAM (rejected: too limited, no advanced constructs)
- Terraform (rejected: different state management model, not AWS-native)
- Raw CloudFormation (rejected: too verbose, no type safety)

---

## ADR-007: LocalStack for Local Development Before Real AWS

**Date:** 2026-02-26
**Status:** Accepted
**Context:** Phase 0 — need to develop without AWS account costs
**Decision:** Use LocalStack for all local AWS service emulation
**Reasoning:**

- Zero AWS costs during initial development
- Faster iteration without real API latency
- No risk of accidentally deploying to production
- Works offline
- Community edition covers all core services needed

**Tradeoffs:**

- Not 100% API-compatible with real AWS (minor differences)
- Some advanced features require Pro edition
- Must still test against real AWS before production

**Alternatives Considered:**

- Moto for testing (kept for unit tests, but not full local stack)
- Real AWS with isolated account (rejected: unnecessary cost in Phase 0)
- SAM local only (rejected: doesn't cover DynamoDB, Secrets Manager, etc.)

---

## ADR-008: Reserved Concurrency on All Lambdas

**Date:** 2026-02-26
**Status:** Accepted
**Context:** Cost protection and blast radius control
**Decision:** Set `reserved_concurrent_executions` on every Lambda function
**Reasoning:**

- Prevents runaway cost from infinite loops or attacks
- Enforces blast radius limits per function
- Forces explicit scaling decisions
- Protects account-level Lambda concurrency quota

**Tradeoffs:**

- Must tune per-function limits (not automatic)
- Can cause throttling if set too low
- Requires monitoring to adjust over time

**Alternatives Considered:**

- No concurrency limits (rejected: Clawdbot-style runaway cost risk)
- Account-level budget only (rejected: too coarse-grained)
- Lambda-level cost alarms (kept, but not sufficient alone)

---

## ADR-009: No Shell Execution in Lambda Functions

**Date:** 2026-02-26
**Status:** Accepted
**Context:** Security Rule #4 — prevent command injection attacks
**Decision:** Ban `os.system()`, `subprocess`, `eval()`, `exec()` in all Lambdas
**Reasoning:**

- Eliminates entire class of command injection vulnerabilities
- Forces use of safer, purpose-built libraries
- Reduces attack surface significantly
- Makes security audits simpler

**Tradeoffs:**

- Cannot use shell-based tools directly
- Some integrations require wrapper libraries
- May increase code complexity for system operations

**Alternatives Considered:**

- Whitelist safe commands (rejected: still risky, easy to bypass)
- Sandboxed shell (rejected: complexity, still attack surface)
- Input sanitization only (rejected: insufficient, often bypassed)

---

## ADR-010: Multi-Agent Model Selection — Cost Optimization Strategy

**Date:** 2026-02-26
**Status:** Accepted
**Context:** Balance quality vs. cost for different agent tasks
**Decision:** Use cheapest model that achieves acceptable quality per task type

**Model Assignment:**

- Security audits, architecture → Opus (highest stakes)
- Complex CDK, IAM, business logic → Sonnet (balanced)
- Tests, docs, file ops, search → Haiku (cost-optimized)

**Reasoning:**

- Haiku 4.5 delivers ~90% of Sonnet quality at 3x cost savings
- Not all tasks require deep reasoning
- Security failures more expensive than Opus tokens
- OpusPlan pattern: Opus designs, Sonnet implements

**Tradeoffs:**

- Must maintain mapping of task → model
- Slight quality drop for non-critical tasks
- Increased coordination complexity

**Alternatives Considered:**

- Sonnet for everything (rejected: 3x higher cost)
- Haiku for everything (rejected: insufficient for security)
- Dynamic routing based on complexity (rejected: adds latency)

---

## ADR-011: Defer WAF to Phase 2 (Pre-Public Launch)

**Date:** 2026-02-27
**Status:** Accepted
**Context:** CoreStack design for Phase 1 local development with LocalStack
**Decision:** Skip WAF v2 implementation in Phase 1 CoreStack, defer until Phase 2 (pre-public launch)
**Reasoning:**

- WAF costs ~$8/month minimum (web ACL + rule charges)
- Unnecessary expense during local development phase
- API Gateway throttling provides adequate protection for private/local phase
- Cognito authentication is first line of defense
- No public exposure until Phase 2+ anyway

**Tradeoffs:**

- Must remember to add WAF before public GitHub release
- No rate limiting beyond API Gateway built-in throttling during Phase 1
- Slightly higher risk if accidentally deployed publicly

**Alternatives Considered:**

- Include WAF from day one (rejected: $8/month wasted during local dev)
- Use WAF only in production environment (kept: will add in Phase 2)
- Skip WAF entirely (rejected: required for public-facing production)

**Revisit:** Before public GitHub release (March 2026 target)

---

## Template for Future ADRs

Use this template when adding new decisions:

```markdown
## ADR-XXX: [Decision Title]

**Date:** YYYY-MM-DD
**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-XXX
**Context:** [What is the issue we're trying to solve?]
**Decision:** [What did we decide to do?]
**Reasoning:**
- [Why is this the best choice?]
- [What are the key benefits?]

**Tradeoffs:**
- [What are we giving up?]
- [What are the downsides?]

**Alternatives Considered:**
- [Option A] (rejected: reason)
- [Option B] (rejected: reason)
```

---

ADR-012: Domain Registration
Decision: Registered lateos.ai via Cloudflare Registrar
Date: 2026-02-27
Rationale: .ai TLD directly signals AI agent platform.
           Cloudflare provides at-cost pricing, free DNSSEC,
           free WHOIS privacy — aligns with security-by-design philosophy.
DNS: Parked — configure routing to AWS pre-public launch (Phase 5)
Revisit: Phase 5 launch prep
---

ADR-013: Python Runtime Pinned to 3.12
Decision: Use Python 3.12 for all CDK and Lambda development
Rationale: JSII/CDK incompatible with Python 3.14 (pre-release).
           Lambda runtime also maxes at 3.12. Consistency across
           local dev and production runtime.
Date: 2026-02-27

---

## ADR-014: Prompt Injection Threat Threshold

**Date:** 2026-02-28
**Status:** Accepted
**Context:** Need clear policy for when to block suspected prompt injection attacks vs. warn
**Decision:** Block requests when 2+ injection patterns detected; warn (log only) for single pattern
**Reasoning:**

- Single pattern may be false positive (legitimate use of words like "ignore", "system", etc.)
- Multiple patterns indicate deliberate attack attempt
- Threshold of 2 balances security with user experience
- Allows legitimate messages containing trigger words to pass

**Tradeoffs:**

- Sophisticated single-pattern attacks may slip through
- Users may hit false positives if message genuinely contains 2+ trigger phrases
- Threshold is somewhat arbitrary (could be 3 or 1)

**Alternatives Considered:**

- Block on single pattern (rejected: too many false positives, poor UX)
- Block on 3+ patterns (rejected: sophisticated attacks often use exactly 2)
- ML-based scoring (rejected: adds latency and complexity for Phase 1-3)
- Context-aware rules (deferred: future enhancement with LLM analysis)

**Security Implications:** Attackers may craft attacks with exactly 1 pattern to evade detection. Mitigations: (1) Bedrock Guardrails provides second layer, (2) Output sanitizer prevents exfiltration even if injection succeeds, (3) All blocked attempts logged to audit table.

---

## ADR-015: Bedrock Guardrails Placement (Output Layer, Not Input)

**Date:** 2026-02-28
**Status:** Accepted
**Context:** Where to apply Bedrock Guardrails in the request pipeline
**Decision:** Apply Guardrails to OUTPUT (post-skill execution) via output_sanitizer Lambda
**Reasoning:**

- Input validation already handled by validator Lambda (cheaper, faster)
- Guardrails ApplyGuardrail API costs $0.75 per 1,000 content units
- Applying to input would double cost (validate + sanitize)
- Output is where harmful content generation matters most
- Prevents accidental PII disclosure even if skill leaks data

**Tradeoffs:**

- Injection attacks that succeed will reach LLM before being caught
- Guardrails won't prevent malicious input, only malicious output
- Latency added at response time (user-visible)

**Alternatives Considered:**

- Apply Guardrails to input only (rejected: misses generated harmful content)
- Apply Guardrails to both input and output (rejected: 2x cost, redundant with validator)
- Use Guardrails for input, regex for output (rejected: inconsistent protection)
- No Guardrails at all (rejected: fails to catch LLM-generated harm)

**Security Implications:** Defense in depth: Input blocked by pattern matching (fast, cheap), Output blocked by Guardrails (ML-based, higher quality). Fail-open design: If Guardrails unavailable (LocalStack), allow output with warning. Cost: ~$0.001 per request vs. $0.002 if applied to both input/output (50% savings).

---

## ADR-016: Skill Isolation Model (One IAM Role Per Lambda, Not Shared)

**Date:** 2026-02-28
**Status:** Accepted
**Context:** How to enforce RULE 2 (scoped IAM) for skill Lambdas
**Decision:** Each skill Lambda has its own dedicated execution role with minimum required permissions
**Reasoning:**

- Email skill can ONLY access `lateos/{env}/gmail/{user_id}` secrets
- Calendar skill can ONLY access `lateos/{env}/google_calendar/{user_id}` secrets
- Web fetch skill has NO AWS permissions (HTTP client only)
- File ops skill can ONLY access S3 prefix `lateos/{env}/files/{user_id}/*`
- Prevents lateral movement: compromised email skill cannot steal calendar credentials

**Tradeoffs:**

- More IAM roles to manage (4 roles instead of 1 shared role)
- Slightly higher CDK complexity (must define each role separately)
- Cannot easily add cross-skill capabilities without role updates

**Alternatives Considered:**

- Shared skill execution role (rejected: violates RULE 2, enables lateral movement)
- Resource-based policies on secrets (rejected: harder to audit, inconsistent model)
- Assume-role from shared role (rejected: adds complexity, still requires per-skill roles)
- Dynamic policy injection (rejected: increases attack surface)

**Security Implications:** Blast radius containment: Email skill RCE cannot exfiltrate calendar data. Principle of least privilege: Each skill has exactly the permissions it needs. Audit clarity: CloudTrail shows exactly which skill accessed which resource. Meets CIS AWS Foundations Benchmark requirement for scoped IAM.

---
| 2026-02-28 | ADR-017: HITL Browser Control |
Autonomous browser rejected — full computer control
is OpenClaw's root attack surface. HITL approval gate
via Step Functions waitForTaskToken planned for Phase 7.
Community pentest of Phase 5 informs implementation. |

```

---

**And while you're in DECISIONS.md, also add:**
```

ADR-018: Need-Based Shell Restriction
ADR-019: Controlled Shell Execution model (Phase 8)

| 2026-02-28 | ADR-017: HITL Browser Control |
Autonomous browser control rejected — full computer
control is the root attack surface of OpenClaw
(CVE-2026-25253, ClawJacked). HITL approval gate via
Step Functions waitForTaskToken planned for Phase 7.
Community pentest of Phase 5 public release informs
implementation details. |

| 2026-02-28 | ADR-018: Need-Based Shell Restriction |
Shell execution excluded at launch — root cause of
every major OpenClaw RCE exploit. Will be enabled in
Phase 8 only when a validated skill task requires it,
under strict constraints: command whitelist, ephemeral
Lambda sandbox, HITL approval gate, no network access
during execution, scoped S3 I/O only, full audit trail. |

| 2026-02-28 | ADR-019: Living Validator Pattern Library |
validator.py pattern list is community-extensible via
PR. Every new pattern requires both a positive test
case (should block) AND a negative test case (should
not block legitimate input). Protects against evolving
threat actor techniques including multi-language
injection, encoding bypass, and payload fragmentation. |

ADR-019: Living validator pattern library
Decision: validator.py pattern list is community-extensible
          via PR with mandatory test case requirement
Rationale: Threat actors evolve faster than any single
           developer can track. Community-sourced patterns
           with mandatory test coverage creates a living
           defense layer.
Security gate: Every new pattern requires a positive test
               case (should block) AND a negative test case
               (should not block legitimate input)

*Keep this document updated as new decisions are made. All ADRs should be immutable once accepted — if a decision changes, create a new ADR and mark the old one as superseded.*
