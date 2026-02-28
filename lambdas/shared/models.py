"""
Data models for Lateos Lambda functions.

Uses Pydantic for type-safe data validation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class UserContext(BaseModel):
    """
    User context extracted from Cognito authorizer.

    Enforces RULE 6: user_id partition key isolation.
    """

    user_id: str = Field(..., description="Cognito user ID (sub claim)")
    email: Optional[str] = Field(None, description="User email address")
    username: Optional[str] = Field(None, description="Username")
    groups: List[str] = Field(default_factory=list, description="Cognito user groups")


class ValidationResult(BaseModel):
    """
    Result of input validation.

    Used by Validator Lambda.
    """

    is_valid: bool = Field(..., description="Whether input passed validation")
    sanitized_input: str = Field(..., description="Sanitized user input")
    warnings: List[str] = Field(
        default_factory=list, description="Non-blocking validation warnings"
    )
    blocked_reason: Optional[str] = Field(
        None, description="Reason for blocking (if is_valid=False)"
    )
    threat_indicators: List[str] = Field(
        default_factory=list, description="Detected threat patterns"
    )


class IntentClassification(BaseModel):
    """
    Classification of user intent.

    Used by Intent Classifier Lambda.
    """

    intent: str = Field(..., description="Primary intent (e.g., 'email', 'calendar', 'web_search')")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    entities: Dict[str, Any] = Field(
        default_factory=dict, description="Extracted entities from input"
    )
    suggested_action: Optional[str] = Field(None, description="Suggested action to execute")


class ActionRequest(BaseModel):
    """
    Request to execute a specific action/skill.

    Used by Action Router Lambda.
    """

    action_type: str = Field(..., description="Type of action (e.g., 'send_email', 'create_event')")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    user_context: UserContext = Field(..., description="User context for authorization")
    request_id: str = Field(..., description="Unique request ID for tracing")


class ActionResponse(BaseModel):
    """
    Response from action execution.

    Used by skill executors.
    """

    success: bool = Field(..., description="Whether action succeeded")
    result: Optional[Dict[str, Any]] = Field(None, description="Action result data")
    error: Optional[str] = Field(None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata (e.g., execution time)"
    )


class OrchestratorRequest(BaseModel):
    """
    Request to the orchestrator Lambda (entry point).

    Received from API Gateway.
    """

    user_input: str = Field(..., description="Raw user input text")
    user_context: UserContext = Field(..., description="User context from Cognito")
    request_id: str = Field(..., description="Unique request ID for tracing")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Request timestamp")


class OrchestratorResponse(BaseModel):
    """
    Response from the orchestrator Lambda.

    Returned to API Gateway.
    """

    response_text: str = Field(..., description="Response text for the user")
    success: bool = Field(..., description="Whether request succeeded")
    request_id: str = Field(..., description="Request ID for tracing")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
