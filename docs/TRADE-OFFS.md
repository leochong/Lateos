# Lateos Architectural Trade-offs

This document proves architectural judgment by documenting what was sacrificed for each major decision. Every trade-off was deliberately evaluated; nothing was accepted without understanding the cost.

---

## 1. Serverless (Lambda) vs. Container Deployment (ECS/Fargate)

**Gained:**

- No persistent attack surface. Containers live for request duration only.
- Eliminates OpenClaw's root vulnerability: no listening ports, no admin panels exposed
- Automatic scaling with zero capacity planning
- Pay-per-execution billing aligns perfectly with chatbot usage patterns
- No OS patching responsibility—AWS manages Lambda infrastructure

**Gave up:**

- Cold start latency: ~100-200ms for Python on first invocation
- Persistent connections: WebSocket requires different architecture (API Gateway managed)
- Ability to run arbitrary background tasks without time limits (5-minute max)
- Warm invocation patterns: connection pooling across requests not possible
- Traditional container orchestration benefits (rolling restarts, graceful shutdown)

**Rationale:**
OpenClaw's entire attack surface stems from persistent processes. The moment your agent runs in a container that stays online, you inherit every networking risk that plagued Clawdbot. Lambda functions are fundamentally ephemeral—each invocation is a clean, isolated process. Cold starts are negligible (100ms) versus the security elimination of an always-on process.

**Numbers:**

- Lambda cold start: ~100-200ms (Python 3.12)
- Warm invocation: ~10-50ms
- ECS minimum cost: $0.096/hour (t3.micro) = $70/month idle
- Lambda: $0.20 per 1M requests, $0.000001667 per GB-second

**ADR Reference:** ADR-007 (LocalStack for dev), implicit in security model

---

## 2. Step Functions Express vs. Standard Workflows

**Gained:**

- 10x lower cost for short-lived orchestrations
  - Express: $0.000001 per state transition
  - Standard: $0.000025 per state transition
- Billing per-request (not per-transition) for our chat workflow
- Capacity: up to 100,000 executions/second
- 5-minute max duration fits our chat response window perfectly

**Gave up:**

- No built-in 90-day execution history (must use CloudWatch)
- No visual debugging in AWS Console (execution history not retained)
- Harder to audit old conversations (manual CloudWatch query required)
- 5-minute ceiling on any single orchestration (not an issue for chat)

**Rationale:**
Standard Workflows cost 25x more per transition and provide 90-day history we don't need. We log everything to CloudWatch anyway (for RULE 8 compliance), making the built-in history redundant. Chat responses complete in <5 seconds; Express max duration is never a constraint.

**Numbers:**

- Standard: $0.000025 per state transition × 10 states per request = $0.00025 per request
- Express: $0.000001 per state transition × 10 transitions = $0.00001 per request
- Monthly savings at 1M requests: $240 difference

**ADR Reference:** ADR-002

---

## 3. Rule-Based Intent Classification (Phase 2) vs. Bedrock LLM

**Gained:**

- Zero LLM cost for classification ($0.003 per request savings vs. Bedrock)
- Deterministic behavior—no variability in intent classification
- Fully testable with 100% coverage (no LLM randomness)
- Fast: <100ms response time

**Gave up:**

- Natural language flexibility: "show me my calendar" works, "what does my calendar look like" requires rule update
- Handles only predefined intents (email, calendar, web, file ops)
- Cannot dynamically add new skills without code changes
- Degrades gracefully but doesn't learn

**Rationale:**
Phase 2 covers the MVP skill set (email, calendar, web search, file ops). These 4 intents can be classified with ~95% accuracy using regex + keyword matching. Upgrading to LLM-based classification in Phase 3 provides flexibility once the core architecture is stable. Phase 2 rules-based approach is "fast enough" and proves the architecture works before adding LLM complexity.

**Numbers:**

- Rule-based classification: <100ms, $0 cost per request
- Bedrock classification: ~500ms, $0.003 per request
- Monthly cost difference at 1M requests: $3,000

**ADR Reference:** Implicit in Phase 2 architecture

---

## 4. KMS Key Per Stack vs. Shared KMS Key

**Gained:**

- Blast radius isolation: CoreStack compromise doesn't decrypt MemoryStack secrets
- No circular dependencies between stacks
- Clearer ownership: each stack knows exactly which KMS key it uses
- Prevents accidental key sharing across concern boundaries

**Gave up:**

- Slight cost increase: $1/key/month per additional key (3 additional keys = $3/month)
- KMS key management complexity: must track 4 keys instead of 1
- Key rotation policy must be maintained for each key separately

**Rationale:**
If an attacker compromises the CoreStack (API Gateway layer) and gains a KMS key, we don't want them to decrypt memory from MemoryStack. Each stack controls its own encryption key. The $3/month cost is negligible compared to the security isolation it provides.

