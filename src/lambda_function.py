"""
AWS Lambda entry point for the demo-lex-bedrock function.

Receives Amazon Lex V2 fulfillment events, processes them through
an AI agent (Bedrock / AgentCore / EC2), and returns the formatted
Lex V2 response.

Ported from ``lex-bedrock-agent-integration/index.mjs``.
"""

import json
import logging
import os
import time

import boto3
from botocore.config import Config as BotoConfig

from src.modules.handlers.lex_handler import LexHandler

logger = logging.getLogger(__name__)
# set log level to INFO by default, can be overridden by environment variable
logging.basicConfig(level=logging.INFO)

REGION = os.getenv("AWS_REGION", "us-east-1")
BOTO_CONFIG = BotoConfig(retries={"max_attempts": 6, "mode": "standard"})

ddb = None

# Module-level singleton — mirrors the JS pattern where LexHandler is
# instantiated once outside the handler for connection reuse across invocations.
lex_handler = LexHandler()


def lambda_handler(event: dict, context) -> dict:
    """
    Lambda handler for Lex V2 fulfillment.

    Parameters
    ----------
    event : dict
        Amazon Lex V2 fulfillment event.
    context : LambdaContext
        AWS Lambda context object.

    Returns
    -------
    dict
        Lex V2 response with ``sessionState``, ``messages``, etc.
    """
    logger.info("=== INICIO PROCESAMIENTO LAMBDA ===")
    # print("Event recibido: %s", json.dumps(event, default=str))
    request_start = time.perf_counter()

    try:
        # Step 1 — Extract Lex data
        step_start = time.perf_counter()
        lex_data = lex_handler.extract_lex_data(event)
        logger.info(
            "Step 1 (extract_lex_data) completed in %.3f ms",
            (time.perf_counter() - step_start) * 1000,
        )

        # Step 2 — Process through agent
        step_start = time.perf_counter()
        user_input = lex_handler.build_agent_input(lex_data)
        agent_response = lex_handler.process_with_bedrock_agent(lex_data, event)
        # data now in inux format
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        logger.info(
            "Step 2 (process_with_bedrock_agent) completed in %.3f ms",
            (time.perf_counter() - step_start) * 1000,
        )

        # Step 3 — Format Lex response
        step_start = time.perf_counter()
        lex_response = lex_handler.format_lex_response(event, agent_response, lex_data)
        logger.info(
            "Step 3 (format_lex_response) completed in %.3f ms",
            (time.perf_counter() - step_start) * 1000,
        )
        logger.info(
            "Total lambda_handler time: %.3f ms",
            (time.perf_counter() - request_start) * 1000,
        )
        return lex_response

    except Exception:
        logger.info(
            "Total lambda_handler time until failure: %.3f ms",
            (time.perf_counter() - request_start) * 1000,
        )
        logger.exception("Error en el handler principal")
        intent_name = (
            event.get("sessionState", {}).get("intent", {}).get("name", "Unknown")
        )
        return {
            "sessionState": {
                "dialogAction": {"type": "Close"},
                "intent": {"name": intent_name, "state": "Failed"},
            },
            "messages": [
                {
                    "contentType": "PlainText",
                    "content": (
                        "Lo siento, ocurrió un error al procesar tu solicitud. "
                        "Por favor, intenta nuevamente."
                    ),
                }
            ],
        }
