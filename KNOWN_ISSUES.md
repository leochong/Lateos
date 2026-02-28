# Lateos — Known Issues

This document tracks known issues, limitations, and their resolutions for the Lateos project.

---

## Issue #1: Python 3.14 Incompatibility with JSII/CDK

**Status:** Resolved
**Severity:** Blocker
**Affected Components:** CDK infrastructure code
**Date Discovered:** 2026-02-27

### Problem

Python 3.14 (pre-release) is incompatible with the JSII runtime used by AWS CDK. When running `cdk synth` or attempting to import `aws_cdk` modules, the following error occurs:

```
ModuleNotFoundError: No module named 'constructs._jsii'
```

This error occurs even though:

- The `constructs` package is properly installed
- The `_jsii` subdirectory exists in the package
- Direct imports work in interactive Python sessions

### Root Cause

The JSII runtime (JavaScript Interoperability) used by AWS CDK does not yet support Python 3.14. JSII is responsible for bridging Python and the underlying TypeScript CDK constructs.

### Resolution

**Use Python 3.12 for all development:**

1. Install Python 3.12: `brew install python@3.12`
2. Create dedicated virtual environment: `python3.12 -m venv .venv312`
3. Install requirements: `pip install -r requirements.txt -r requirements-dev.txt`
4. Update `cdk.json` to use Python 3.12: `"app": ".venv312/bin/python infrastructure/cdk_wrapper.py"`

**Related ADR:** See ADR-013 in DECISIONS.md

### Testing

Verified working with:

- Python 3.12.12
- aws-cdk-lib 2.240.0
- constructs 10.5.1
- jsii 1.127.0

### Future Outlook

Monitor JSII/CDK releases for Python 3.14 support. Track at:

- <https://github.com/aws/jsii/issues>
- <https://github.com/aws/aws-cdk/issues>

---

## Issue #2: Naming Conflict with `infrastructure/constructs/` Directory

**Status:** Resolved
**Severity:** Blocker
**Affected Components:** CDK infrastructure code
**Date Discovered:** 2026-02-27

### Problem

When running Python scripts from the `infrastructure/` directory, imports of the `constructs` pip package fail with:

```
ModuleNotFoundError: No module named 'constructs._jsii'
```

This occurs even though the package is installed and imports work from other directories.

### Root Cause

Python adds the script's directory to `sys.path` when running. The `infrastructure/constructs/` directory (intended for reusable CDK constructs) shadows the installed `constructs` pip package. Python finds the local empty directory first and fails to import `._jsii` submodule.

### Resolution

**Renamed the directory to avoid shadowing:**

```bash
mv infrastructure/constructs infrastructure/cdk_constructs
```

All future reusable CDK constructs should be placed in `infrastructure/cdk_constructs/`.

### Prevention

**Never create directories in `infrastructure/` that match pip package names:**

- ❌ `constructs/` (conflicts with `constructs` package)
- ❌ `aws_cdk/` (conflicts with `aws-cdk-lib` package)
- ❌ `jsii/` (conflicts with `jsii` package)
- ✅ `cdk_constructs/` (safe)
- ✅ `lateos_constructs/` (safe)
- ✅ `stacks/` (safe)

### Testing

After renaming:

```bash
.venv312/bin/python -c "import constructs._jsii"  # Success
cdk synth  # Success
```

---

## Issue #3: CDK CLI Version Mismatch

**Status:** Resolved
**Severity:** High
**Affected Components:** CDK infrastructure deployment
**Date Discovered:** 2026-02-27

### Problem

After fixing Python version and constructs naming issues, `cdk synth` fails with:

```
This CDK CLI is not compatible with the CDK library used by your application.
Maximum schema version supported is 48.x.x, but found 50.0.0.
```

### Root Cause

The aws-cdk-lib Python package (v2.240.0) uses cloud assembly schema version 50, but the globally installed CDK CLI was outdated and only supported up to schema version 48.

### Resolution

**Upgrade CDK CLI to latest version:**

```bash
npm install -g aws-cdk@latest
```

### Verification

```bash
cdk --version  # Should show 2.1105.0 or higher
cdk synth      # Should succeed
```

### Prevention

Keep CDK CLI and aws-cdk-lib versions in sync:

- Check versions before major CDK library upgrades
- Update both CLI and library together
- Document minimum required CLI version in README.md

---

## Issue #4: Cognito `advancedSecurityMode` Deprecation Warnings

**Status:** Known, Non-blocking
**Severity:** Low
**Affected Components:** CoreStack Cognito User Pool
**Date Discovered:** 2026-02-27

### Problem

When running `cdk synth`, deprecation warnings appear:

```
[WARNING] aws-cdk-lib.aws_cognito.UserPoolProps#advancedSecurityMode is deprecated.
Advanced Security Mode is deprecated due to user pool feature plans.
Use StandardThreatProtectionMode and CustomThreatProtectionMode to set Thread Protection level.
```

### Impact

- No functional impact (still works)
- Will break in next major CDK version
- Affects user pool security configuration

### Resolution Plan

**Deferred to Phase 2 (Pre-Public Launch):**

1. Review new threat protection modes in CDK documentation
2. Update CoreStack to use `StandardThreatProtectionMode`
3. Test threat protection configuration
4. Update before next major CDK upgrade

**Tracking:** Add to Phase 2 security hardening checklist

---

## Template for Future Issues

```markdown
## Issue #N: [Short Title]

**Status:** Open | In Progress | Resolved | Wontfix
**Severity:** Blocker | High | Medium | Low
**Affected Components:** [Component names]
**Date Discovered:** YYYY-MM-DD

### Problem
[Describe the issue and how it manifests]

### Root Cause
[Technical explanation of why it happens]

### Resolution
[How to fix it, or planned fix]

### Testing
[How to verify the fix works]

### Prevention (if applicable)
[How to avoid this in the future]
```

---

*Last Updated: 2026-02-27*
*Maintainer: Leo Chong*