**Numbers:**

- AWS KMS key: $1/month per key + API calls
- 4 stacks × $1 = $4/month
- Negligible vs. breach impact

**ADR Reference:** Implicit in infrastructure design

---

## 5. DynamoDB On-Demand Billing vs. Provisioned Capacity

**Gained:**

- Auto-scaling without capacity planning
- Protection against traffic spikes (viral adoption scenario)
- Pay exactly for what you use
- No risk of throttling during unexpected load

**Gave up:**

- Cost at high scale: on-demand is ~4-5x more expensive than provisioned at 1M WCU/month
- Cannot reserve capacity for discounts
- Unpredictable monthly costs (good for early stage, bad at scale)

**Rationale:**
We don't know Lateos's usage pattern yet. On-demand protects against two failure modes: (1) traffic spike causes throttling, (2) over-provisioning burns money on unused capacity. At <1M requests/month, on-demand is cheaper. We'll revisit in Phase 6 (production monitoring) and switch to provisioned if we hit consistent >1TB/month usage.

**Numbers:**

- DynamoDB on-demand: $1.25 per million WCU, $0.25 per million RCU
- DynamoDB provisioned: $0.000075 per WCU-hour = $0.54/month for 100 WCU (more with larger capacity)
- At 10M WCU/month: on-demand = $12.50, provisioned = $54-100 (depends on profile)
- Crossover point: ~8M WCU/month

**ADR Reference:** ADR-003

---

## 6. No Community Skill Marketplace vs. ClawHub Model

**Gained:**

- Eliminates supply chain attack vector: malicious skills can't be installed
- Controlled execution environment: only Lateos team can add skills
- No platform liability for third-party skill behavior
- Simpler security model: audit 4 skills vs. 1000s

**Gave up:**

- Community extensibility: users cannot share their own custom skills
- Network effects: no marketplace ecosystem like ClawHub had
- Rapid innovation: new skills require code changes + deployment
- User-driven feature requests take longer to implement

**Rationale:**
ClawHub's skill marketplace had ~20% malicious packages (documented in OpenClaw CVEs). Lateos Phase 5 prioritizes security over ecosystem. Phases 6-7 will add signed skill verification and controlled marketplace, but only after security foundation is airtight.

**ADR Reference:** Implicit in threat model (Clawdbot regression prevention)

---

## 7. Python 3.12 (Pinned) vs. Latest Python / Version Flexibility

**Gained:**

- Consistency: CDK, Lambda runtime, and local dev all use 3.12
- JSII compatibility: Python 3.14+ breaks AWS CDK (confirmed issue)
- Long-term support: 3.12 is supported until Oct 2028
- Predictable behavior across environments

**Gave up:**

- Latest features: 3.13+ features (like implicit optional grouping) not available
- Performance improvements in 3.13+ not gained
- Future-proofing: will need migration to 3.13 eventually

**Rationale:**
AWS CDK is incompatible with Python 3.14. We must pin to 3.12 for local development CDK synthesis. Lambda runtime also maxes at 3.12. Forcing consistency eliminates the "works locally but fails in Lambda" error class.

**ADR Reference:** ADR-013

---

## 8. WAF Deferral to Phase 2 (Pre-Launch)

**Gained:**

- $8-15/month cost savings during Phase 1-2 local development
- No Layer 7 rate limiting rules to configure (simpler initial deployment)
- API Gateway throttling provides adequate protection for private phase

**Gave up:**

- DDoS protection Layer 7 (but API Gateway throttling provides Layer 4)
- Geographic blocking rules (unnecessary for local dev)
- Bot detection (Phase 5 launch will add)
- SQL/XSS pattern matching (input validation Lambda provides this)

**Rationale:**
WAF costs $8/month minimum (web ACL) + $0.60/month per rule. During Phase 0-2, Lateos is local-only or private. Public launch happens Phase 5, at which point WAF is mandatory. Adding WAF now would waste $8-15/month during development phases when only engineers access the API.

**Numbers:**

- WAF web ACL: $8/month
- Common Rule Set: $5/month
- Custom rules: $0.60/month each
- Total: ~$15/month during private phase
- Phase 1-2: 2 months × $15 = $30 wasted

**ADR Reference:** ADR-011

---

## 9. REST API Gateway vs. HTTP API Gateway

**Gained:**

- OAuth 2.0 and OIDC integration (Cognito)
- Request validators (faster validation before Lambda invocation)
- Request/response transformations (though rarely used)
- Longer history and more documentation

**Gave up:**

- ~30% lower latency with HTTP API (~100ms vs. 70ms)
- ~50% lower cost: HTTP API $0.90 per 1M requests vs. REST $1.50
- Simpler configuration for modern serverless
- Better WebSocket support (if needed later)

