"""
AgentCore service — invokes an AWS Bedrock AgentCore runtime endpoint
and returns the structured agent response dict.

Payload sent to AgentCore:
    {"input": "<user text>", "sessionAttributes": {<client data>}}

Response expected from AgentCore:
    {"sessionid": "<uuid>", "txt": "...", "end": true/false}
"""

import json
import logging

import boto3
from botocore.config import Config as BotoConfig

from src.modules.models.agent_response import AgentResponse
from src.modules.services.base_agent import BaseAgentService
from src.modules.utils.config import Config

logger = logging.getLogger(__name__)


class AgentCoreService(BaseAgentService):
    """Wraps the Bedrock AgentCore ``invoke_agent_runtime`` API."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        timeout_s = self.config.agentcore_timeout_ms / 1000
        self._client_config = BotoConfig(read_timeout=int(timeout_s))
        self.client = None
        self.agent_runtime_arn = self.config.agentcore_runtime_arn

    def _get_client(self):
        if self.client is None:
            self.client = boto3.client(
                "bedrock-agentcore",
                region_name=self.config.agentcore_region,
                config=self._client_config,
            )
        return self.client

    def process_with_agent(self, user_input: str, context: dict, event: dict) -> dict:
        if not self.agent_runtime_arn:
            raise ValueError(
                "AGENTCORE_RUNTIME_ARN is required. Set it to the AgentCore "
                "runtime ARN, e.g. "
                "arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/MyRuntime-AbCdEfGhIj"
            )

        # Resolve session ID via sessionState.sessionAttributes.contactId or sessionId
        raw_session_id = context.get("conversationHistory", {}).get("sessionId", "")
        session_attributes = context.get("conversationHistory", {}).get("sessionAttributes", {})
        print("Session attributes:", {"input": user_input, "sessionId": raw_session_id, "sessionAttributes": session_attributes})
        logger.info(
            "Calling AgentCore agent: arn=%s, session=%s",
            self.agent_runtime_arn,
            raw_session_id,
        )

        payload = {
            "input": user_input,
            "sessionAttributes": session_attributes,
            "runtimeSessionId": raw_session_id,
        }

        logger.info("AgentCore payload: %s", json.dumps(payload))
        payload_bytes = json.dumps(payload).encode("utf-8")

        try:
            response = self._get_client().invoke_agent_runtime(
                agentRuntimeArn=self.agent_runtime_arn,
                runtimeSessionId=raw_session_id,
                payload=payload_bytes,
            )
        except Exception as exc:
            logger.error("AgentCore invocation failed: %s", exc)
            raise RuntimeError(f"AgentCore invocation failed: {exc}") from exc

        result = self._read_response(response)

        logger.debug("AgentCore agent response: %s", result.txt[:200])
        return result.to_dict()

    def _read_response(self, response: dict) -> AgentResponse:
        """Parse the AgentCore response into an ``AgentResponse``."""
        content_type = response.get("contentType", "")

        # Streaming event-stream response
        if "text/event-stream" in content_type:
            chunks = []
            for line in response["response"].iter_lines(chunk_size=10):
                if line:
                    decoded = line.decode("utf-8")
                    if decoded.startswith("data: "):
                        decoded = decoded[6:]
                    chunks.append(decoded)
            raw = "\n".join(chunks)
        else:
            # Standard body/payload response
            body = response.get("body") or response.get("payload") or response.get("response")
            if body is None:
                raise RuntimeError("AgentCore response has no body")
            if hasattr(body, "read"):
                raw = body.read().decode("utf-8")
            elif isinstance(body, (bytes, bytearray)):
                raw = body.decode("utf-8")
            else:
                raw = str(body)

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Non-JSON AgentCore response: %s", raw[:300])
            raise RuntimeError("AgentCore returned a non-JSON response")

        # Validate expected structure
        if "txt" not in result:
            logger.error("Unexpected AgentCore response shape: %s", result)
            raise RuntimeError('AgentCore response missing "txt" field')

        return AgentResponse.from_dict(result)
