# Approaches Evaluated and Rejected

This document catalogs architectural approaches we evaluated during Lateos design and deliberately rejected, along with the reasoning. This proves comprehensive architectural evaluation rather than accepting the first suggestion.

Every decision here was weighed against Lateos's core design principle: **security-by-design**, informed by the 512 OpenClaw CVEs that demonstrated how persistent processes, poor isolation, and unconstrained permissions create exponential attack surfaces.

---

## Rejected: ECS/Fargate Instead of Lambda

**Reason:** Persistent containers = persistent attack surface. OpenClaw runs on persistent processes. That is the core problem.

**Evaluation notes:**

ECS/Fargate would provide familiar container orchestration and persistent state management. On the surface, appealing for teams experienced with Docker. However:

- Containers (even serverless ones) maintain a listening process between requests
- Persistent process memory can leak credentials from previous requests
- Container escape vulnerabilities affect an always-running target
- Admin panels or misconfigured health checks remain open between requests
- Container image vulnerabilities (CVE in dependencies) compromise the persistent process

Lambda enforces a hard security boundary: the function dies after each request. No persistent state, no listening ports, no attack surface between invocations.

**Security implications:**

OpenClaw's documented CVE-2026-25253 exploited RCE in a persistent bot process. Lateos eliminates the attack surface entirely by refusing persistent processes. Fargate removes this guarantee.

**Would reconsider if:**

- AWS introduces Lambda execution isolation at the hypervisor level with lower cold start cost (unlikely)
- Threat model changes to include long-running user sessions (e.g., browser-based agent) — even then, would use Lambda for API layer + Session Manager for user control

---

## Rejected: API Keys Instead of Cognito JWT

**Reason:** Static API keys cannot be revoked per-session. One compromised key = permanent account compromise until manual rotation.

**Evaluation notes:**

API keys are simpler to issue and manage initially. Some early design sketches used simple bearer tokens stored in Secrets Manager. However:

- Static keys cannot be revoked per-request (only per-rotation cycle)
- No session lifecycle — a stolen key works forever until next scheduled rotation
- No audit trail of which session was used for which action (JWT includes session_id and iat timestamp)
- No easy per-user MFA enforcement
- Impossible to implement step-up authentication for sensitive actions

Cognito JWT provides:

- Session-scoped tokens with explicit expiration (MFA re-auth forces new session)
- Per-request audit trail (session_id tied to IAM principal)
- Revocation via Cognito session termination (immediate, not waiting for rotation)
- MFA enforcement per-account
- Built-in token refresh mechanism

**Security implications:**

OpenClaw's CVE log shows multiple instances of leaked static API keys in public Git repos and Slack messages. With a static key, the compromise is permanent. Cognito sessions are revocable within seconds.

**Would reconsider if:**

- Lateos needed to support non-human clients (legacy integrations requiring API keys) — would use separate Cognito client ID with API key (asymmetric auth)
- Session-less operation became a requirement (very unlikely for a personal agent)

---

## Rejected: Single Lambda Monolith vs. Separate Skill Lambdas

**Reason:** One IAM role = OpenClaw's threat model. Skill isolation requires separate execution contexts.

**Evaluation notes:**

A monolith with one Lambda function and one IAM role is simpler to reason about (one entry point, one permission set). We briefly considered this for Phase 0 to accelerate initial development. However:

- Email skill compromise would automatically grant calendar skill access (same IAM role)
- Calendar skill compromise could exfiltrate email OAuth tokens
- One wildcard permission anywhere affects all skills
- Cost monitoring per-skill impossible (only account-level budget)
- Concurrency limits affect all skills equally (email spam blocks calendar)
- Deployment coupling: fixing one skill requires redeploying entire monolith

Separate Lambdas with isolated IAM roles provide:

- Email skill IAM role ONLY accesses `lateos/{env}/gmail/{user_id}` secrets
- Calendar skill CANNOT read email credentials (different role)
- Compromised web fetch skill has zero AWS permissions (HTTP client only)
- Per-skill cost attribution and concurrency limits
- Independent deployment and scaling
- Lateral movement requires compromise of multiple execution contexts

**Security implications:**