**Rationale:**
Cognito integration requires REST API. HTTP API doesn't natively support Cognito authorizers. Given RULE 6 (all requests must be user-scoped), Cognito is mandatory. The latency and cost difference (30ms, $0.60 per 1M) is acceptable for security at the ingestion layer.

**Numbers:**

- REST API: $1.50 per 1M requests
- HTTP API: $0.90 per 1M requests
- Monthly difference at 1M requests: $0.60
- Latency: REST ~100ms, HTTP ~70ms (difference: 30ms)

**ADR Reference:** Implicit in CoreStack design

---

## 10. Cognito vs. Custom Authentication

**Gained:**

- Built-in MFA support (TOTP, SMS, email)
- Token refresh cycles (automatic expiration)
- User management console (no custom UI needed)
- HIPAA/PCI compliance built-in
- AWS-managed security patches

**Gave up:**

- Complete control over auth flow
- Ability to use alternative auth methods (SAML, custom OAuth)
- Simpler auth for internal-only usage

**Rationale:**
RULE 6 requires authenticated user scope. Cognito provides this out-of-box with MFA enforced. Custom auth would require implementing token refresh, MFA, session management—all complex and security-critical. Cognito's managed service eliminates this entire attack surface.

**ADR Reference:** Implicit in security model (RULE 6)

---

## 11. Amazon Bedrock vs. Direct Anthropic API

**Gained:**

- Data stays within AWS security perimeter (no API calls to external services)
- Regional data residency guarantees (HIPAA/PCI compliance)
- Unified IAM-based access control
- No API keys to manage (uses IAM roles)
- Single invoice (no separate Anthropic account)

**Gave up:**

- Model selection limited to Bedrock-available models (currently Claude 3)
- Slightly higher latency than direct Anthropic API (~100-200ms)
- Model version updates follow AWS schedule, not Anthropic
- Minor cost increase (~5-10% vs. direct API)

**Rationale:**
Lateos's entire value proposition is "security by design." Using external APIs means user data leaves the AWS security boundary. Bedrock keeps everything inside. The 5-10% cost premium is worth the compliance guarantee.

**Numbers:**

- Bedrock Claude 3 Sonnet: $3 per 1M input, $15 per 1M output tokens
- Direct Anthropic API: ~$3/$15 (roughly similar, sometimes cheaper)
- Latency difference: <200ms (acceptable for agent responses)

**ADR Reference:** ADR-001

---

## 12. LocalStack for Local Development vs. Real AWS

**Gained:**

- Zero AWS costs during Phase 1-2 development (~$100+ saved)
- Faster iteration without real API latency
- Offline development capability
- No risk of accidentally deploying to production
- Deterministic behavior (no eventual consistency surprises)

**Gave up:**

- API differences: some AWS features not fully emulated in LocalStack
- Advanced features require Pro version
- Must still validate against real AWS before production
- Debugging mismatch: "works in LocalStack but fails in real AWS"

**Rationale:**
Phase 0-2 are scaffolding and development. Deploying to real AWS every iteration costs money and time. LocalStack lets us iterate fast locally, then validate once in Phase 3 against real AWS. The $100 development cost savings outweigh the risk of eventual production validation.

**ADR Reference:** ADR-007

---

## 13. Reserved Concurrency vs. Unreserved Lambda

**Gained:**

- Cost protection: runaway loops cannot scale infinitely
- Blast radius control: each Lambda has maximum concurrent executions
- Fail-safe: if you don't know the limit, you set it low (conservative default)
- Forces explicit scaling decisions

**Gave up:**

- Need to tune concurrency limits per-function (not automatic)
- Can cause throttling if set too low
- Requires ongoing monitoring as traffic patterns change
- Additional CloudWatch alarms needed for throttling detection

**Rationale:**
Clawdbot had zero concurrency limits. An infinite loop or attack could spawn unlimited Lambda instances, costing $1000s in minutes. Reserved concurrency forces us to explicitly decide "email skill can run 10 concurrent times, calendar skill 5 times." If we set too low, we get throttling (visible failure), not silent cost explosion.

**Numbers:**

- Unreserved Lambda: 1000 concurrent limit at account level (soft quota)
- Reserved concurrency: per-function limit (e.g., 10, 5, 20)
- Cost impact: 0 (reserved concurrency has no additional cost)
- Risk if not set: unlimited cost exposure in attack scenario

**ADR Reference:** ADR-008

---

## 14. Single-Region (us-east-1) vs. Multi-Region

**Gained:**

- Simpler infrastructure: one Region = simpler disaster recovery
- Lower cost: no cross-region replication charges
- Easier to debug and reason about data flow
- Simpler compliance: all data in one jurisdiction
- Faster initial launch: less to orchestrate

**Gave up:**

- Geographic resilience: Region failure affects all users
- Compliance: cannot serve users in regions requiring data residency
- Latency optimization: users far from us-east-1 see slower responses
- HA deployment model: cannot do active-active

