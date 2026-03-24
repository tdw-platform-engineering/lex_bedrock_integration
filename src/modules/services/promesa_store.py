"""
Stores accepted payment promises in DynamoDB table ``tdw-promesas-pago-us-west-2``.
"""

import logging
from datetime import datetime, timezone

import boto3

from src.modules.utils.config import Config

logger = logging.getLogger(__name__)

TABLE_NAME = "tdw-promesas-pago-us-west-2"


class PromesaStore:
    """Thin wrapper around DynamoDB put_item for payment promises."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = boto3.resource(
                "dynamodb", region_name=self.config.aws_region
            ).Table(TABLE_NAME)
        return self._client

    def save_promesa(self, session_id: str, agent_response: dict, session_attrs: dict) -> None:
        """Persist a PROMESA_ACEPTADA record keyed by session_id + timestamp."""
        ts = datetime.now(timezone.utc).isoformat()

        item = {
            "pk": session_id,
            "ts": ts,
            "st": agent_response.get("st"),
            "amount": agent_response.get("amount"),
            "date": agent_response.get("date"),
            "alt_phone": agent_response.get("alt_phone"),
            "txt": agent_response.get("txt", ""),
            "jobPk": session_attrs.get("jobPk"),
            "jobSk": session_attrs.get("jobSk"),
        }

        logger.info("Saving promesa: pk=%s, ts=%s, st=%s", session_id, ts, item["st"])
        self.client.put_item(Item={k: v for k, v in item.items() if v is not None})
