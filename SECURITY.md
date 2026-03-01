# Security Policy

## 🔒 Security Commitment

Lateos is built with security as the foundational design principle. This
project was created in direct response to the Clawdbot/Moltbot security crisis
of January 2026, and security is not an afterthought—it's the architecture.

**Project Lead:** Leo Chong (CISSP, AWS Cloud Practitioner, CCNA Security, NREMT)

---

## 📋 Supported Versions

| Version | Supported          | Status                     |
| ------- | ------------------ | -------------------------- |
| main    | :white_check_mark: | Phase 5 (Launch Prep)      |
| develop | :white_check_mark: | Active development         |
| < 1.0   | :x:                | Not released               |

**Note:** Lateos is currently in Phase 5 (Launch Prep). Production releases
will follow semantic versioning with LTS support for major versions.

---

## 🚨 Reporting a Vulnerability

**CRITICAL: Do NOT open public GitHub issues for security vulnerabilities.**

### How to Report

1. **Private Security Advisory (Preferred)**
   - Go to: `https://github.com/Leochong/lateos/security/advisories/new`
   - Select "Report a vulnerability"
   - Provide detailed information using the template below

2. **Email (Alternative)**
   - Contact: `security@lateos.dev` (will be active post-launch)
   - Subject: `[SECURITY] Brief description`
   - Encrypt with GPG key (available in repository root)

### What to Include

```markdown
## Vulnerability Report Template

**Summary:**
Brief description of the vulnerability

**Severity:**
[CRITICAL | HIGH | MEDIUM | LOW]

**Component:**
[Infrastructure | Lambda | Integration | Other]

**Attack Vector:**
How can this be exploited?

**Impact:**
What is the potential damage?

**Proof of Concept:**
Steps to reproduce (code/screenshots if applicable)

**Suggested Fix:**
Your recommendation (if any)

**Discoverer:**
Your name/handle (for credit in security advisory)
```

---

## ⏱️ Response Timeline

| Severity     | Acknowledgment | Patch Release | Disclosure  |
| ------------ | -------------- | ------------- | ----------- |
| **CRITICAL** | < 24 hours     | < 7 days      | After patch |
| **HIGH**     | < 48 hours     | < 14 days     | After patch |
| **MEDIUM**   | < 5 days       | < 30 days     | After patch |
| **LOW**      | < 7 days       | Next release  | After patch |

**CRITICAL** = Remote code execution, secret exposure, authentication bypass,
data breach
**HIGH** = Privilege escalation, SQL injection, XSS, significant DoS
**MEDIUM** = Information disclosure, CSRF, limited DoS
**LOW** = Minor information leak, configuration issue

---

## 🔐 Security Features

### What Lateos Prevents (vs. Clawdbot/Moltbot Vulnerabilities)

<!-- markdownlint-disable MD013 -->

| CVE / Issue                     | Root Cause                       | Lateos Prevention                   | Status        |
| ------------------------------- | -------------------------------- | ----------------------------------- | ------------- |
| **Exposed Admin Panels**        | Always-on process, no auth       | No persistent processes—serverless  | ✅ Immune     |
| **Localhost Auto-Trust**        | Reverse proxy misconfiguration   | API Gateway + Cognito, no localhost | ✅ Immune     |
| **Plaintext Secrets in Files**  | Credentials in Markdown/JSON     | Secrets Manager only                | ✅ Immune     |
| **ClawHub Skill Poisoning**     | No skill signing/verification    | Signed skills, SAST scan required   | ✅ Immune     |
| **CVE-2026-25253 (RCE)**        | Command injection in gateway     | No shell execution, no subprocess   | ✅ Immune     |
| **Prompt Injection**            | No input sanitization            | Injection detection pipeline        | ✅ Protected  |
| **Delayed Multi-Turn Attacks**  | No memory guardrails             | Bedrock Guardrails + memory TTL     | ✅ Protected  |
| **Account Hijacking**           | No trademark protection          | GitHub org, verified publisher      | ✅ Protected  |

<!-- markdownlint-enable MD013 -->

**Test Coverage:** All vulnerabilities above have comprehensive coverage:

- Prompt injection: `tests/security/test_prompt_injection.py` (43 test cases)
- CVE mapping: `docs/CVE-CHECKLIST.md` (all OpenClaw CVEs documented)

---

## 🛡️ Security Architecture

### The 8 Immutable Security Rules

These rules are enforced by CI/CD and cannot be bypassed:

1. **No secrets in code/env vars** — Only AWS Secrets Manager
2. **No wildcard IAM policies** — Every resource explicitly scoped
3. **No public S3 buckets** — Private only, WAF + Cognito for endpoints
4. **No shell execution** — `os.system()`, `subprocess`, `eval()`, `exec()` banned
5. **Input sanitization required** — No raw user input to LLM
6. **Per-user data isolation** — DynamoDB partition key = `user_id`
7. **Lambda concurrency limits** — `reserved_concurrent_executions` on all functions
8. **No plaintext logging of PII** — Structured logging with field redaction

**Enforcement:**

- Pre-commit hooks: `detect-secrets`, `gitleaks`, `bandit`
- CI/CD pipeline: Secret scanning blocks all PRs
- CDK: `cdk-nag` enforces AWS best practices
- Tests: Security regression suite in `tests/security/`

---

## 🔥 Incident Response: If a Secret Was Committed

If you accidentally commit a secret to version control:

