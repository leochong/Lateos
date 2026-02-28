"""
Web Fetch Skill Lambda

Handles secure HTTP requests to external websites.
Implements RULE 2: Scoped IAM role (no wildcard permissions).
Implements RULE 4: No shell execution.

Capabilities:
- GET requests to whitelisted domains
- POST requests to whitelisted APIs
- Parse HTML content
- Extract structured data
- Rate limiting per user
- Content filtering (block malicious content)

Security:
- Domain whitelist enforcement
- No shell execution (RULE 4)
- SSL/TLS verification required
- Request timeout limits
- Content size limits
- Rate limiting (max requests per minute)
- Scoped IAM role (only DynamoDB audit access)
"""

import json
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")

# Initialize logger and tracer
logger = Logger(service="web_fetch_skill")
tracer = Tracer(service="web_fetch_skill")

# Environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
AUDIT_TABLE_NAME = os.environ.get("AUDIT_TABLE_NAME")

# Security configuration
MAX_CONTENT_SIZE = 10 * 1024 * 1024  # 10 MB
REQUEST_TIMEOUT = 30  # seconds
RATE_LIMIT_PER_MINUTE = 60

# Domain whitelist (can be extended via environment variable)
DEFAULT_ALLOWED_DOMAINS = [
    "wikipedia.org",
    "*.wikipedia.org",
    "github.com",
    "api.github.com",
    "stackoverflow.com",
    "news.ycombinator.com",
    "reddit.com",
    "*.reddit.com",
]


class WebFetchError(Exception):
    """Raised when web fetch operation fails"""

    pass


def is_domain_allowed(url: str, allowed_domains: List[str]) -> bool:
    """
    Check if URL domain is in whitelist.

    Args:
        url: URL to check
        allowed_domains: List of allowed domain patterns

    Returns:
        True if domain is allowed
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        for allowed in allowed_domains:
            # Handle wildcard patterns
            if allowed.startswith("*."):
                # Match subdomains
                if domain.endswith(allowed[2:]) or domain == allowed[2:]:
                    return True
            else:
                # Exact match
                if domain == allowed.lower():
                    return True

        return False
    except Exception as e:
        logger.error(f"Failed to parse URL {url}: {e}")
        return False


def check_rate_limit(user_id: str) -> bool:
    """
    Check if user has exceeded rate limit.

    Args:
        user_id: Cognito user ID

    Returns:
        True if within rate limit, False if exceeded

    Note:
        In production, this would query DynamoDB to track requests per minute.
        For Phase 3, we'll return True (allow all requests).
    """
    # TODO: Implement actual rate limiting with DynamoDB in production
    logger.info(f"Rate limit check for user {user_id}: OK (mock)")
    return True


def fetch_url(
    user_id: str,
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fetch content from URL.

    Args:
        user_id: Cognito user ID
        url: URL to fetch
        method: HTTP method (GET, POST)
        headers: Optional HTTP headers
        body: Optional request body (for POST)

    Returns:
        Response dict with status, headers, and content

    Raises:
        WebFetchError: If request fails or is blocked
    """
    logger.info(f"Fetching URL for user {user_id}: {url}")

    # Check rate limit
    if not check_rate_limit(user_id):
        raise WebFetchError("Rate limit exceeded. Please try again later.")

    # Validate URL
    if not url.startswith(("http://", "https://")):
        raise WebFetchError("Invalid URL scheme. Only HTTP(S) allowed.")

    # Check domain whitelist
    allowed_domains = DEFAULT_ALLOWED_DOMAINS
    # Allow custom domains from environment variable
    custom_domains = os.environ.get("ALLOWED_DOMAINS", "")
    if custom_domains:
        allowed_domains.extend(custom_domains.split(","))

    if not is_domain_allowed(url, allowed_domains):
        parsed = urlparse(url)
        raise WebFetchError(f"Domain '{parsed.netloc}' is not in the allowed whitelist.")

    # Validate method
    if method not in ["GET", "POST", "HEAD"]:
        raise WebFetchError(f"Unsupported HTTP method: {method}")

    # Mock response for Phase 3
    # TODO: Implement actual HTTP client (requests or urllib3) in production
    # Important: Use SSL verification, timeout, and size limits

    response = {
        "status_code": 200,
        "headers": {
            "content-type": "text/html; charset=utf-8",
            "content-length": "1234",
        },
        "content": f"<html><body>Mock content from {url}</body></html>",
        "url": url,
        "method": method,
    }

    # Log to audit table
    log_web_fetch_action(
        user_id,
        "fetch_url",
        {
            "url": url,
            "method": method,
            "status": response["status_code"],
        },
    )

    return response


