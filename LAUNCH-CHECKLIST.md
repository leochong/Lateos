# Lateos Launch Checklist

**Purpose:** Pre-launch verification checklist for Lateos before making the repository public and deploying to real AWS.

**Last Updated:** 2026-02-28
**Target Launch Date:** TBD (after Phase 5.5 - Documentation Sprint)

---

## AUTOMATED CHECKS (Claude Code / CI/CD Verifies These)

These checks are automated and can be verified by running the commands below. All must pass before launch.

###  Test Suite

```bash
source .venv312/bin/activate
pytest tests/ -v
```

**Expected Result:**

- All unit tests passing
- Security tests passing (43 prompt injection test cases)
- Integration tests may be skipped (LocalStack not deployed)
- Coverage e 80% (measured in `pytest --cov` in CI/CD)

**Status:** [ ] PASS  [ ] FAIL

---

###  CDK Synthesis

```bash
source .venv312/bin/activate
cdk synth
```

**Expected Result:**

- All 5 stacks synthesize without errors:
  - `LateosCoreDevStack`
  - `LateosMemoryDevStack`
  - `LateosCostProtectionDevStack`
  - `LateosSkillsDevStack`
  - `LateosOrchestrationDevStack`
- No deprecation warnings blocking deployment
- CloudFormation templates generated in `cdk.out/`

**Status:** [ ] PASS  [ ] FAIL

---

###  Pre-Commit Hooks

```bash
pre-commit run --all-files
```

**Expected Result:**

- All hooks passing:
  - `detect-secrets`  No secrets in codebase
  - `gitleaks`  No secrets in git history
  - `black`  Python code formatted
  - `isort`  Imports sorted
  - `flake8`  Linting clean
  - `bandit`  No security vulnerabilities (HIGH/CRITICAL)
  - `markdownlint`  Markdown formatted (warnings acceptable)

**Status:** [ ] PASS  [ ] FAIL

---

###  Secret Detection

```bash
detect-secrets scan --baseline .secrets.baseline
gitleaks detect --no-git
```

**Expected Result:**

- No new secrets detected
- `.secrets.baseline` up to date
- Git history clean (no leaked credentials)

**Status:** [ ] PASS  [ ] FAIL

---

###  README.md Renders Correctly

```bash
# View on GitHub (after push to main)
# Or use grip for local preview:
grip README.md
```

**Expected Result:**

- All markdown renders correctly
- Links functional
- Images display (if any)
- Architecture diagram visible (Phase 5.5)
- Badges showing (build status, coverage)

**Status:** [ ] PASS  [ ] FAIL

---

###  Security Documentation Complete

**Files to verify exist and are up-to-date:**

- [ ] `SECURITY.md` (vulnerability reporting policy)
- [ ] `CONTRIBUTING.md` (security-first contribution guide)
- [ ] `PENTEST-GUIDE.md` (penetration testing guide)
- [ ] `docs/CVE-CHECKLIST.md` (OpenClaw CVE mapping)
- [ ] `DECISIONS.md` (ADRs 001-016 documented)

**Status:** [ ] PASS  [ ] FAIL

---

###  Error Code Coverage

**Verify all Lambda functions use LATEOS error codes:**

```bash
# Check that all Lambdas import error_codes
grep -r "from shared.error_codes import" lambdas/
```

**Expected Result:**

- All core Lambdas use LATEOS error codes
- All skill Lambdas use LATEOS error codes
- Error codes LATEOS-001 through LATEOS-015 defined in `lambdas/shared/error_codes.py`

**Status:** [ ] PASS  [ ] FAIL

---

###  Git Status Clean

```bash
git status
```

**Expected Result:**

- No uncommitted changes
- Working directory clean
- All Phase 5 work committed
- Latest commit on `main` branch

**Status:** [ ] PASS  [ ] FAIL

---

## MANUAL CHECKS (Leo Does These)

These checks require manual verification and cannot be fully automated.

### =

 Review LAUNCH-CHECKLIST.md Top to Bottom

- [ ] Read through this entire checklist
- [ ] Verify all automated checks have been run
- [ ] Verify all automated checks have passed
- [ ] Document any failing checks and create GitHub issues
- [ ] Confirm no blockers for launch

**Status:** [ ] DONE  [ ] PENDING

---

### < lateos.ai DNS Configured and Resolving

**Verify DNS setup:**

```bash
dig lateos.ai +short
nslookup lateos.ai
```

