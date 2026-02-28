"""
Calendar Skill Lambda

Handles calendar operations via Google Calendar API with OAuth 2.0.
Implements RULE 1: All secrets via Secrets Manager.
Implements RULE 2: Scoped IAM role (no wildcard permissions).

Capabilities:
- Create events
- List events (today, week, month, custom range)
- Update events
- Delete events
- Search events by query
- Check availability

Security:
- OAuth 2.0 tokens stored in Secrets Manager
- Per-user token isolation (user_id in secret path)
- No access to other skills' secrets
- Scoped IAM role (only Google Calendar OAuth secret and DynamoDB audit)
"""

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize AWS clients
secrets_manager = boto3.client("secretsmanager")
dynamodb = boto3.resource("dynamodb")

# Initialize logger and tracer
logger = Logger(service="calendar_skill")
tracer = Tracer(service="calendar_skill")

# Environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
AUDIT_TABLE_NAME = os.environ.get("AUDIT_TABLE_NAME")


class CalendarSkillError(Exception):
    """Raised when calendar skill operation fails"""

    pass


def get_calendar_credentials(user_id: str) -> Dict[str, Any]:
    """
    Retrieve Google Calendar OAuth credentials from Secrets Manager.

    Args:
        user_id: Cognito user ID for secret isolation

    Returns:
        Google Calendar OAuth credentials dict

    Raises:
        CalendarSkillError: If credentials cannot be retrieved
    """
    secret_name = f"lateos/{ENVIRONMENT}/google_calendar/{user_id}"

    try:
        response = secrets_manager.get_secret_value(SecretId=secret_name)
        return json.loads(response["SecretString"])
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ResourceNotFoundException":
            logger.warning(f"Calendar credentials not found for user {user_id}")
            raise CalendarSkillError(
                "Google Calendar not connected. Please authorize Google Calendar first."
            )
        else:
            logger.error(f"Failed to retrieve Calendar credentials: {e}")
            raise CalendarSkillError("Failed to access Google Calendar credentials")