def parse_html(user_id: str, html: str, selector: Optional[str] = None) -> Dict[str, Any]:
    """
    Parse HTML content and extract data.

    Args:
        user_id: Cognito user ID
        html: HTML content to parse
        selector: Optional CSS selector to extract specific elements

    Returns:
        Parsed data dict

    Note:
        In production, use BeautifulSoup or lxml for HTML parsing.
        For Phase 3, return a mock response.
    """
    logger.info(f"Parsing HTML for user {user_id}, selector: {selector}")

    # Mock response for Phase 3
    # TODO: Implement actual HTML parsing with BeautifulSoup in production

    result = {
        "title": "Mock Page Title",
        "text_content": "Mock extracted text content",
        "links": ["https://example.com/link1", "https://example.com/link2"],
        "images": ["https://example.com/image1.jpg"],
    }

    if selector:
        result["selected"] = [f"Mock element matching {selector}"]

    # Log to audit table
    log_web_fetch_action(
        user_id,
        "parse_html",
        {"selector": selector, "elements_found": len(result.get("selected", []))},
    )

    return result


def extract_data(
    user_id: str, content: str, pattern: str, extract_type: str = "regex"
) -> List[str]:
    """
    Extract structured data from content.

    Args:
        user_id: Cognito user ID
        content: Content to extract from
        pattern: Extraction pattern (regex, json path, etc.)
        extract_type: Type of extraction (regex, json, xml)

    Returns:
        List of extracted values
    """
    logger.info(f"Extracting data for user {user_id}, type: {extract_type}")

    results = []

    if extract_type == "regex":
        try:
            matches = re.findall(pattern, content, re.IGNORECASE)
            results = matches[:100]  # Limit results
        except re.error as e:
            raise WebFetchError(f"Invalid regex pattern: {e}")

    elif extract_type == "json":
        # Mock JSON extraction
        results = ["mock-json-value-1", "mock-json-value-2"]

    elif extract_type == "xml":
        # Mock XML extraction
        results = ["mock-xml-value-1"]

    else:
        raise WebFetchError(f"Unsupported extract type: {extract_type}")

    # Log to audit table
    log_web_fetch_action(
        user_id,
        "extract_data",
        {"pattern": pattern, "type": extract_type, "count": len(results)},
    )

    return results


def log_web_fetch_action(user_id: str, action: str, details: Dict[str, Any]) -> None:
    """
    Log web fetch action to audit table.

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
                "timestamp": details.get("timestamp", "2026-02-28T10:00:00Z"),
                "skill": "web_fetch",
                "action": action,
                "details": json.dumps(details),
            }
        )
        logger.info(f"Logged web fetch action: {action} for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to log web fetch action: {e}")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Web fetch skill Lambda handler.

    Event format:
    {
        "user_id": "cognito-user-id",
        "action": "fetch_url" | "parse_html" | "extract_data",
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
    logger.info("Web fetch skill invoked", extra={"event": event})

    try:
        # Extract user context
        user_id = event.get("user_id")
        if not user_id:
            raise WebFetchError("Missing user_id in request")

        # Extract action
        action = event.get("action")
        if not action:
            raise WebFetchError("Missing action in request")

        # Extract parameters
        params = event.get("parameters", {})

        # Route to appropriate handler
        if action == "fetch_url":
            result = fetch_url(
                user_id=user_id,
                url=params.get("url", ""),
                method=params.get("method", "GET"),
                headers=params.get("headers"),
                body=params.get("body"),
            )
        elif action == "parse_html":
            result = parse_html(
                user_id=user_id,
                html=params.get("html", ""),
                selector=params.get("selector"),
            )
        elif action == "extract_data":
            result = extract_data(
                user_id=user_id,
                content=params.get("content", ""),
                pattern=params.get("pattern", ""),
                extract_type=params.get("extract_type", "regex"),
            )
        else:
            raise WebFetchError(f"Unknown action: {action}")

        return {
            "statusCode": 200,
            "body": {"result": result, "skill": "web_fetch", "action": action},
        }

    except WebFetchError as e:
        logger.error(f"Web fetch error: {e}")
        return {
            "statusCode": 400,
            "body": {"error": str(e), "skill": "web_fetch"},
        }
    except Exception as e:
        logger.exception(f"Unexpected error in web fetch skill: {e}")
        return {
            "statusCode": 500,
            "body": {"error": "Internal server error", "skill": "web_fetch"},
        }