**Expected Result:**

- DNS A record points to AWS CloudFront/ALB (Phase 5+ deployment)
- DNS propagated globally (check from multiple locations)
- HTTPS certificate valid (Let's Encrypt or AWS ACM)
- No DNS hijacking or typosquatting

**Actions Required:**

- [ ] Configure Cloudflare DNS to point to AWS (after deployment)
- [ ] Enable Cloudflare proxy (orange cloud) for DDoS protection
- [ ] Configure SSL/TLS to "Full (strict)" mode
- [ ] Enable DNSSEC
- [ ] Set up CAA records (limit cert issuance to AWS ACM, Let's Encrypt)

**Status:** [ ] DONE  [ ] PENDING

---

###  AWS Deployment to Real Account (Not LocalStack)

**Pre-deployment verification:**

1. **Run account baseline checker:**

   ```bash
   python scripts/verify_account_baseline.py --profile lateos-prod
   ```

2. **Deploy to AWS:**

   ```bash
   # Ensure AWS credentials are configured
   aws sts get-caller-identity --profile lateos-prod

   # Deploy all stacks
   cdk deploy --all --profile lateos-prod --require-approval never
   ```

3. **Post-deployment verification:**
   - [ ] All 5 stacks deployed successfully
   - [ ] API Gateway endpoint reachable
   - [ ] Cognito User Pool created
   - [ ] DynamoDB tables created with KMS encryption
   - [ ] Lambda functions deployed with correct runtime (Python 3.12)
   - [ ] Step Functions workflow defined
   - [ ] Cost protection kill switch configured
   - [ ] CloudWatch Logs encrypted with KMS
   - [ ] IAM roles scoped correctly (no wildcards)
   - [ ] S3 buckets private (no public access)

4. **Smoke test:**

   ```bash
   # Create test user in Cognito
   aws cognito-idp admin-create-user \
     --user-pool-id <USER_POOL_ID> \
     --username test-user \
     --profile lateos-prod

   # Send test request to API Gateway
   curl -X POST <API_GATEWAY_URL>/agent \
     -H "Authorization: Bearer <COGNITO_JWT>" \
     -H "Content-Type: application/json" \
     -d '{"message": "Hello Lateos"}'
   ```

**Status:** [ ] DONE  [ ] PENDING

---

### = GitHub Repo Visibility Set to Public

**CRITICAL: Do NOT set repo to public until ALL other checks complete.**

**Steps:**

1. Go to <https://github.com/Leochong/lateos/settings>
2. Scroll to "Danger Zone"
3. Click "Change repository visibility"
4. Select "Public"
5. Type repository name to confirm
6. Click "I understand, change repository visibility"

**Pre-public checklist:**

- [ ] All automated checks passing
- [ ] All sensitive data removed from git history
- [ ] No secrets in `.env` files (only `.env.example` committed)
- [ ] `SECURITY.md` reviewed
- [ ] `README.md` finalized
- [ ] License file present (MIT)
- [ ] `.gitignore` covers all sensitive patterns

**Status:** [ ] DONE  [ ] PENDING

---

### =� Wave 1 LinkedIn Post Reviewed and Ready

**Draft LinkedIn announcement:**

```markdown
=� Introducing Lateos: Security-By-Design AI Personal Agent

After the Clawdbot/Moltbot security crisis exposed 1,247 leaked API keys and $50K in fraud, I built Lateos to prove AI agents can be secure from day one.

= What makes Lateos different:
" Serverless architecture (no listening processes = no RCE)
" 8 immutable security rules enforced by CI/CD
" Every OpenClaw CVE architecturally eliminated
" Prompt injection detection (21 patterns, 43 test cases)
" Scoped IAM roles (one per skill, no wildcasts)
" Open-source, MIT licensed

=� Full transparency:
" Security policy: github.com/Leochong/lateos/SECURITY.md
" CVE checklist: github.com/Leochong/lateos/docs/CVE-CHECKLIST.md
" Pentest guide: github.com/Leochong/lateos/PENTEST-GUIDE.md
" Design decisions: github.com/Leochong/lateos/DECISIONS.md

=� Built by: Leo Chong (CISSP, AWS Cloud Practitioner, CCNA Security)
= GitHub: github.com/Leochong/lateos
< Docs: lateos.ai

Security researchers welcome. No bug bounty (yet), but I respond to every report.

#AIagents #security #opensource #AWS #serverless
```

**Review checklist:**

- [ ] Proofread for typos
- [ ] Links functional
- [ ] Tone professional but authentic
- [ ] No overpromises
- [ ] Security focus clear
- [ ] Credit to Claude AI/Anthropic (design assistance)
- [ ] Tagged relevant people (optional)

**Status:** [ ] DONE  [ ] PENDING

---

### =� Phase 5.5 Documentation Sprint Complete

**Documentation to finalize before public launch:**

- [ ] `README.md`  Project overview, quick start, architecture diagram
- [ ] `docs/architecture.md`  Detailed system architecture
- [ ] `docs/threat-model.md`  Threat analysis and mitigations
- [ ] `docs/deployment-guide.md`  Step-by-step AWS deployment
- [ ] `docs/skills/`  Documentation for each skill Lambda
- [ ] `CHANGELOG.md`  Version history (start with v0.1.0)
- [ ] `LICENSE`  MIT License (already exists)

**Status:** [ ] DONE  [ ] PENDING

---

## POST-LAUNCH MONITORING

After launch, monitor these metrics for the first 48 hours:

### CloudWatch Metrics

- [ ] Lambda error rates (target: < 1%)
- [ ] API Gateway 4xx/5xx rates
- [ ] DynamoDB throttling (should be 0)
- [ ] Step Functions failed executions
- [ ] CloudWatch Log errors (filter for ERROR level)

### Cost Protection

- [ ] AWS Budgets alert not triggered
- [ ] Estimated monthly cost < $10
- [ ] No unexpected charges (Lambda concurrency capped)

### Security

- [ ] No failed authentication attempts (Cognito)
- [ ] No IAM AccessDenied errors (CloudTrail)
- [ ] No S3 bucket public access warnings (AWS Config)
- [ ] Security Hub findings = 0 CRITICAL, 0 HIGH

### GitHub Activity

- [ ] GitHub Issues triaged (respond within 48 hours)
- [ ] Pull requests reviewed (if any)
- [ ] Security advisories monitored
- [ ] Discussions responded to

---

## ROLLBACK PLAN

If critical issues are discovered post-launch:

### Immediate Actions (< 5 minutes)

1. **Revert GitHub to private:**

   ```bash
   # Go to Settings > Danger Zone > Change visibility > Private
   ```

2. **Disable API Gateway:**

   ```bash
   aws apigateway update-stage \
     --rest-api-id <API_ID> \
     --stage-name prod \
     --patch-operations op=replace,path=/deploymentId,value=<OLD_DEPLOYMENT_ID> \
     --profile lateos-prod
   ```

3. **Post incident notice:**

   ```markdown
   # Pin to GitHub repo
   � NOTICE: Lateos is temporarily offline while we address [issue].
   Expected resolution: [timeframe]
   Security impact: [assessment]
   ```

### Investigation (< 1 hour)

- Review CloudWatch Logs for error patterns
- Check CloudTrail for suspicious API calls
- Review Security Hub findings
- Analyze AWS Config compliance

### Fix and Redeploy (< 4 hours)

- Create hotfix branch
- Fix issue
- Re-run all automated checks
- Deploy to staging (if available)
- Re-deploy to production
- Re-enable API Gateway
- Set GitHub to public

### Post-Mortem (< 24 hours)

- Document incident in `docs/incidents/YYYY-MM-DD-incident-name.md`
- Update STATUS.md
- Create GitHub issue for tracking
- Send update to community (if major incident)

---

## LAUNCH DECISION

**Launch is GO when:**

- [x] All automated checks passing
- [ ] All manual checks complete
- [ ] No CRITICAL or HIGH severity blockers
- [ ] Leo has reviewed this checklist top to bottom
- [ ] AWS deployment successful and smoke-tested
- [ ] Documentation complete (Phase 5.5)
- [ ] LinkedIn post ready (not necessarily posted)

**Launch authority:** Leo Chong (project lead)

**Signature:** ____________________  **Date:** __________

---

**Next Steps After Launch:**

1. Monitor CloudWatch metrics (first 48 hours)
2. Respond to GitHub issues/PRs
3. Address security reports (if any)
4. Plan Phase 6+ features (multi-channel integrations, advanced skills)
5. Consider external security audit (if budget allows)

---

**Last Updated:** 2026-02-28
**Maintained by:** Leo (CISSP, AWS Cloud Practitioner, CCNA Security, NREMT)

*This checklist will be reviewed and updated after each major release.*
