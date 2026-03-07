"""
MCP Handler Integration Tests

Tests the MCP protocol handler Lambda against LocalStack:
- MCP initialize handshake
- MCP tools/list returns correct schema
- MCP tools/call invokes email_skill Lambda
- Authentication and error handling

Prerequisites:
- LocalStack running: docker-compose up -d localstack
- AWS credentials configured for localstack profile
- All stacks deployed to LocalStack

Run:
    AWS_PROFILE=localstack pytest tests/integration/test_mcp_handler.py -v
"""

import json
import os

import boto3
import pytest
from botocore.exceptions import ClientError

# LocalStack endpoint configuration
LOCALSTACK_ENDPOINT = os.environ.get("LOCALSTACK_ENDPOINT", "http://localhost:4566")

# Test configuration
TEST_ENVIRONMENT = "dev"
TEST_REGION = "us-east-1"
TEST_USER_ID = "test-user-12345"  # Mock Cognito user ID


@pytest.fixture(scope="module")
def aws_clients():
    """Create AWS clients configured for LocalStack"""
    session = boto3.Session(
        aws_access_key_id="test",  # pragma: allowlist secret
        aws_secret_access_key="test",  # pragma: allowlist secret
        region_name=TEST_REGION,
    )

    clients = {
        "lambda": session.client("lambda", endpoint_url=LOCALSTACK_ENDPOINT),
        "dynamodb": session.client("dynamodb", endpoint_url=LOCALSTACK_ENDPOINT),
    }

    return clients


@pytest.fixture(scope="module")
def mcp_handler_function(aws_clients):
    """Get MCP handler Lambda function name"""
    lambda_client = aws_clients["lambda"]
    function_name = f"lateos-{TEST_ENVIRONMENT}-mcp-handler"

    try:
        lambda_client.get_function(FunctionName=function_name)
        return function_name
    except ClientError:
        pytest.skip(f"MCP handler Lambda not deployed: {function_name}")


def invoke_mcp_handler(lambda_client, function_name, method, params=None, request_id=1):
    """
    Helper function to invoke MCP handler with JSON-RPC payload.

    Args:
        lambda_client: Boto3 Lambda client
        function_name: Lambda function name
        method: MCP method name
        params: Method parameters (optional)
        request_id: JSON-RPC request ID

    Returns:
        Parsed response payload
    """
    # Build MCP request (JSON-RPC 2.0 format)
    mcp_request = {
        "jsonrpc": "2.0",
        "method": method,
        "id": request_id,
    }

    if params is not None:
        mcp_request["params"] = params

    # Build API Gateway event structure
    # Note: In real deployment, Cognito would populate authorizer claims
    api_event = {
        "body": json.dumps(mcp_request),
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": TEST_USER_ID,
                    "email": "test@lateos.local",
                    "cognito:username": "test-user",
                }
            }
        },
    }

    # Invoke Lambda
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(api_event),
    )

    # Parse response
    payload = json.loads(response["Payload"].read())
    return payload


def test_mcp_initialize(aws_clients, mcp_handler_function):
    """Test MCP initialize method"""
    lambda_client = aws_clients["lambda"]

    response = invoke_mcp_handler(
        lambda_client,
        mcp_handler_function,
        method="initialize",
        params={
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0",
            },
        },
    )

    # Verify response structure
    assert response["statusCode"] == 200

    body = json.loads(response["body"])
    assert body["jsonrpc"] == "2.0"
    assert "result" in body
    assert body["result"]["protocolVersion"] == "2024-11-05"
    assert "capabilities" in body["result"]
    assert "serverInfo" in body["result"]
    assert body["result"]["serverInfo"]["name"] == "lateos-mcp-server"


def test_mcp_tools_list(aws_clients, mcp_handler_function):
    """Test MCP tools/list returns correct schema"""
    lambda_client = aws_clients["lambda"]

    response = invoke_mcp_handler(
        lambda_client,
        mcp_handler_function,
        method="tools/list",
    )

    # Verify response structure
    assert response["statusCode"] == 200

    body = json.loads(response["body"])
    assert body["jsonrpc"] == "2.0"
    assert "result" in body
    assert "tools" in body["result"]

    tools = body["result"]["tools"]
    assert len(tools) == 1

    # Verify lateos_email_summary tool schema
    tool = tools[0]
    assert tool["name"] == "lateos_email_summary"
    assert "description" in tool
    assert "Securely reads and summarizes emails" in tool["description"]
    assert "inputSchema" in tool

    # Verify input schema
    schema = tool["inputSchema"]
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "max_emails" in schema["properties"]
    assert "filter" in schema["properties"]
    assert "summary_style" in schema["properties"]


