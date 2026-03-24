"""
EC2 Agent service — sends requests to an HTTP endpoint running on
an EC2 instance (or any HTTP server conforming to the same contract).
"""

import json
import logging
import time

import requests

from src.modules.services.base_agent import BaseAgentService
from src.modules.utils.config import Config

logger = logging.getLogger(__name__)


class Ec2AgentService(BaseAgentService):
    """Calls an HTTP agent endpoint via POST ``/chat``."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self.endpoint = self.config.agent_http_url
        self.timeout_s = self.config.agent_http_timeout_ms / 1000

    def process_with_agent(self, user_input: str, context: dict, event: dict) -> dict:
        # Resolve session ID via sessionState.sessionAttributes.contactId or sessionId
        raw_session_id = context.get("conversationHistory", {}).get("sessionId", "")
        session_attributes = context.get("conversationHistory", {}).get("sessionAttributes", {})
        print("Session attributes:", {"message": user_input, "sessionId": raw_session_id, "sessionAttributes": session_attributes})
        logger.info(
            "Calling EC2 agent: endpoint=%s, session=%s, timeout=%ss",
            self.endpoint,
            raw_session_id,
            self.timeout_s,
        )

        response = requests.post(
            self.endpoint,
            json={"message": user_input, "sessionId": raw_session_id, "sessionAttributes": session_attributes},
            timeout=self.timeout_s,
            headers={"Content-Type": "application/json"},
        )

        if not response.ok:
            raise RuntimeError(
                f"EC2 agent request failed ({response.status_code}): "
                f"{response.text}"
            )

        payload = response.json()

        # New structured format: {"response": {"txt": "...", "end": false, ...}}
        agent_response = payload.get("response")
        if not isinstance(agent_response, dict) or "txt" not in agent_response:
            raise RuntimeError(
                f"EC2 agent response missing structured 'response.txt' field. Got: {payload}"
            )

        logger.debug("EC2 agent response: %s", agent_response.get("txt", "")[:200])
        return agent_response
