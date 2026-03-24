"""
Bedrock Agent service — invokes an Amazon Bedrock Agent via the
bedrock-agent-runtime SDK and returns the streamed text completion.
"""

import logging
import re

import boto3

from src.modules.services.base_agent import BaseAgentService
from src.modules.utils.config import Config

logger = logging.getLogger(__name__)

# Spanish month names for date formatting (avoids babel / locale deps)
_MONTH_NAMES_ES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}

# XML-like function call tags that Bedrock sometimes injects
_XML_TAGS_TO_STRIP = [
    "<_function=user_askuser>",
    "<__function=user_askuser>",
    "<_parameter=question>",
    "<__parameter=question>",
    "</_parameter>",
    "</__parameter>",
    "</__",
]


class BedrockAgentService(BaseAgentService):
    """Wraps the Amazon Bedrock Agent Runtime ``invoke_agent`` API."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self.client = None

    def _get_client(self):
        if self.client is None:
            self.client = boto3.client(
                "bedrock-agent-runtime",
                region_name=self.config.aws_region,
            )
        return self.client

    # ------------------------------------------------------------------
    # Low-level invoke
    # ------------------------------------------------------------------
    def invoke_agent(
        self,
        agent_id: str,
        agent_alias_id: str,
        session_id: str,
        input_text: str,
    ) -> str:
        """Call Bedrock ``InvokeAgent`` and return the concatenated completion."""

        response = self._get_client().invoke_agent(
            agentId=agent_id,
            agentAliasId=agent_alias_id,
            sessionId=session_id,
            inputText=input_text,
        )

        completion = ""
        chunk_count = 0

        for event in response.get("completion", []):
            chunk_count += 1
            chunk_bytes = event.get("chunk", {}).get("bytes")
            if chunk_bytes:
                completion += chunk_bytes.decode("utf-8")

        logger.info(
            "Bedrock agent responded — chunks=%d, length=%d",
            chunk_count,
            len(completion),
        )
        return completion

    # ------------------------------------------------------------------
    # Public interface (BaseAgentService)
    # ------------------------------------------------------------------
    def process_with_agent(self, user_input: str, context: dict) -> str:
        agent_id = self.config.bedrock_agent_id
        agent_alias_id = self.config.bedrock_agent_alias_id
        session_id = context.get("conversationHistory", {}).get("sessionId", "")

        logger.info(
            "Bedrock config: agent_id=%s, alias=%s, session=%s, region=%s",
            agent_id,
            agent_alias_id,
            session_id,
            self.config.aws_region,
        )

        if not agent_id or not agent_alias_id:
            raise ValueError(
                "Configuración del agente de Bedrock incompleta. "
                "Verificar BEDROCK_AGENT_ID y BEDROCK_AGENT_ALIAS_ID."
            )

        if not re.match(r"^[A-Z0-9]{10}$", agent_id):
            raise ValueError(
                f"Formato inválido de BEDROCK_AGENT_ID: {agent_id}. "
                "Debe ser 10 caracteres alfanuméricos."
            )

        if (
            not re.match(r"^[A-Z0-9]{10}$", agent_alias_id)
            and agent_alias_id != "TSTALIASID"
        ):
            raise ValueError(
                f"Formato inválido de BEDROCK_AGENT_ALIAS_ID: {agent_alias_id}. "
                "Debe ser 10 caracteres alfanuméricos o 'TSTALIASID'."
            )

        # Prepend current date in Spanish
        from datetime import datetime  # noqa: E402

        now = datetime.now()
        fecha = f"{now.day} de {_MONTH_NAMES_ES[now.month]} de {now.year}"
        enriched_input = f"Fecha actual es {fecha}, {user_input}"
        logger.info("Input nuevo: %s", enriched_input)

        agent_response = self.invoke_agent(
            agent_id, agent_alias_id, session_id, enriched_input
        )

        # Strip XML-like function call tags
        cleaned = agent_response
        for tag in _XML_TAGS_TO_STRIP:
            cleaned = cleaned.replace(tag, "")

        logger.info("Respuesta del agente: %s", cleaned[:200])
        return cleaned