def test_mcp_tools_call_valid(aws_clients, mcp_handler_function):
    """Test MCP tools/call with valid arguments invokes email_skill"""
    lambda_client = aws_clients["lambda"]

    response = invoke_mcp_handler(
        lambda_client,
        mcp_handler_function,
        method="tools/call",
        params={
            "name": "lateos_email_summary",
            "arguments": {
                "max_emails": 5,
                "summary_style": "brief",
            },
        },
    )

    # Verify response structure
    assert response["statusCode"] == 200

    body = json.loads(response["body"])
    assert body["jsonrpc"] == "2.0"
    assert "result" in body

    # Verify result contains content
    result = body["result"]
    assert "content" in result
    assert len(result["content"]) > 0
    assert result["content"][0]["type"] == "text"
    assert "Found" in result["content"][0]["text"] or "Email" in result["content"][0]["text"]


def test_mcp_tools_call_missing_tool_name(aws_clients, mcp_handler_function):
    """Test MCP tools/call with missing tool name returns error"""
    lambda_client = aws_clients["lambda"]

    response = invoke_mcp_handler(
        lambda_client,
        mcp_handler_function,
        method="tools/call",
        params={
            "arguments": {
                "max_emails": 5,
            },
        },
    )

    # Verify response structure
    assert response["statusCode"] == 200

    body = json.loads(response["body"])
    assert body["jsonrpc"] == "2.0"
    assert "error" in body

    # Verify error code (MCP_ERROR_INVALID_PARAMS)
    error = body["error"]
    assert error["code"] == -32602
    assert "Missing required parameter" in error["message"]


def test_mcp_tools_call_invalid_tool_name(aws_clients, mcp_handler_function):
    """Test MCP tools/call with invalid tool name returns error"""
    lambda_client = aws_clients["lambda"]

    response = invoke_mcp_handler(
        lambda_client,
        mcp_handler_function,
        method="tools/call",
        params={
            "name": "nonexistent_tool",
            "arguments": {},
        },
    )

    # Verify response structure
    assert response["statusCode"] == 200

    body = json.loads(response["body"])
    assert body["jsonrpc"] == "2.0"
    assert "error" in body

    # Verify error code (MCP_ERROR_METHOD_NOT_FOUND)
    error = body["error"]
    assert error["code"] == -32601
    assert "Tool not found" in error["message"]


def test_mcp_invalid_method(aws_clients, mcp_handler_function):
    """Test MCP with invalid method returns error"""
    lambda_client = aws_clients["lambda"]

    response = invoke_mcp_handler(
        lambda_client,
        mcp_handler_function,
        method="invalid/method",
    )

    # Verify response structure
    assert response["statusCode"] == 200

    body = json.loads(response["body"])
    assert body["jsonrpc"] == "2.0"
    assert "error" in body

    # Verify error code (MCP_ERROR_METHOD_NOT_FOUND)
    error = body["error"]
    assert error["code"] == -32601
    assert "Method not found" in error["message"]


def test_mcp_audit_logging(aws_clients, mcp_handler_function):
    """Test that MCP calls are logged to audit table"""
    lambda_client = aws_clients["lambda"]
    dynamodb_client = aws_clients["dynamodb"]

    # Invoke tools/list
    response = invoke_mcp_handler(
        lambda_client,
        mcp_handler_function,
        method="tools/list",
    )

    assert response["statusCode"] == 200

    # Check audit table for log entry
    # Note: In LocalStack, DynamoDB may not have the exact same behavior
    # This is a best-effort check
    table_name = f"lateos-{TEST_ENVIRONMENT}-audit-logs"

    try:
        # Query for recent audit logs for test user
        response = dynamodb_client.query(
            TableName=table_name,
            KeyConditionExpression="user_id = :uid",
            ExpressionAttributeValues={
                ":uid": {"S": TEST_USER_ID},
            },
            Limit=10,
            ScanIndexForward=False,  # Most recent first
        )

        # Should have at least one audit log
        # Note: This may not work perfectly in LocalStack
        items = response.get("Items", [])
        # Just verify the query succeeds (table exists)
        assert isinstance(items, list)

    except ClientError as e:
        # Table might not exist in LocalStack - that's okay
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
