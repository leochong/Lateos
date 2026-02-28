"""
Orchestrator Lambda

Entry point for all agent requests.
Routes requests through Step Functions workflow.

Flow:
1. Extract user context from API Gateway event
2. Create orchestration request
3. Invoke Step Functions workflow
4. Return response to API Gateway
"""

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger(service="orchestrator")
tracer = Tracer(service="orchestrator")

# Initialize AWS clients
sfn_client = boto3.client("stepfunctions")

# Get state machine ARN from environment
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN", "")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Orchestrator Lambda handler.

    Args:
        event: API Gateway proxy event
        context: Lambda context

    Returns:
        API Gateway proxy response
    """
    try:
        # Parse request body
        body = json.loads(event.get("body", "{}"))
        user_input = body.get("input", "")

        # Extract user context from authorizer (Cognito)
        authorizer = event.get("requestContext", {}).get("authorizer", {})
        claims = authorizer.get("claims", {})

        user_context = {
            "user_id": claims.get("sub", "unknown"),
            "email": claims.get("email"),
            "username": claims.get("cognito:username"),
        }

        # Generate request ID
        request_id = str(uuid.uuid4())

        logger.info(
            "Orchestrating request",
            extra={
                "request_id": request_id,
                "user_id": user_context["user_id"],
                "input_length": len(user_input),
            },
        )

        # For Phase 2, return placeholder response
        # Phase 3 will integrate with Step Functions
        response_text = (
            f"Lateos received your request: '{user_input[:50]}...' "
            f"(Request ID: {request_id}). "
            f"Full Step Functions integration coming in Phase 3."
        )

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(
                {
                    "response_text": response_text,
                    "success": True,
                    "request_id": request_id,
                    "metadata": {
                        "user_id": user_context["user_id"],
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                }
            ),
        }

    except Exception as e:
        logger.exception("Orchestration error", extra={"error": str(e)})
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "error": "Internal server error",
                    "message": str(e),
                }
            ),
        }