### 1. IMMEDIATELY Revoke the Secret (< 5 minutes)

```bash
# AWS Secrets Manager
aws secretsmanager delete-secret --secret-id lateos/env/secret-name --force-delete-without-recovery

# API Keys (wherever they're stored)
# Revoke via provider dashboard IMMEDIATELY
```

### 2. Rotate the Secret (< 10 minutes)

```bash
# Generate new secret
aws secretsmanager create-secret --name lateos/env/secret-name --secret-string "NEW_VALUE"

# Update applications to use new secret (automated via Secrets Manager rotation)
```

### 3. Remove from Git History (< 15 minutes)

```bash
# Using BFG Repo-Cleaner (fastest)
bfg --delete-files SECRET_FILE
bfg --replace-text passwords.txt

# Or git filter-repo (more precise)
git filter-repo --path-glob '**/secrets.*' --invert-paths

# Force push (coordination required)
git push origin --force --all
git push origin --force --tags
```

### 4. Notify Security Team (< 30 minutes)

- Internal notification via incident channel
- Assess: Was the secret exposed publicly? For how long?
- Check CloudTrail: Was it accessed during exposure?

### 5. Document and Learn (< 24 hours)

- Post-mortem: How did it bypass pre-commit hooks?
- Update `.secrets.baseline` if needed
- Add test case to prevent recurrence

---

## 🧪 Security Testing

### Automated Security Checks (CI/CD)

Every PR runs:

- **Gitleaks**: Secret detection in commits
- **detect-secrets**: Entropy-based secret detection
- **TruffleHog**: Verified secrets in git history
- **Bandit**: Python security linting (fails on HIGH severity)
- **cdk-nag**: Infrastructure security best practices
- **Safety**: Dependency vulnerability scanning

### Manual Security Testing

We welcome security researchers to test Lateos. Please:

1. **Read `PENTEST-GUIDE.md`** for scope and rules of engagement
2. **Test against your own deployment** (not shared infrastructure)
3. **Report findings via security advisory** (not public issues)
4. **Wait for acknowledgment** before public disclosure

### Bug Bounty Program

**Lateos does not currently offer a bug bounty program.**

We are an open-source project maintained on a volunteer/best-effort basis. We
cannot offer financial rewards for vulnerability reports. However, we deeply
appreciate responsible disclosures and will:

- Publicly credit researchers (with permission)
- Respond promptly and transparently
- Fix verified vulnerabilities as quickly as possible
- Consider your findings for future security enhancements

If you're looking for paid bug bounties, consider:

- [AWS Vulnerability Reporting](https://aws.amazon.com/security/vulnerability-reporting/) for AWS service vulnerabilities
- [Anthropic Responsible Disclosure](https://www.anthropic.com/security) for Bedrock/Claude vulnerabilities

---

## 🔍 Security Audit History

<!-- markdownlint-disable MD013 -->

| Date       | Auditor    | Scope               | Findings           | Status    |
| ---------- | ---------- | ------------------- | ------------------ | --------- |
| 2026-02-28 | Self-audit | Phase 4 hardening   | 0 CRITICAL, 0 HIGH | ✅ Clean  |
| 2026-02-27 | Self-audit | Phase 0 scaffolding | 0 CRITICAL, 0 HIGH | ✅ Clean  |

<!-- markdownlint-enable MD013 -->

External audit planned for post-launch (after Phase 5).

---

## 📚 Security Resources

### For Developers

- **Security rules:** `CLAUDE.md` (8 immutable rules)
- **Threat model:** `docs/threat-model.md` (Phase 1+)
- **Security patterns:** `.claude/security-patterns.md`
- **Regression tests:** `tests/security/test_clawdbot_regression.py` (Phase 1+)

### For Security Researchers

- **Penetration testing guide:** `PENTEST-GUIDE.md`
- **Architecture documentation:** `docs/architecture.md` (Phase 1+)
- **Design conversation:** Link available in README.md

### For Users

- **Deployment security:** `docs/deployment-security.md` (Phase 1+)
- **Account baseline checker:** `scripts/verify_account_baseline.py` (Phase 1+)

---

## 📞 Security Contacts

- **Lead Maintainer:** Leo Chong (@Leochong)
- **Security Email:** `security@lateos.dev` (active post-launch)
- **GitHub Security Advisory:** [Create new](https://github.com/Leochong/lateos/security/advisories/new)

---

## 🏆 Security Hall of Fame

We recognize security researchers who help make Lateos more secure:

<!-- Contributors will be listed here after responsible disclosure -->

No vulnerabilities reported yet (Phase 0)

---

## 📜 Coordinated Disclosure

We follow a **90-day coordinated disclosure** timeline:

1. **Day 0:** Vulnerability reported
2. **Day 0-7:** Acknowledgment + severity assessment
3. **Day 7-30:** Patch development + testing
4. **Day 30:** Patch released to users
5. **Day 30-90:** Grace period for users to update
6. **Day 90:** Public disclosure (CVE + security advisory)

**Exceptions:**

- **CRITICAL vulnerabilities under active exploitation:** Immediate disclosure
  after patch
- **Low-severity issues:** May be disclosed earlier with researcher consent

---

## 🔐 GPG Key

**Coming soon:** GPG public key for encrypted vulnerability reports will be
added here post-launch.

---

**Last Updated:** 2026-02-28
**Next Review:** Post-launch (after Phase 5)
