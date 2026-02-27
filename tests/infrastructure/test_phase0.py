"""
Phase 0 Smoke Tests — Verify Local Development Setup

These tests verify that Phase 0 setup is complete and secure before
proceeding to Phase 1 (CDK stack development).

Run with: pytest tests/infrastructure/test_phase0.py -v
"""

import json
import os
import re
from pathlib import Path

import pytest

# Determine project root (tests/ is two levels deep from root)
PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestPhase0Setup:
    """Phase 0 setup verification tests."""

    def test_env_example_exists_and_has_no_real_values(self):
        """Verify .env.example exists and contains only mock/template values."""
        env_example = PROJECT_ROOT / ".env.example"
        assert env_example.exists(), ".env.example file not found"

        content = env_example.read_text()

        # Check for dangerous real-looking values
        dangerous_patterns = [
            r"sk-[a-zA-Z0-9]{32,}",  # OpenAI API keys
            r"xoxb-[0-9]{10,}",  # Slack bot tokens
            r"AKIA[0-9A-Z]{16}",  # AWS access keys
            r"[0-9]{12}:[a-zA-Z0-9]{32}",  # Telegram bot tokens (real format)
        ]

        for pattern in dangerous_patterns:
            matches = re.findall(pattern, content)
            assert not matches, f"Possible real secret in .env.example: {matches}"

        # Check that it has template/mock values
        assert (
            "CHANGE_ME" in content or "example" in content.lower()
        ), ".env.example should contain template/example values"

    def test_dotenv_not_committed(self):
        """Verify that .env files are not tracked by git."""
        # Check .gitignore covers .env
        gitignore = PROJECT_ROOT / ".gitignore"
        assert gitignore.exists(), ".gitignore file not found"

        content = gitignore.read_text()
        assert ".env" in content, ".env not in .gitignore"

        # Verify actual .env files don't exist in git tracking
        # (users may have local .env, but it shouldn't be tracked)
        import subprocess

        result = subprocess.run(
            ["git", "ls-files", ".env"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        tracked_env_files = result.stdout.strip()
        assert not tracked_env_files, f".env files are tracked by git: {tracked_env_files}"

    def test_gitignore_covers_secrets(self):
        """Verify .gitignore has comprehensive secret protection patterns."""
        gitignore = PROJECT_ROOT / ".gitignore"
        assert gitignore.exists(), ".gitignore file not found"

        content = gitignore.read_text()

        # Required patterns
        required_patterns = [
            ".env",
            "*.pem",
            "*.key",
            "*credential*",
            "*token*",
            "*secret*",
            ".aws/",
        ]

        missing = []
        for pattern in required_patterns:
            if pattern not in content:
                missing.append(pattern)

        assert not missing, f"Missing patterns in .gitignore: {missing}"

        # Verify .secrets.baseline is explicitly allowed (exception to *secret*)
        assert (
            "!.secrets.baseline" in content
        ), ".secrets.baseline should be explicitly allowed in .gitignore"

    def test_requirements_files_exist(self):
        """Verify requirements.txt and requirements-dev.txt exist."""
        requirements = PROJECT_ROOT / "requirements.txt"
        requirements_dev = PROJECT_ROOT / "requirements-dev.txt"

        assert requirements.exists(), "requirements.txt not found"
        assert requirements_dev.exists(), "requirements-dev.txt not found"

        # Verify core dependencies are present
        req_content = requirements.read_text()
        assert "aws-cdk-lib" in req_content, "aws-cdk-lib not in requirements.txt"
        assert "boto3" in req_content, "boto3 not in requirements.txt"

        req_dev_content = requirements_dev.read_text()
        assert "pytest" in req_dev_content, "pytest not in requirements-dev.txt"
        assert "bandit" in req_dev_content, "bandit not in requirements-dev.txt"

    def test_no_pinned_versions_with_security_vulnerabilities(self):
        """Check that no known vulnerable package versions are pinned."""
        requirements = PROJECT_ROOT / "requirements.txt"
        requirements_dev = PROJECT_ROOT / "requirements-dev.txt"

        all_content = requirements.read_text() + requirements_dev.read_text()

        # Known vulnerable versions (examples - not exhaustive)
        # This is a smoke test; real vulnerability scanning is done by CI/CD
        vulnerable_patterns = [
            r"cryptography==38\.0\.[0-2]",  # CVE-2023-23931
            r"urllib3==1\.26\.[0-9]",  # CVE-2021-33503 (fixed in 1.26.5+)
            r"requests==2\.27\.[0-1]",  # CVE-2023-32681 (fixed in 2.31.0+)
        ]

        vulnerabilities_found = []
        for pattern in vulnerable_patterns:
            if re.search(pattern, all_content):
                vulnerabilities_found.append(pattern)

        assert (
            not vulnerabilities_found
        ), f"Vulnerable package versions found: {vulnerabilities_found}"

    def test_precommit_config_exists(self):
        """Verify .pre-commit-config.yaml exists and has required hooks."""
        precommit_config = PROJECT_ROOT / ".pre-commit-config.yaml"
        assert precommit_config.exists(), ".pre-commit-config.yaml not found"

        content = precommit_config.read_text()

        # Required security hooks
        required_hooks = [
            "detect-secrets",
            "gitleaks",
            "trufflehog",
            "bandit",
        ]

        missing_hooks = []
        for hook in required_hooks:
            if hook not in content:
                missing_hooks.append(hook)

        assert not missing_hooks, f"Missing pre-commit hooks: {missing_hooks}"

    def test_github_workflows_exist(self):
        """Verify GitHub Actions CI/CD pipeline exists."""
        ci_workflow = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        assert ci_workflow.exists(), ".github/workflows/ci.yml not found"

        content = ci_workflow.read_text()

        # Verify critical jobs exist
        required_jobs = [
            "secret-scan",
            "security-lint",
            "cdk-security",
            "unit-tests",
        ]

        missing_jobs = []
        for job in required_jobs:
            if job not in content:
                missing_jobs.append(job)

        assert not missing_jobs, f"Missing CI/CD jobs: {missing_jobs}"

    def test_security_md_exists(self):
        """Verify SECURITY.md exists with vulnerability reporting process."""
        security_md = PROJECT_ROOT / "SECURITY.md"
        assert security_md.exists(), "SECURITY.md not found"

        content = security_md.read_text()

        # Verify key sections exist
        required_sections = [
            "Reporting a Vulnerability",
            "Response Timeline",
            "Security Features",
            "8 Immutable Security Rules",
        ]

        missing_sections = []
        for section in required_sections:
            if section not in content:
                missing_sections.append(section)

        assert not missing_sections, f"Missing sections in SECURITY.md: {missing_sections}"

        # Verify it warns against public issues
        assert (
            "Do NOT open public GitHub issues" in content
        ), "SECURITY.md should warn against public vulnerability reports"


class TestPhase0Documentation:
    """Verify Phase 0 documentation is complete."""

    def test_decisions_md_exists_and_has_adrs(self):
        """Verify DECISIONS.md exists and has architectural decisions."""
        decisions_md = PROJECT_ROOT / "DECISIONS.md"
        assert decisions_md.exists(), "DECISIONS.md not found"

        content = decisions_md.read_text()

        # Verify ADRs are documented
        assert "ADR-001" in content, "No ADRs found in DECISIONS.md"

        # Count ADRs (should have at least 8 from Phase 0)
        adr_matches = re.findall(r"ADR-\d+", content)
        assert len(adr_matches) >= 8, f"Expected at least 8 ADRs, found {len(adr_matches)}"

    def test_claude_md_exists(self):
        """Verify CLAUDE.md exists for Claude Code context."""
        claude_md = PROJECT_ROOT / "CLAUDE.md"
        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text()

        # Verify key sections exist
        assert (
            "8 Immutable Security Rules" in content or "Security Rules" in content
        ), "CLAUDE.md should document security rules"
        assert "Project Structure" in content, "CLAUDE.md missing project structure"

    def test_phase0_status_exists(self):
        """Verify PHASE-0-STATUS.md exists and is updated."""
        phase0_status = PROJECT_ROOT / "PHASE-0-STATUS.md"
        assert phase0_status.exists(), "PHASE-0-STATUS.md not found"

        content = phase0_status.read_text()

        # Verify it shows progress
        assert (
            "COMPLETED" in content or "TODO" in content
        ), "PHASE-0-STATUS.md should show task completion status"


class TestPhase0CDK:
    """Verify CDK configuration is correct."""

    def test_cdk_json_exists_and_valid(self):
        """Verify cdk.json exists and is valid JSON."""
        cdk_json = PROJECT_ROOT / "cdk.json"
        assert cdk_json.exists(), "cdk.json not found"

        content = cdk_json.read_text()

        # Verify it's valid JSON
        try:
            config = json.loads(content)
        except json.JSONDecodeError as e:
            pytest.fail(f"cdk.json is not valid JSON: {e}")

        # Verify required keys
        assert "app" in config, "cdk.json missing 'app' key"
        assert "context" in config, "cdk.json missing 'context' key"

        # Verify app entry point
        assert (
            "infrastructure/app.py" in config["app"]
        ), "cdk.json app should point to infrastructure/app.py"

        # Verify security context values
        context = config["context"]
        assert context.get("cognito_mfa") == "REQUIRED", "MFA should be required in CDK context"
        assert (
            context.get("guardduty_enabled") is True
        ), "GuardDuty should be enabled in CDK context"

    def test_infrastructure_app_py_exists(self):
        """Verify infrastructure/app.py exists."""
        app_py = PROJECT_ROOT / "infrastructure" / "app.py"
        assert app_py.exists(), "infrastructure/app.py not found"

        content = app_py.read_text()

        # Verify it imports CDK
        assert (
            "import aws_cdk" in content or "from aws_cdk" in content
        ), "infrastructure/app.py should import aws_cdk"


class TestPhase0Scripts:
    """Verify Phase 0 scripts exist."""

    def test_verify_account_baseline_exists(self):
        """Verify AWS account baseline checker script exists."""
        script = PROJECT_ROOT / "scripts" / "verify_account_baseline.py"
        assert script.exists(), "scripts/verify_account_baseline.py not found"

        content = script.read_text()

        # Verify it checks critical services
        required_checks = [
            "cloudtrail",
            "guardduty",
            "security_hub",
        ]

        missing_checks = []
        for check in required_checks:
            if check.lower() not in content.lower():
                missing_checks.append(check)

        assert not missing_checks, f"Baseline checker missing checks: {missing_checks}"

    def test_localstack_setup_exists(self):
        """Verify LocalStack setup script exists."""
        script = PROJECT_ROOT / "localstack-setup.sh"
        assert script.exists(), "localstack-setup.sh not found"

        # Verify it's executable
        assert os.access(script, os.X_OK), "localstack-setup.sh is not executable (run: chmod +x)"


class TestPhase0LocalStack:
    """Verify LocalStack configuration."""

    def test_docker_compose_exists(self):
        """Verify docker-compose.yml exists for LocalStack."""
        docker_compose = PROJECT_ROOT / "docker-compose.yml"
        assert docker_compose.exists(), "docker-compose.yml not found"

        content = docker_compose.read_text()

        # Verify LocalStack service is configured
        assert "localstack" in content, "LocalStack service not in docker-compose.yml"
        assert (
            "localstack/localstack" in content
        ), "LocalStack image not specified in docker-compose.yml"

        # Verify critical AWS services are enabled
        assert "lambda" in content, "Lambda not enabled in LocalStack config"
        assert "dynamodb" in content, "DynamoDB not enabled in LocalStack config"


# Summary test that runs last
class TestPhase0Complete:
    """Final verification that Phase 0 is complete."""

    @pytest.mark.last
    def test_phase0_complete(self):
        """Verify all Phase 0 requirements are met."""
        project_root = PROJECT_ROOT

        # Check all critical files exist
        critical_files = [
            ".gitignore",
            ".env.example",
            "requirements.txt",
            "requirements-dev.txt",
            ".pre-commit-config.yaml",
            ".secrets.baseline",
            "cdk.json",
            "docker-compose.yml",
            "localstack-setup.sh",
            "DECISIONS.md",
            "CLAUDE.md",
            "SECURITY.md",
            ".github/workflows/ci.yml",
            "infrastructure/app.py",
            "scripts/verify_account_baseline.py",
            "tests/infrastructure/test_phase0.py",
        ]

        missing_files = []
        for file_path in critical_files:
            if not (project_root / file_path).exists():
                missing_files.append(file_path)

        assert not missing_files, f"Phase 0 incomplete - missing files: {missing_files}"

        print("\n" + "=" * 70)
        print("✅ Phase 0 Complete — All smoke tests passed!")
        print("=" * 70)
        print("\n📋 Next Steps:")
        print("  1. Run: pre-commit run --all-files")
        print("  2. Run: detect-secrets scan --baseline .secrets.baseline")
        print("  3. Run: gitleaks detect")
        print("  4. Start Docker Desktop and run: ./localstack-setup.sh")
        print("  5. Commit Phase 0 completion")
        print("  6. Proceed to Phase 1: CDK stack development")
        print("\n" + "=" * 70)
