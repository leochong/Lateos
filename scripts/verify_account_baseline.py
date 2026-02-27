#!/usr/bin/env python3
"""
Lateos AWS Account Security Baseline Checker

Verifies that the AWS account meets minimum security requirements before
allowing CDK deployment. This prevents deploying Lateos into an insecure AWS
environment.

Usage:
    python scripts/verify_account_baseline.py [--profile PROFILE] [--region REGION]

Exit Codes:
    0 - All checks passed
    1 - One or more checks failed
    2 - AWS credentials not configured or boto3 error

Author: Leo Chong (CISSP, AWS Cloud Practitioner, CCNA Security, NREMT)
"""

import argparse
import sys
from typing import Dict, Tuple

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    print("❌ ERROR: boto3 not installed. Run: pip install boto3")
    sys.exit(2)


class SecurityBaselineChecker:
    """Checks AWS account security baseline requirements."""

    def __init__(self, profile: str = None, region: str = "us-east-1"):
        """Initialize the checker with AWS session."""
        try:
            session_args = {"region_name": region}
            if profile:
                session_args["profile_name"] = profile

            self.session = boto3.Session(**session_args)
            self.region = region
            self.account_id = self.session.client("sts").get_caller_identity()["Account"]
            print(f"🔍 Checking AWS Account: {self.account_id}")
            print(f"📍 Region: {region}")
            print("=" * 70)
        except NoCredentialsError:
            print("❌ AWS credentials not configured")
            print("   Run: aws configure")
            sys.exit(2)
        except Exception as e:
            print(f"❌ Failed to initialize AWS session: {e}")
            sys.exit(2)

    def check_cloudtrail(self) -> Tuple[bool, str]:
        """Verify CloudTrail is enabled and logging."""
        try:
            client = self.session.client("cloudtrail")
            trails = client.describe_trails()["trailList"]

            if not trails:
                return False, "No CloudTrail trails configured"

            # Check if at least one trail is logging
            for trail in trails:
                trail_name = trail["Name"]
                status = client.get_trail_status(Name=trail_name)
                if status["IsLogging"]:
                    return True, f"CloudTrail active: {trail_name}"

            return False, "CloudTrail configured but not logging"

        except ClientError as e:
            return False, f"Cannot check CloudTrail: {e}"

    def check_guardduty(self) -> Tuple[bool, str]:
        """Verify GuardDuty is enabled."""
        try:
            client = self.session.client("guardduty")
            detectors = client.list_detectors()["DetectorIds"]

            if not detectors:
                return False, "GuardDuty not enabled"

            # Check if detector is active
            detector_id = detectors[0]
            detector = client.get_detector(DetectorId=detector_id)

            if detector["Status"] == "ENABLED":
                return True, f"GuardDuty enabled: {detector_id}"
            else:
                return False, "GuardDuty detector exists but disabled"

        except ClientError as e:
            if e.response["Error"]["Code"] == "AccessDeniedException":
                return (
                    False,
                    "Cannot check GuardDuty (insufficient permissions)",
                )
            return False, f"Cannot check GuardDuty: {e}"

    def check_security_hub(self) -> Tuple[bool, str]:
        """Verify Security Hub is enabled."""
        try:
            client = self.session.client("securityhub")
            hub = client.describe_hub()

            if hub["HubArn"]:
                return True, "Security Hub enabled"

        except ClientError as e:
            if e.response["Error"]["Code"] == "InvalidAccessException":
                return False, "Security Hub not enabled"
            return False, f"Cannot check Security Hub: {e}"

        return False, "Security Hub status unknown"

    def check_iam_access_analyzer(self) -> Tuple[bool, str]:
        """Verify IAM Access Analyzer exists."""
        try:
            client = self.session.client("accessanalyzer")
            analyzers = client.list_analyzers()["analyzers"]

            active_analyzers = [a for a in analyzers if a["status"] == "ACTIVE"]

            if active_analyzers:
                analyzer_name = active_analyzers[0]["name"]
                return True, f"IAM Access Analyzer active: {analyzer_name}"
            elif analyzers:
                return False, "IAM Access Analyzer exists but not active"
            else:
                return False, "IAM Access Analyzer not configured"

        except ClientError as e:
            return False, f"Cannot check IAM Access Analyzer: {e}"

    def check_s3_block_public_access(self) -> Tuple[bool, str]:
        """Verify S3 Block Public Access is enabled at account level."""
        try:
            client = self.session.client("s3control")
            config = client.get_public_access_block(AccountId=self.account_id)
            block = config["PublicAccessBlockConfiguration"]

            if all(
                [
                    block.get("BlockPublicAcls"),
                    block.get("IgnorePublicAcls"),
                    block.get("BlockPublicPolicy"),
                    block.get("RestrictPublicBuckets"),
                ]
            ):
                return True, "S3 Block Public Access enabled (all settings)"
            else:
                return False, "S3 Block Public Access partially configured"

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchPublicAccessBlockConfiguration":
                return False, "S3 Block Public Access not configured"
            return False, f"Cannot check S3 Block Public Access: {e}"

    def check_ebs_encryption(self) -> Tuple[bool, str]:
        """Verify EBS encryption is enabled by default."""
        try:
            client = self.session.client("ec2")
            result = client.get_ebs_encryption_by_default()

            if result["EbsEncryptionByDefault"]:
                return True, "EBS encryption enabled by default"
            else:
                return False, "EBS encryption not enabled by default"

        except ClientError as e:
            return False, f"Cannot check EBS encryption: {e}"

    def check_root_account_mfa(self) -> Tuple[bool, str]:
        """Verify root account has MFA enabled."""
        try:
            client = self.session.client("iam")
            summary = client.get_account_summary()["SummaryMap"]

            # Note: This check is limited - it checks if ANY MFA devices exist
            # for the account, not specifically root MFA
            if summary.get("AccountMFAEnabled", 0) == 1:
                return True, "Root account MFA enabled"
            else:
                return (
                    False,
                    "Root account MFA not enabled (CRITICAL SECURITY RISK)",
                )

        except ClientError as e:
            return False, f"Cannot check root MFA: {e}"

    def check_root_access_keys(self) -> Tuple[bool, str]:
        """Verify root account has no active access keys."""
        try:
            client = self.session.client("iam")
            report = client.get_credential_report()

            # This requires credential report to be generated
            # If not generated, we'll return a warning
            if report["Content"]:
                import csv
                import io

                content = report["Content"].decode("utf-8")
                reader = csv.DictReader(io.StringIO(content))

                for row in reader:
                    if row["user"] == "<root_account>":
                        has_key1 = row.get("access_key_1_active") == "true"
                        has_key2 = row.get("access_key_2_active") == "true"

                        if not has_key1 and not has_key2:
                            return True, "Root account has no active access keys"
                        else:
                            return (
                                False,
                                "Root account has active access keys (DELETE THEM)",
                            )

        except ClientError as e:
            if e.response["Error"]["Code"] == "ReportNotPresent":
                # Try to generate the report
                try:
                    client.generate_credential_report()
                    return (
                        None,
                        "Credential report generating (re-run in 60 seconds)",
                    )
                except ClientError:
                    pass
            return None, f"Cannot check root access keys: {e}"

        return None, "Cannot verify root access keys"

    def check_billing_alerts(self) -> Tuple[bool, str]:
        """Verify billing alerts/budgets are configured."""
        try:
            # Check AWS Budgets
            client = self.session.client("budgets")
            budgets = client.describe_budgets(AccountId=self.account_id)["Budgets"]

            if budgets:
                budget_names = [b["BudgetName"] for b in budgets]
                return True, f"Budgets configured: {', '.join(budget_names)}"

            return False, "No billing alerts or budgets configured"

        except ClientError as e:
            if e.response["Error"]["Code"] == "AccessDeniedException":
                return (
                    None,
                    "Cannot check budgets (insufficient permissions)",
                )
            return False, f"Cannot check billing alerts: {e}"

    def check_config_enabled(self) -> Tuple[bool, str]:
        """Verify AWS Config is enabled."""
        try:
            client = self.session.client("config")
            recorders = client.describe_configuration_recorders()

            if not recorders.get("ConfigurationRecorders"):
                return False, "AWS Config not configured"

            # Check if recorder is recording
            recorder_name = recorders["ConfigurationRecorders"][0]["name"]
            status = client.describe_configuration_recorder_status(
                ConfigurationRecorderNames=[recorder_name]
            )

            if status["ConfigurationRecordersStatus"][0]["recording"]:
                return True, f"AWS Config enabled: {recorder_name}"
            else:
                return False, "AWS Config configured but not recording"

        except ClientError as e:
            return False, f"Cannot check AWS Config: {e}"

    def run_all_checks(self) -> Dict[str, Tuple[bool, str]]:
        """Run all security baseline checks."""
        checks = {
            "CloudTrail": self.check_cloudtrail,
            "GuardDuty": self.check_guardduty,
            "Security Hub": self.check_security_hub,
            "IAM Access Analyzer": self.check_iam_access_analyzer,
            "S3 Block Public Access": self.check_s3_block_public_access,
            "EBS Encryption": self.check_ebs_encryption,
            "Root MFA": self.check_root_account_mfa,
            "Root Access Keys": self.check_root_access_keys,
            "Billing Alerts": self.check_billing_alerts,
            "AWS Config": self.check_config_enabled,
        }

        results = {}
        for check_name, check_func in checks.items():
            print(f"\n{'='*70}")
            print(f"CHECK: {check_name}")
            print(f"{'='*70}")

            try:
                passed, message = check_func()
                results[check_name] = (passed, message)

                if passed is True:
                    print(f"✅ PASS: {message}")
                elif passed is False:
                    print(f"❌ FAIL: {message}")
                else:  # None = warning/cannot determine
                    print(f"⚠️  WARNING: {message}")

            except Exception as e:
                results[check_name] = (False, f"Unexpected error: {e}")
                print(f"❌ ERROR: {e}")

        return results


