#!/usr/bin/env python3
"""
End-to-end test for MCP handler lateos_email_summary tool.

This script tests the full chain:
1. MCP handler receives tools/call request
2. MCP handler invokes email_summary_skill Lambda
3. email_summary_skill fetches Gmail emails
4. email_summary_skill detects prompt injection
5. email_summary_skill summarizes with Bedrock
6. Response returns through MCP handler

Usage:
    python scripts/test_mcp_email_summary.py

Requirements:
    - AWS credentials configured (AWS_PROFILE=lateos-prod)
    - MCP handler Lambda deployed to AWS
    - email_summary_skill Lambda deployed to AWS
    - Gmail OAuth token stored in Secrets Manager
"""

import json
import sys

import boto3

# Initialize AWS clients
lambda_client = boto3.client("lambda", region_name="us-east-1")


def test_mcp_email_summary():
    """
    Test the MCP handler lateos_email_summary tool end-to-end.
    """
    print("\n" + "=" * 80)
    print("MCP EMAIL SUMMARY - END-TO-END TEST")
    print("=" * 80 + "\n")

    # Build MCP tools/call request
    mcp_request = {
        "jsonrpc": "2.0",
        "id": "test-123",
        "method": "tools/call",
        "params": {
            "name": "lateos_email_summary",
            "arguments": {
                "max_emails": 5,
            },
        },
    }

    # Wrap in API Gateway proxy event format
    api_gateway_event = {
        "body": json.dumps(mcp_request),
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "demo-user-001",  # Match the user in Secrets Manager
                    "email": "demo@example.com",
                    "cognito:username": "demo-user",
                }
            }
        },
    }

    print("MCP Request:")
    print(json.dumps(mcp_request, indent=2))
    print("\n" + "-" * 80 + "\n")

    try:
        # Invoke MCP handler Lambda
        print("Invoking MCP handler Lambda...")
        response = lambda_client.invoke(
            FunctionName="lateos-dev-mcp-handler",
            InvocationType="RequestResponse",
            Payload=json.dumps(api_gateway_event),
        )

        # Parse response
        lambda_response = json.loads(response["Payload"].read())

        print("Lambda Response:")
        print(json.dumps(lambda_response, indent=2, default=str))
        print("\n" + "-" * 80 + "\n")

        # Parse MCP response from body
        if "body" in lambda_response:
            payload = json.loads(lambda_response["body"])
            print("MCP Response:")
            print(json.dumps(payload, indent=2, default=str))
            print("\n" + "=" * 80 + "\n")
        else:
            payload = lambda_response

        # Check if successful
        if "result" in payload:
            result = payload["result"]

            # Extract summary from content
            if "content" in result and len(result["content"]) > 0:
                summary_text = result["content"][0].get("text", "")

                print("EMAIL SUMMARY:")
                print("-" * 80)
                print(summary_text)
                print("-" * 80 + "\n")

                print("✓ End-to-end test PASSED")
                print("  - MCP handler invoked successfully")
                print("  - email_summary_skill executed")
                print("  - Email summary returned")
                return True
            else:
                print("✗ End-to-end test FAILED: No content in result")
                return False
        elif "error" in payload:
            print(f"✗ End-to-end test FAILED: MCP error")
            print(f"  Code: {payload['error'].get('code')}")
            print(f"  Message: {payload['error'].get('message')}")
            if "data" in payload["error"]:
                print(f"  Data: {json.dumps(payload['error']['data'], indent=2)}")
            return False
        else:
            print("✗ End-to-end test FAILED: Unexpected response format")
            return False

    except Exception as e:
        print(f"✗ End-to-end test FAILED with exception:")
        print(f"  {type(e).__name__}: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """
    Run the end-to-end test.
    """
    success = test_mcp_email_summary()

    if success:
        print("\n✓ All tests passed! MCP → email_summary_skill → Bedrock chain working.\n")
        sys.exit(0)
    else:
        print("\n✗ Tests failed. Review output above.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
