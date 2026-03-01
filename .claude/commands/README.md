# Lateos Custom Claude Code Commands

## /new-lambda

Create a new Lambda function following Lateos standards.

**Usage:** `/new-lambda skill-name=<name> trigger=<api|stepfunctions|eventbridge|sns>`

**Claude Code should:**

1. Read `lambdas/CLAUDE.md` for the handler template
2. Create `lambdas/skills/<name>/<name>_skill.py` using the handler template
3. Create `lambdas/skills/<name>/__init__.py`
4. Create `lambdas/skills/<name>/requirements.txt`
5. Create `tests/unit/test_<name>_skill.py` with standard test structure
6. Create IAM role construct in `infrastructure/constructs/<name>_role.py`
   following the least-privilege pattern in `infrastructure/CLAUDE.md`
7. Remind: "Add this Lambda to the appropriate CDK stack and wire the IAM role"

**Checklist before finishing:**

- [ ] Handler uses Powertools Logger, Tracer, Metrics
- [ ] Secrets fetched from Secrets Manager at module level
- [ ] `@safe_handler` decorator applied
- [ ] Input sanitization applied before any LLM call
- [ ] `reserved_concurrent_executions` set in CDK construct
- [ ] Explicit `timeout` set
- [ ] DLQ configured
- [ ] Test file covers: happy path, missing auth, error handling, secret source

---

## /new-stack

Create a new CDK stack following Lateos standards.

**Usage:** `/new-stack name=<StackName> purpose=<one-line description>`

**Claude Code should:**

1. Read `infrastructure/CLAUDE.md` for patterns
2. Create `infrastructure/stacks/<stack_name>.py`
3. Create `tests/infrastructure/test_<stack_name>.py`
4. Apply all required patterns:
   - Resource tagging (`Tags.of(self)`)
   - cdk-nag suppression pattern (with mandatory reason strings)
   - Removal policies (RETAIN for data, DESTROY only for logs in dev)
   - CloudWatch alarms for key resources
5. Add stack to `infrastructure/app.py`

---

## /security-review

Review a file or directory for security issues before committing.

**Usage:** `/security-review <path>`

**Claude Code should check for:**

1. Secrets in code (patterns from `tests/security/test_no_secrets_leaked.py`)
2. Banned functions: `os.system`, `subprocess`, `eval`, `exec`
3. Wildcard IAM policies
4. DynamoDB scan operations (should be queries)
5. Missing input sanitization before Bedrock calls
6. Missing `@safe_handler` decorator on Lambda handlers
7. Missing Powertools decorators
8. Raw exceptions surfaced to users
9. Missing timeout or concurrency limits in CDK constructs
10. Hardcoded ARNs or account IDs

Output: Findings list with file:line references and suggested fixes.

---

## /add-injection-test

Add a new prompt injection pattern to the regression test suite.

**Usage:** `/add-injection-test pattern=<injection string> source=<CVE or reference>`

**Claude Code should:**

1. Add the pattern to `INJECTION_PATTERNS` in `lambdas/shared/sanitizer.py`
2. Add a parametrized test case to `tests/security/test_clawdbot_regression.py`
   in the `TestPromptInjectionDefense` class
3. Add a comment with the source reference
4. Run the test to verify it passes

---

## /cost-check

Review infrastructure for potential cost runaway risks.

**Usage:** `/cost-check`

**Claude Code should:**

1. Scan all CDK stack files for:
   - Lambda functions missing `reserved_concurrent_executions`
   - Step Functions without `timeout`
   - DynamoDB tables without TTL attribute
   - Missing CloudWatch alarms
   - Bedrock calls without `max_tokens` limit
2. Check `infrastructure/stacks/cost_protection_stack.py` is included in `app.py`
3. Verify all resources have `Project=Lateos` tag
4. Report findings with file:line references

---

## /update-regression

Add a new Clawdbot/Moltbot/agentic AI CVE to the regression test suite.

**Usage:** `/update-regression cve=<CVE-ID> description=<what it exploits>`

**Claude Code should:**

1. Add a new test class to `tests/security/test_clawdbot_regression.py`
2. Document the CVE with reference links in the class docstring
3. Write tests that verify Lateos is not vulnerable
4. Update the CVE table in the root `CLAUDE.md`

---

## /check-iam

Verify IAM policies follow least-privilege for a specific Lambda or stack.

**Usage:** `/check-iam <lambda-name or stack-name>`

**Claude Code should:**

1. Find the IAM role and policy for the specified resource
2. Check for:
   - Wildcard `*` actions → flag and suggest specific actions
   - Wildcard `*` resources → flag and suggest ARN scoping
   - Missing permission boundary
   - Missing conditions (e.g., `aws:PrincipalAccount`)
   - Overly broad service access
3. Suggest the minimum viable policy for the function's actual needs

---

*Add new commands here as repetitive tasks emerge during development.*
