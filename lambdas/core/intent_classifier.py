"""
Intent Classifier Lambda

Classifies user intent from sanitized input.
Phase 2: Rule-based classification
Phase 3: Will integrate with Amazon Bedrock for LLM-based classification

Supported intents:
- greeting: General greetings and pleasantries
- help: User requesting help or guidance
- email: Email-related requests
- calendar: Calendar/scheduling requests
- web_search: Web search requests
- general_query: General questions
- unknown: Cannot determine intent
"""

import re
from typing import Any, Dict, Tuple

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger(service="intent-classifier")
tracer = Tracer(service="intent-classifier")

# Intent patterns (simple keyword-based for Phase 2)
INTENT_PATTERNS = {
    "greeting": [
        r"\b(hello|hi|hey|greetings|good morning|good afternoon|good evening)\b",
    ],
    "help": [
        r"\b(help|assist|support|what can you do|how do i)\b",
    ],
    "email": [
        r"\b(email|send|message|compose|draft|mail)\b.*\b(to|recipient)\b",
        r"\b(send|write|compose)\b.*\b(email|message)\b",
    ],
    "calendar": [
        r"\b(schedule|calendar|meeting|appointment|event|remind)\b",
        r"\b(book|set up|create)\b.*\b(meeting|appointment)\b",
    ],
    "web_search": [
        r"\b(search|find|look up|google|what is|who is|where is)\b",
    ],
}


def classify_intent(text: str) -> Tuple[str, float, Dict[str, Any]]:
    """
    Classify user intent from input text.

    Args:
        text: Sanitized user input

    Returns:
        Tuple of (intent, confidence, entities)
    """
    text_lower = text.lower()

    # Check each intent pattern
    best_intent = "unknown"
    best_confidence = 0.0
    entities = {}

    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                # Simple confidence based on pattern match
                confidence = 0.8  # High confidence for direct pattern match
                if confidence > best_confidence:
                    best_intent = intent
                    best_confidence = confidence

    # If no pattern matched, classify as general_query if it's a question
    if best_intent == "unknown":
        if "?" in text or text_lower.startswith(("what", "who", "where", "when", "why", "how")):
            best_intent = "general_query"
            best_confidence = 0.6
        elif len(text.split()) < 5:
            # Short input without clear pattern
            best_intent = "unknown"
            best_confidence = 0.3

    # Extract basic entities (Phase 2 simple extraction)
    # Phase 3 will use Bedrock for entity extraction
    entities = extract_entities(text, best_intent)

    return best_intent, best_confidence, entities


def extract_entities(text: str, intent: str) -> Dict[str, Any]:
    """
    Extract entities from text based on intent.

    Args:
        text: User input text
        intent: Classified intent

    Returns:
        Dictionary of extracted entities
    """
    entities = {}

    if intent == "email":
        # Extract email addresses
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        emails = re.findall(email_pattern, text)
        if emails:
            entities["recipients"] = emails

    elif intent == "calendar":
        # Extract date/time references (simple for Phase 2)
        date_keywords = [
            "today",
            "tomorrow",
            "next week",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]
        for keyword in date_keywords:
            if keyword in text.lower():
                entities["time_reference"] = keyword
                break

        # Extract time patterns (HH:MM or HH AM/PM)
        time_pattern = r"\b\d{1,2}:\d{2}\b|\b\d{1,2}\s*(am|pm)\b"
        times = re.findall(time_pattern, text.lower())
        if times:
            entities["time"] = times[0]

    return entities


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Intent Classifier Lambda handler.

    Args:
        event: Contains sanitized input from validator
        context: Lambda context

    Returns:
        Intent classification result
    """
    try:
        # Extract sanitized input
        sanitized_input = event.get("sanitized_input", "")
        request_id = event.get("request_id", "unknown")

        logger.info(
            "Classifying intent",
            extra={
                "request_id": request_id,
                "input_length": len(sanitized_input),
            },
        )

        # Classify intent
        intent, confidence, entities = classify_intent(sanitized_input)

        # Determine suggested action based on intent
        suggested_action = None
        if intent == "email":
            suggested_action = "send_email"
        elif intent == "calendar":
            suggested_action = "create_calendar_event"
        elif intent == "web_search":
            suggested_action = "web_search"
        elif intent == "greeting":
            suggested_action = "respond_greeting"
        elif intent == "help":
            suggested_action = "show_help"

        logger.info(
            "Intent classified",
            extra={
                "intent": intent,
                "confidence": confidence,
                "suggested_action": suggested_action,
                "entity_count": len(entities),
            },
        )

        return {
            "statusCode": 200,
            "intent": intent,
            "confidence": confidence,
            "entities": entities,
            "suggested_action": suggested_action,
            "request_id": request_id,
        }

    except Exception as e:
        logger.exception("Intent classification error", extra={"error": str(e)})
        return {
            "statusCode": 500,
            "intent": "unknown",
            "confidence": 0.0,
            "entities": {},
            "suggested_action": None,
            "error": str(e),
        }