def print_summary(results: Dict[str, Tuple[bool, str]]) -> int:
    """Print summary and return exit code."""
    print("\n" + "=" * 70)
    print("SECURITY BASELINE CHECK SUMMARY")
    print("=" * 70)

    passed = sum(1 for status, _ in results.values() if status is True)
    failed = sum(1 for status, _ in results.values() if status is False)
    warnings = sum(1 for status, _ in results.values() if status is None)
    total = len(results)

    print(f"\n✅ Passed:   {passed}/{total}")
    print(f"❌ Failed:   {failed}/{total}")
    print(f"⚠️  Warnings: {warnings}/{total}")

    print("\n" + "-" * 70)
    print("FAILED CHECKS:")
    print("-" * 70)

    for check_name, (status, message) in results.items():
        if status is False:
            print(f"❌ {check_name}: {message}")

    if warnings > 0:
        print("\n" + "-" * 70)
        print("WARNINGS:")
        print("-" * 70)

        for check_name, (status, message) in results.items():
            if status is None:
                print(f"⚠️  {check_name}: {message}")

    print("\n" + "=" * 70)

    if failed > 0:
        print("❌ SECURITY BASELINE CHECK FAILED")
        print("\n🚫 Cannot deploy Lateos to this AWS account until issues are resolved.")
        print("   See CLAUDE.md for AWS account setup requirements.")
        return 1
    elif warnings > 0:
        print("⚠️  SECURITY BASELINE CHECK PASSED WITH WARNINGS")
        print("\n⚠️  Some checks could not be verified. Review warnings above.")
        return 0
    else:
        print("✅ SECURITY BASELINE CHECK PASSED")
        print("\n🎉 AWS account meets all security requirements for Lateos deployment.")
        return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Verify AWS account security baseline for Lateos deployment"
    )
    parser.add_argument(
        "--profile",
        help="AWS CLI profile to use (default: default profile)",
        default=None,
    )
    parser.add_argument(
        "--region",
        help="AWS region to check (default: us-east-1)",
        default="us-east-1",
    )
    args = parser.parse_args()

    print("🔒 Lateos AWS Security Baseline Checker")
    print("=" * 70)
    print()

    checker = SecurityBaselineChecker(profile=args.profile, region=args.region)
    results = checker.run_all_checks()
    exit_code = print_summary(results)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
