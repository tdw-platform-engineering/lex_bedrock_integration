"""
Lex V2 handler — extracts data from the Lex event, delegates to the
selected agent backend, and formats the Lex V2 fulfillment response.

Ported from ``lex-bedrock-agent-integration/src/handlers/lex-handler.mjs``.
"""

import json
import logging
import time
from datetime import datetime, timezone

from src.modules.services.base_agent import BaseAgentService, create_agent_service
from src.modules.services.customer_profiles import CustomerProfilesService
from src.modules.utils.config import Config

logger = logging.getLogger(__name__)


class LexHandler:
    """Processes Amazon Lex V2 fulfillment events through an AI agent."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self.agent_service: BaseAgentService = create_agent_service(
            self.config.agent_provider
        )
        self.customer_profiles_service = CustomerProfilesService(self.config)
        logger.info("Using agent provider: %s", self.config.agent_provider)

    # ------------------------------------------------------------------
    # 1. Extract Lex data
    # ------------------------------------------------------------------
    def extract_lex_data(self, event: dict) -> dict:
        """
        Parse a Lex V2 event into a structured ``lex_context`` dict.

        Returns a dict with keys: ``intent``, ``userInput``,
        ``originalUtterance``, ``slots``, ``conversationHistory``.
        """
        session_state = event.get("sessionState", {})
        intent_data = session_state.get("intent", {})
        slots_data = intent_data.get("slots") or {}

        lex_context: dict = {
            "intent": intent_data.get("name", ""),
            "userInput": event.get("inputTranscript", ""),
            "originalUtterance": event.get("inputTranscript", ""),
            "slots": {},
            "conversationHistory": self.extract_conversation_history(event),
        }

        # Extract slot values dynamically
        for slot_name, slot_obj in slots_data.items():
            if slot_obj and isinstance(slot_obj, dict):
                original_value = (
                    slot_obj.get("value", {}).get("originalValue")
                    if slot_obj.get("value")
                    else None
                )
                if original_value:
                    lex_context["slots"][slot_name] = original_value

        return lex_context

    # ------------------------------------------------------------------
    # Conversation history
    # ------------------------------------------------------------------
    def extract_conversation_history(self, event: dict) -> dict:
        """Build a conversation history dict from the Lex event."""
        session_attrs = event.get("sessionState", {}).get(
            "sessionAttributes", {}
        )

        # Resolve session / contact ID
        incoming_contact_id = str(session_attrs.get("contactId", "")).strip()
        incoming_session_id = str(event.get("sessionId", "")).strip()

        if incoming_contact_id and incoming_contact_id.lower() != "unknown":
            resolved_session_id = incoming_contact_id
        elif incoming_session_id and incoming_session_id.lower() != "unknown":
            resolved_session_id = incoming_session_id
        else:
            resolved_session_id = f"lex-{int(time.time() * 1000)}"

        return {
            "sessionId": resolved_session_id,
            "sessionAttributes": session_attrs,
            "requestAttributes": event.get("requestAttributes", {}),
            "previousMessages": [],
            "currentTurn": {
                "userInput": event.get("inputTranscript", ""),
                "intent": event.get("sessionState", {})
                .get("intent", {})
                .get("name", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    # ------------------------------------------------------------------
    # 2. Process with agent
    # ------------------------------------------------------------------
    def process_with_bedrock_agent(self, lex_data: dict, event: dict) -> dict:
        """Build the prompt and send it to the configured agent backend."""
        logger.debug(
            "Datos extraídos de Lex: %s",
            json.dumps(lex_data, default=str),
        )

        agent_input = self.build_agent_input(lex_data)
        logger.debug("Input construido para agente:\n%s", agent_input)

        response = self.agent_service.process_with_agent(agent_input, lex_data, event)

        logger.debug("Respuesta estructurada recibida: %s", response.get("txt", "")[:200])
        return responseg("Respuesta estructurada recibida: %s", response.get("txt", "")[:200])

    # ------------------------------------------------------------------
    # 3. Build agent input text
    # ------------------------------------------------------------------
    def build_agent_input(self, lex_data: dict) -> str:
        """Construct the structured text prompt for the agent."""
        parts = [
            f"Cliente: {lex_data.get('originalUtterance', '')}"
        ]

        slots = lex_data.get("slots", {})
        if slots:
            parts.append("Parámetros:")
            for key, value in slots.items():
                parts.append(f"- {key}: {value}")

        return "\n".join(parts) + "\n"


    @staticmethod
    def _coerce_to_bool(value: object) -> bool:
        """Normalize bool-like values that may come from JSON payloads."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "si", "sí"}
        if isinstance(value, (int, float)):
            return value == 1
        return False

    def format_lex_response(
        self,
        original_event: dict,
        agent_response: dict,
        lex_data: dict,
    ) -> dict:
        """
        Build the Lex V2 fulfillment response from the structured agent
        response dict: ``{"txt": "...", "end": bool, "st": ..., ...}``.
        """
        cleaned_response = agent_response.get("txt", "")
        should_end_call = self._coerce_to_bool(agent_response.get("end"))

        logger.debug(
            "Structured agent response: end=%s, st=%s, amount=%s, date=%s",
            agent_response.get("end"),
            agent_response.get("st"),
            agent_response.get("amount"),
            agent_response.get("date"),
        )

        intent_state = "Fulfilled" if should_end_call else "Failed"
        completed = "true" if intent_state == "Fulfilled" else "false"

        # Build Lex V2 response
        session_attrs = dict(
            original_event.get("sessionState", {}).get("sessionAttributes", {})
        )
        session_attrs["COMPLETED"] = completed

        intent_name = (
            original_event.get("sessionState", {})
            .get("intent", {})
            .get("name", "Unknown")
        )

        return {
            "sessionState": {
                "dialogAction": {
                    "type": "Close" if intent_state == "Fulfilled" else "ElicitIntent",
                },
                "intent": {
                    "name": intent_name,
                    "state": (
                        "Fulfilled" if intent_state == "Fulfilled" else "InProgress"
                    ),
                },
                "sessionAttributes": session_attrs,
            },
            "messages": [
                {
                    "contentType": "PlainText",
                    "content": cleaned_response,
                }
            ],
        }
