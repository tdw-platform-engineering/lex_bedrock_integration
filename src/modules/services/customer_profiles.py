"""
Customer Profiles service — updates an Amazon Connect Customer Profile
with a summary/cotización from the agent conversation.
"""

import logging
import boto3

from src.modules.utils.config import Config

logger = logging.getLogger(__name__)


class CustomerProfilesService:
    """Wraps the Connect Customer Profiles ``update_profile`` API."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self.client = None
        self.domain_name = self.config.connect_domain_name
        self.summary_field = self.config.summary_field

    def _get_client(self):
        if self.client is None:
            self.client = boto3.client(
                "customer-profiles",
                region_name=self.config.aws_region,
            )
        return self.client

    def update_profile(self, profile_id: str, summary: str) -> None:
        """Update the customer profile with the given *summary* text."""
        if not profile_id or not self.domain_name:
            return

        params = {
            "DomainName": self.domain_name,
            "ProfileId": profile_id,
            self.summary_field: summary,
        }

        try:
            self._get_client().update_profile(**params)
            logger.info("Profile %s updated successfully", profile_id)
        except Exception as exc:
            logger.error("Error actualizando profile: %s", exc)