This directly implements RULE 2 (scoped IAM) and ADR-016 (Skill Isolation Model). OpenClaw's architecture treats all skills as equal — one RCE compromises the entire agent. Lateos enforces least privilege through separate execution contexts.

**Would reconsider if:**

- Shared state between skills became required (unlikely for personal agent use case)
- Cold start latency became the primary constraint (could batch related skills)

---

## Rejected: Community Skill Registry/Marketplace

**Reason:** ClawHub had 20% malicious packages. We control what executes. No community plugins.

**Evaluation notes:**

A community-driven skill marketplace (like OpenAI's plugin store) would accelerate feature development and allow third-party innovation. We evaluated this briefly because open ecosystems are powerful. However:

- ClawHub (OpenClaw's official registry) suffered 512 CVEs partly from malicious/negligent community contributions
- 20% of community skills in ClawHub were intentionally malicious (vendetta attacks)
- No effective review process can scale to thousands of community submissions
- A malicious skill runs with full agent permissions (in designs without skill isolation)
- Supply chain trust is impossible to establish without centralized control

Lateos enforces a closed skill deployment model:

- All skills are curated, signed, and deployed by project maintainers
- SAST scanning and security review required before skill goes live
- No third-party code execution in production
- Users can fork Lateos and add skills (open source), but cannot add runtime plugins

Users retain agency through open-source: anyone can review the code, fork, and extend with their own skills in their own deployment.

**Security implications:**

OpenClaw's attack surface explosion came partly from ecosystem compromise. Lateos eliminates ecosystem attack vectors by refusing arbitrary community code. This trades extensibility for auditability.

**Would reconsider if:**

- Lateos reaches adoption scale where ecosystem lock-in becomes limiting
- Skill signing and containment mechanisms mature enough to audit community code
- Mandatory transparency reports from community developers become standard practice

---

## Rejected: DynamoDB Global Tables (Multi-Region)

**Reason:** Cross-region replication increases attack surface. Single-region for MVP; re-evaluate post security audit.

**Evaluation notes:**

Global Tables provide low-latency read access and automatic failover across regions. Early designs considered this for resilience. However:

- Cross-region replication increases data exposure surface (data in transit between regions)
- Replication lag means eventual consistency in security-critical tables (audit logs, session state)
- Global Tables require KMS key sharing across regions (violates RULE 3 intent)
- Failure domains are now multi-region (outage in one region can trigger cascading issues)
- Audit trail fragmentation (separate CloudTrail per region)
- Additional operational complexity without clear threat model justification

Single-region (us-east-1) provides:

- All data stays in one region — clear data residency
- Immediate consistency in security-critical writes
- Simplified audit trail (one region's CloudTrail)
- Easier to recover from regional outages (can rebuild from backups/snapshots)

For a Phase 0-1 MVP serving individual users, multi-region failover is not required. Cost and complexity are not justified.

**Security implications:**

Multi-region increases attack surface without clear security benefit for a personal agent. Single region simplifies auditability and trust boundaries.

**Would reconsider if:**

- Lateos scales to enterprise multi-tenant SaaS (data residency would require regional replication)
- AWS region outages start affecting user availability (currently acceptable downtime)
- Users explicitly request geographic data residency (GDPR, data sovereignty)

---

## Rejected: WebSocket API for Real-Time Messaging

**Reason:** Persistent connections = persistent attack surface. HTTP polling with CloudFront caching sufficient for MVP.

**Evaluation notes:**

WebSocket API provides true bidirectional communication and real-time updates (e.g., agent streaming responses mid-generation). Appealing for UX, especially for browser-based clients. However:

- WebSocket connections are persistent (attack surface between messages)
- WebSocket state in API Gateway must be managed (session storage complicates recovery)
- Connection hijacking possible if JWT validation skipped once
- Streaming responses increase memory footprint (buffering data for delivery to connection)
- Difficult to audit message sequence (no stateless request/response)

HTTP polling (Lambda → API Gateway → HTTP) provides:

- Each request is stateless and self-contained
- Authentication verified for every single request
- Easier to add request signing and HMAC validation
- Simpler to implement in resource-constrained clients
- CloudFront can cache responses (API Gateway cannot with WebSocket)
- Trivial to audit request sequence in CloudTrail

**Tradeoff:** Users see slightly higher latency (polling interval) rather than true real-time. For agent responses (typically 2-30 seconds), 2-second polling introduces negligible delay.

**Security implications:**

WebSockets introduce persistent connection state that must be managed and secured. Stateless HTTP polling eliminates this attack surface. OWASP and NIST both recommend stateless APIs for security-critical systems.

**Would reconsider if:**

- User experience studies show polling latency is unacceptable (current evidence says otherwise)
- Bedrock Streaming API becomes cost-prohibitive compared to full-request responses
- Browser-based real-time collaboration features require true bidirectional comms

---

## Rejected: Browser Automation Skill (Puppeteer/Playwright)

**Reason:** Full computer control is OpenClaw's root attack surface. Human-in-the-loop approval gate planned (Phase 7).

**Evaluation notes:**

Browser automation (Puppeteer, Playwright, Selenium) would enable powerful skills: automated form filling, web scraping, screenshot capture. Early designs considered this for "web interaction" skill. However:

- Browser automation is Turing-complete — can do anything a human can do on the internet
- RCE in browser automation script becomes full internet access
- Cannot feasibly audit what a malicious prompt will make Puppeteer do
- JavaScript execution environment is deeply integrated with OS
- Headless browsers still require network isolation (can reach internal networks)

OpenClaw's core vulnerability: unrestricted automation of any task. One RCE = access to everything the agent can see or do on the internet.

Lateos enforces explicit function boundaries:

- Email skill: send emails, no more
- Calendar skill: read/write events, no more
- Web fetch skill: HTTP GET only, no JavaScript execution
- Mandatory HITL (human-in-the-loop) approval for any new capability

**Security implications:**

Browser automation violates the principle of least privilege. The attack surface is equivalent to giving an attacker full shell access. This is ADR-017 (HITL Browser Control) — we explicitly rejected autonomous browser control.

**Would reconsider if:**

- Bedrock Agentic API matures with sandbox isolation (AWS provides sandboxed execution environment)
- Human-in-the-loop approval gate is implemented (Phase 7) with mandatory user confirmation
- Formal verification of browser automation scripts becomes practical

---

## Rejected: Model Fine-Tuning (Custom Claude Model)

**Reason:** Operational burden, cost, and security risk outweigh benefits. General Claude 3 model sufficient for Phase 0-3.

**Evaluation notes:**

Fine-tuning Claude on Lateos-specific examples would improve intent classification accuracy and reduce hallucination. We evaluated this for Phase 2. However:

- Fine-tuning requires continuous data pipeline (collect examples, label, retrain)
- Fine-tuned model remains proprietary to Lateos deployment (cannot share improvements with community)
- Cost: $4 per million input tokens, $20 per million output tokens (fine-tuning)
- Operational risk: fine-tuned model becomes a single point of failure
- Regulatory risk: fine-tuned model trained on user data could raise GDPR questions

Phase 1-2 mitigation: use rule-based intent classification (deterministic, testable, zero cost) instead of fine-tuned model. Provides certainty and auditability.

**Tradeoff:** Less natural language flexibility in early phases, but explainable behavior and zero hidden cost. Phase 3 adds soft intent classification via Claude prompt evaluation (still not fine-tuned).

**Security implications:**

Fine-tuned models introduce operational complexity and maintenance burden. Rule-based classification is more auditable and deterministic — security reviewers can verify exactly what intents are recognized.

**Would reconsider if:**

- Lateos reaches Phase 5+ and user study shows rule-based classification is insufficient
- Anthropic releases fine-tuned model management tools with audit trail
- Fine-tuning becomes cost-competitive with prompt engineering

---

## Rejected: Kubernetes/EKS Deployment

**Reason:** Kubernetes is designed for long-running services. Lateos is event-driven (per-request). Lambda + CDK is the right tool.

**Evaluation notes:**

Kubernetes is a powerful orchestration platform. Some early architecture sketches used EKS to deploy containerized Lateos agents. However:

- Kubernetes assumes long-running workloads (pods persist between requests)
- Kubernetes requires persistent authentication (API server tokens, kubeconfig)
- Kubernetes API rate limiting and RBAC are less mature than IAM
- Operational burden: cluster management, node patching, ingress configuration
- Cost: EC2 instance fleet vs. Lambda pay-per-millisecond
- Cold start: deploying pod takes 30-60 seconds vs. Lambda 50-100ms

Lambda + AWS CDK provide the right abstraction:

- Event-driven execution (Lambda scales to zero when not in use)
- IAM integration (every function has scoped execution role)
- Built-in observability (CloudWatch, X-Ray, CloudTrail)
- No cluster to manage (AWS manages runtime)
- Cost scales with actual usage (not idle EC2 instances)

**Tradeoff:** Kubernetes provides more control and visibility. Lambda hides implementation details. For a small team and MVP, abstraction is a feature, not a limitation.

**Security implications:**

Kubernetes cluster management introduces new attack surface: API server authentication, etcd encryption, network policies. Lambda eliminates cluster-level security management entirely. NIST prefers serverless for security-sensitive systems (less attack surface to manage).

**Would reconsider if:**

- Lateos becomes multi-tenant SaaS (Kubernetes provides workload isolation across customers)
- Lateos needs persistent state that survives beyond single request (Kubernetes StatefulSets)
- Cost analysis shows Lambda becomes more expensive than EKS at scale (unlikely for this workload type)

---

## Rejected: PostgreSQL RDS vs. DynamoDB

**Reason:** DynamoDB enforces data isolation by design (partition key = user_id). RDS requires careful SQL to prevent cross-user access.

**Evaluation notes:**

PostgreSQL RDS is familiar to many developers and provides ACID transactions, complex queries, and relational data modeling. Early designs considered RDS for audit logs and session state. However:

- SQL by default is open (SELECT * can read anything without explicit filtering)
- Cross-user queries require careful WHERE clauses (easy to miss one)
- RULE 6 (no cross-user data access) is enforced by application logic, not database
- RDS requires network isolation (VPC, security groups) and SSL
- RDS provisioned capacity planning (similar scaling complexity to DynamoDB provisioned)
- RDS backups require encryption and access controls

DynamoDB enforces data isolation by design:

- Partition key = user_id is mandatory on every query
- DynamoDB SDK syntax makes it harder to accidentally scan all users
- KMS encryption at rest, TLS in transit (enforced by SDK)
- On-demand scaling without capacity planning
- Point-in-time recovery automatically encrypted

**Tradeoff:** DynamoDB cannot run complex JOINs. Lateos doesn't need them. Most queries are single-partition scans (all user's events, all user's secrets).

**Security implications:**

DynamoDB makes RULE 6 violations harder to introduce. RDS makes them require explicit attention. For security-sensitive applications, harder is better. Defense in depth: database structure enforces isolation, application logic validates isolation.

**Would reconsider if:**

- Audit log queries require complex JOINs across users (unlikely — each user's audit log is independent)
- Compliance requirements mandate SQL-based audit trails (possible for enterprise)
- DynamoDB query performance becomes prohibitive (would add RDS as read-only replica, not primary store)

---

## Rejected: EventBridge vs. Step Functions

**Reason:** Step Functions provides synchronous orchestration with explicit state machines. EventBridge is asynchronous event routing (different use case).

**Evaluation notes:**

AWS EventBridge is designed for loosely-coupled, event-driven architectures. Some designs proposed EventBridge for Lateos orchestration (publish "user_message" event → route to classifier → route to action handler). However:

- EventBridge is asynchronous by design (caller doesn't wait for handler completion)
- Lateos requires synchronous orchestration (user expects response before connection closes)
- EventBridge routing is declarative (rules), not explicit state machine
- Error handling in EventBridge is fire-and-forget with DLQ (not suitable for user-facing requests)
- EventBridge requires separate infrastructure for replay and recovery

Step Functions Express Workflows provide:

- Synchronous orchestration (caller blocks until workflow completes)
- Explicit state machine definition (easy to audit execution path)
- Built-in error handling and retry logic
- CloudWatch integration for every execution
- Deterministic ordering (critical for multi-step requests)

**Tradeoff:** Step Functions Express is more tightly-coupled. EventBridge is more decoupled. Lateos is a single-user agent, not a distributed microservices system — decoupling is unnecessary.

**Security implications:**

Step Functions' synchronous model makes request lifecycle auditable and deterministic. EventBridge's asynchronous model makes audit trails harder to reconstruct (events fire-and-forget). For security auditing, explicit > implicit.

**Would reconsider if:**

- Lateos becomes multi-tenant platform (EventBridge for isolation between users)
- Asynchronous processing becomes acceptable (user polls for results instead of waiting)
- Lateos adds background jobs (skill execution scheduled outside of user request) — would add EventBridge in addition to Step Functions

---

## Rejected: Direct Anthropic API vs. Bedrock

**Reason:** Direct API sends data outside AWS security boundary. Bedrock keeps all data within VPC.

**Evaluation notes:**

Anthropic's direct API (api.anthropic.com) would provide direct access to latest Claude models without Bedrock's limitations. Early designs considered this for maximum flexibility and feature access. However:

- Direct API requires HTTPS egress from Lambda → api.anthropic.com (data leaves AWS security boundary)
- Cannot use AWS PrivateLink to keep data within VPC
- API key stored in Secrets Manager (another service to authenticate with)
- API rate limits and authentication separate from IAM
- Data does not remain in AWS region (unknown routing)
- No AWS audit trail of API calls (only Anthropic has logs)

Amazon Bedrock provides:

- API calls stay within AWS VPC (PrivateLink available)
- IAM-based authentication (no separate API key management)
- CloudTrail logs every Bedrock API call (AWS accountability)
- Regional data residency (data never leaves specified region)
- Data processing agreement with AWS

**Tradeoff:** Bedrock model availability lags Anthropic releases by weeks. Bedrock pricing is slightly higher ($0.003 per 1K input vs. Anthropic's $0.003).

**Security implications:**

RULE 1 includes data residency: keeping user data within AWS security boundary. Direct API violates this. Bedrock aligns with zero-trust architecture: never trust external services when AWS provides integrated alternative.

**Would reconsider if:**

- Bedrock stops supporting Claude models (very unlikely)
- AWS Bedrock Guardrails become insufficient (would switch to output validation layer, not change LLM provider)
- Lateos needs access to bleeding-edge Claude features unavailable in Bedrock (acceptable tradeoff)

---

## Rejected: Custom LLM (LLaMA, Mistral) vs. Claude

**Reason:** Custom LLMs require infrastructure, continuous fine-tuning, and lose security advantages of managed providers.

**Evaluation notes:**

Open-source LLMs (LLaMA 2, Mistral 7B) would eliminate Anthropic/AWS dependency and provide maximum control. We evaluated this for long-term independence. However:

- Self-hosted LLM requires GPU infrastructure (SageMaker or EC2)
- GPU instances are expensive at scale and add operational complexity
- No safety guarantees — custom LLM may hallucinate, confabulate, or refuse inappropriate requests inconsistently
- Prompt injection protection must be custom-built (Claude has built-in guardrails)
- Model updates require retraining and re-evaluation (continuous operational burden)
- Security patches must be applied manually

Claude via Bedrock provides:

- Safety guardrails built-in by Anthropic (fine-tuned for harm prevention)
- Regular model updates with zero operational burden
- Prompt injection resistance through training
- Consistent behavior across deployments
- AWS takes security responsibility (shared responsibility model)

**Tradeoff:** Dependency on Anthropic and AWS. No ability to fully customize model behavior without fine-tuning.

**Security implications:**

Claude is designed by Anthropic's safety team with constitutional AI principles. Custom LLMs have zero safety engineering. For security-sensitive agent (personal data, account access), this is not a tradeoff — managed models win.

**Would reconsider if:**

- Anthropic discontinues Bedrock support (would migrate to direct API, not custom LLM)
- Open-source models mature to production safety levels (5+ years away)
- Cost of Claude becomes prohibitive (current cost is negligible vs. infrastructure)

---

## Rejected: Node.js Runtime vs. Python

**Reason:** Python has stronger security/ML community, type hints for safety, and better AWS SDK support.

**Evaluation notes:**

Node.js is faster at cold starts (30-50ms vs Python's 50-100ms) and has large contributor base. Some design sketches used Node.js for Lambda runtime selection. However:

- Python type hints (dataclasses, Pydantic) catch errors at static analysis time
- Python security auditing tools more mature (bandit, semgrep)
- Python security community larger (most AWS security research uses Python)
- Python async/await is cleaner than Node.js callbacks (modern Node.js is better, but legacy npm modules still callback-heavy)
- boto3 (AWS SDK for Python) is more feature-complete than AWS SDK for JavaScript

Node.js advantages:

- Faster cold starts (100ms vs 50-100ms difference is negligible for 5-30 second requests)
- Larger npm ecosystem (but requires careful vetting — more supply chain risk)

**Tradeoff:** Slightly slower cold starts. Smaller dependency ecosystem (but more security scrutiny of what we do use).

**Security implications:**

Node.js npm ecosystem has higher supply chain risk (11M packages, many unmaintained). Python has fewer packages but higher bar for inclusion (PyPI, setuptools). For security-sensitive code, smaller vetted ecosystem is preferable. Type hints allow static analysis tools to catch errors before runtime.

**Would reconsider if:**

- Lateos team has deep Node.js expertise and weak Python skills (team composition is opposite)
- Cold start latency becomes critical constraint (user studies show current latency is acceptable)
- Node.js security tooling matures to match Python (unlikely in next 5 years)

---

## Rejected: GraphQL API vs. REST

**Reason:** REST is simpler to audit, secure, and cache. GraphQL complexity not justified for single-endpoint agent API.

**Evaluation notes:**

GraphQL provides flexible query language, nested resource fetching, and schema introspection. Some designs proposed GraphQL as "modern" alternative to REST. However:

- GraphQL requires deeper security hardening (query depth limits, resolver timeout management)
- GraphQL resolvers introduce new attack surface (each resolver is a potential injection point)
- GraphQL schema introspection can leak information about backend structure
- GraphQL caching is more complex (HTTP caching doesn't work transparently)
- Query complexity analysis required to prevent DoS (another operational burden)

Lateos API is minimal and single-endpoint (POST /agent):

- Request: { user_id, message, context }
- Response: { status, response, metadata }
- REST naturally models this as a single endpoint with standardized HTTP semantics
- CloudFront caching works transparently
- CloudTrail auditing shows exact request/response (not opaque GraphQL query)

**Tradeoff:** REST cannot do nested resource queries. Lateos doesn't need them (single endpoint is intentional design choice).

**Security implications:**

GraphQL attack surface is larger (query depth, resolver complexity, introspection). REST attack surface is smaller (HTTP semantics, standard caching, straightforward logging). NIST recommends REST for security-sensitive APIs (REST is simpler to reason about).

**Would reconsider if:**

- Lateos becomes multi-endpoint API (unlikely — intentionally single POST endpoint)
- Mobile clients require fine-grained resource control (would use REST filtering parameters, not GraphQL)
- Complex nested queries become necessary (would add REST endpoints, not GraphQL)

---

## Rejected Approaches Summary

Every rejection above shares a common thread: **security through simplicity**. Lateos deliberately chose simpler architectures, even when more powerful alternatives existed, because:

1. **Simpler is more auditable** — Three-line Python script is easier to review than 500-line Node.js callback chain
2. **Simpler is more resilient** — Lambda function with explicit role survives RCE attempts better than monolith with wildcard permissions
3. **Simpler is more testable** — Stateless REST API is easier to test than stateful WebSocket with eventual consistency
4. **Simpler is more observable** — Event-driven Lambda with CloudTrail logs provides better audit trail than EventBridge fire-and-forget
5. **Simpler is more compliant** — DynamoDB partition keys by user_id enforce RULE 6 automatically; SQL queries require explicit WHERE clauses

This is not a limitation of Phase 0 thinking. This is a deliberate architectural principle: **prefer operational simplicity over feature completeness**. When in doubt, choose the approach that leaves the smallest attack surface.

---

*Last updated: 2026-03-01*
*For new rejected approaches, add them to this file with the same structure.*