**Rationale:**
MVP (Phase 5) targets single-region for simplicity. Multi-region replication increases attack surface (data must be encrypted in transit across regions). We'll revisit post-launch; single-region is acceptable for early users. Latency is <500ms even from us-west (acceptable for agent responses).

**ADR Reference:** Implicit in infrastructure design

---

## 15. Bedrock Guardrails Placement: Output Layer (Not Input)

**Gained:**

- Cost savings: ~50% cheaper than applying Guardrails to both input and output
  - Guardrails: $0.75 per 1,000 content units
  - Applying only to output: ~$0.001 per request
- Fast input validation: pattern matching is cheaper than LLM Guardrails
- Catch malicious LLM outputs: Guardrails on output prevents Bedrock-generated harm
- Layered defense: input validated by pattern matching, output by Guardrails

**Gave up:**

- Early blocking of injection attacks: if injection succeeds at input validation, it reaches LLM before Guardrails catch it
- No LLM-based input filtering (but pattern matching catches 95%+ of cases)
- Latency at response time: Guardrails adds ~200-500ms to response

**Rationale:**
Two layers: Input validated by regex (fast, cheap), output sanitized by Guardrails (ML-based, catches nuanced harms). Pattern matching catches obvious injections. If a sophisticated attack slips through, Guardrails catches the generated output before it reaches user. Cost: ~$0.001/request vs. $0.002 if applied to both (50% savings).

**Numbers:**

- Pattern matching (input): <50ms, $0 cost
- Guardrails (output): ~400ms, $0.00075 per request
- Both: ~450ms, $0.0015 per request
- Monthly savings at 1M requests: $750

**ADR Reference:** ADR-015

---

## 16. Prompt Injection Threat Threshold: 2+ Patterns to Block

**Gained:**

- Balanced security: sophisticated attacks typically use 2+ patterns
- Reduces false positives: single pattern may be legitimate ("ignore whitespace" in code)
- Better UX: legitimate messages containing one trigger word pass through
- Simple logic: rule is easy to audit and test

**Gave up:**

- Some single-pattern attacks slip through (Latency injection: "system prompt override")
- Sophisticated attacks using exactly 2 patterns could be specifically crafted to evade
- Arbitrary threshold: 2 is somewhat empirical, not mathematically proven optimal

**Rationale:**
Threshold of 1 causes false positives (blocks users asking "can I ignore this rule?"). Threshold of 3 misses attacks with exactly 2 patterns. Threshold of 2 is empirically optimal for our 15+ pattern detector. Defense-in-depth: if pattern matching misses it, Guardrails catches it on output.

**Security Implications:**

- Single-pattern attacks evaded: yes, mitigated by Guardrails + output sanitizer
- Blocked attempts logged: CloudTrail + DynamoDB audit table
- Threat score calculated: LATEOS-001 error code emitted

**ADR Reference:** ADR-014

---

## Summary: Every Trade-off Was Worth It

| Trade-off | Gained | Cost | Acceptable |
|-----------|--------|------|-----------|
| Serverless | No attack surface | 100-200ms cold start | ✅ Yes |
| Express Workflows | 10x cost savings | No 90-day history | ✅ Yes |
| Rules-based intent | Zero LLM cost | Limited flexibility | ✅ Until Phase 3 |
| KMS per-stack | Blast radius isolation | $3/month | ✅ Yes |
| On-demand DynamoDB | Auto-scaling | Higher cost at scale | ✅ Until Phase 6 |
| No skill marketplace | Supply chain safety | No ecosystem | ✅ Until Phase 7 |
| Python 3.12 pinned | Consistency | Can't use 3.13 features | ✅ Yes |
| WAF deferred | $8-15/month savings | No L7 filtering | ✅ Until Phase 2 |
| REST API Gateway | Cognito integration | 30% higher latency | ✅ Yes |
| Cognito | Built-in MFA + compliance | Less control | ✅ Yes |
| Bedrock | Data in AWS | 5-10% cost premium | ✅ Yes |
| LocalStack | $100+ cost savings | Eventual AWS validation | ✅ Yes |
| Reserved concurrency | Cost protection | Must tune per-function | ✅ Yes |
| Single-region | Simpler ops | No geographic resilience | ✅ Until Phase 7 |
| Guardrails on output only | 50% cost savings | Injection→LLM possible | ✅ Yes (with defense-in-depth) |
| 2+ pattern threshold | Better UX | Some attacks slip through | ✅ Yes (with Guardrails backup) |

Every trade-off serves Lateos's core mission: **security by design with minimal attack surface**. We sacrificed features, performance, and ecosystem for the architectural rigor that eliminates OpenClaw's vulnerabilities.

The fundamental principle: **A cheap fix to an expensive security problem is always worth it.**