def create_event(
    user_id: str,
    title: str,
    start_time: str,
    end_time: str,
    description: Optional[str] = None,
    attendees: Optional[List[str]] = None,
    location: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a calendar event.

    Args:
        user_id: Cognito user ID
        title: Event title
        start_time: Start time (ISO 8601 format)
        end_time: End time (ISO 8601 format)
        description: Optional event description
        attendees: Optional list of attendee emails
        location: Optional event location

    Returns:
        Created event dict with event_id
    """
    logger.info(f"Creating calendar event for user {user_id}: {title}")

    # Get OAuth credentials
    credentials = get_calendar_credentials(user_id)  # noqa: F841

    # Mock response for Phase 3
    # TODO: Implement actual Google Calendar API integration in production
    event = {
        "event_id": f"mock-event-{hash(title)}",
        "title": title,
        "start_time": start_time,
        "end_time": end_time,
        "description": description,
        "attendees": attendees or [],
        "location": location,
        "status": "confirmed",
    }

    # Log to audit table
    log_calendar_action(user_id, "create_event", event)

    return event


def list_events(
    user_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    List calendar events.

    Args:
        user_id: Cognito user ID
        start_date: Start date (ISO 8601), defaults to today
        end_date: End date (ISO 8601), defaults to 7 days from now
        limit: Maximum number of events (max 50)

    Returns:
        List of event dicts
    """
    logger.info(f"Listing calendar events for user {user_id}")

    # Enforce limit
    if limit > 50:
        limit = 50

    # Get OAuth credentials
    credentials = get_calendar_credentials(user_id)  # noqa: F841

    # Default date range if not provided
    if not start_date:
        start_date = datetime.now().isoformat()
    if not end_date:
        end_date = (datetime.now() + timedelta(days=7)).isoformat()

    # Mock response for Phase 3
    events = [
        {
            "event_id": f"mock-event-{i}",
            "title": f"Meeting {i}",
            "start_time": start_date,
            "end_time": start_date,
            "description": "Mock event for testing",
            "attendees": ["attendee@example.com"],
            "location": "Conference Room A",
        }
        for i in range(min(limit, 5))
    ]

    # Log to audit table
    log_calendar_action(user_id, "list_events", {"start_date": start_date, "count": len(events)})

    return events


def update_event(
    user_id: str,
    event_id: str,
    updates: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Update a calendar event.

    Args:
        user_id: Cognito user ID
        event_id: Event ID to update
        updates: Dict of fields to update

    Returns:
        Updated event dict
    """
    logger.info(f"Updating calendar event {event_id} for user {user_id}")

    # Get OAuth credentials
    credentials = get_calendar_credentials(user_id)  # noqa: F841

    # Mock response for Phase 3
    event = {
        "event_id": event_id,
        "title": updates.get("title", "Updated Event"),
        "start_time": updates.get("start_time", datetime.now().isoformat()),
        "end_time": updates.get("end_time", datetime.now().isoformat()),
        "status": "confirmed",
    }

    # Log to audit table
    log_calendar_action(user_id, "update_event", {"event_id": event_id, **updates})

    return event


def delete_event(user_id: str, event_id: str) -> Dict[str, Any]:
    """
    Delete a calendar event.

    Args:
        user_id: Cognito user ID
        event_id: Event ID to delete

    Returns:
        Deletion confirmation dict
    """
    logger.info(f"Deleting calendar event {event_id} for user {user_id}")

    # Get OAuth credentials
    credentials = get_calendar_credentials(user_id)  # noqa: F841

    # Mock response for Phase 3
    result = {
        "event_id": event_id,
        "status": "deleted",
    }

    # Log to audit table
    log_calendar_action(user_id, "delete_event", {"event_id": event_id})

    return result


def search_events(user_id: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search calendar events by query.

    Args:
        user_id: Cognito user ID
        query: Search query
        limit: Maximum number of results (max 50)

    Returns:
        List of matching event dicts
    """
    logger.info(f"Searching calendar events for user {user_id} with query: {query}")

    # Enforce limit
    if limit > 50:
        limit = 50

    # Get OAuth credentials
    credentials = get_calendar_credentials(user_id)  # noqa: F841

    # Mock response for Phase 3
    results = [
        {
            "event_id": f"mock-search-{i}",
            "title": f"Match: {query}",
            "start_time": datetime.now().isoformat(),
            "end_time": datetime.now().isoformat(),
        }
        for i in range(min(limit, 3))
    ]

    # Log to audit table
    log_calendar_action(user_id, "search_events", {"query": query, "count": len(results)})

    return results


def log_calendar_action(user_id: str, action: str, details: Dict[str, Any]) -> None:
    """
    Log calendar action to audit table.

    Args:
        user_id: Cognito user ID
        action: Action name
        details: Action details dict
    """
    if not AUDIT_TABLE_NAME:
        logger.warning("Audit table not configured, skipping audit log")
        return

    try:
        table = dynamodb.Table(AUDIT_TABLE_NAME)
        table.put_item(
            Item={
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
                "skill": "calendar",
                "action": action,
                "details": json.dumps(details),
            }
        )
        logger.info(f"Logged calendar action: {action} for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to log calendar action: {e}")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Calendar skill Lambda handler.

    Event format:
    {
        "user_id": "cognito-user-id",
        "action": "create_event" | "list_events" | "update_event" |
                  "delete_event" | "search_events",
        "parameters": {
            # Action-specific parameters
        }
    }

    Returns:
        {
            "statusCode": 200,
            "body": {
                "result": <action result>
            }
        }
    """
    logger.info("Calendar skill invoked", extra={"event": event})

    try:
        # Extract user context
        user_id = event.get("user_id")
        if not user_id:
            raise CalendarSkillError("Missing user_id in request")

        # Extract action
        action = event.get("action")
        if not action:
            raise CalendarSkillError("Missing action in request")

        # Extract parameters
        params = event.get("parameters", {})

        # Route to appropriate handler
        if action == "create_event":
            result = create_event(
                user_id=user_id,
                title=params.get("title", ""),
                start_time=params.get("start_time", ""),
                end_time=params.get("end_time", ""),
                description=params.get("description"),
                attendees=params.get("attendees"),
                location=params.get("location"),
            )
        elif action == "list_events":
            result = list_events(
                user_id=user_id,
                start_date=params.get("start_date"),
                end_date=params.get("end_date"),
                limit=params.get("limit", 10),
            )
        elif action == "update_event":
            result = update_event(
                user_id=user_id,
                event_id=params.get("event_id", ""),
                updates=params.get("updates", {}),
            )
        elif action == "delete_event":
            result = delete_event(
                user_id=user_id,
                event_id=params.get("event_id", ""),
            )
        elif action == "search_events":
            result = search_events(
                user_id=user_id,
                query=params.get("query", ""),
                limit=params.get("limit", 10),
            )
        else:
            raise CalendarSkillError(f"Unknown action: {action}")

        return {
            "statusCode": 200,
            "body": {"result": result, "skill": "calendar", "action": action},
        }

    except CalendarSkillError as e:
        logger.error(f"Calendar skill error: {e}")
        return {
            "statusCode": 400,
            "body": {"error": str(e), "skill": "calendar"},
        }
    except Exception as e:
        logger.exception(f"Unexpected error in calendar skill: {e}")
        return {
            "statusCode": 500,
            "body": {"error": "Internal server error", "skill": "calendar"},
        }
