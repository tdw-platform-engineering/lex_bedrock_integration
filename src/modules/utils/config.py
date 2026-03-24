"""
Centralized configuration for the demo-lex-bedrock Lambda.

Reads environment variables with sensible defaults and exposes
them through a Config dataclass for type-safe access across modules.
"""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    """Immutable configuration loaded from environment variables."""

    # Agent provider selection: bedrock | agentcore | ec2
    agent_provider: str = field(
        default_factory=lambda: os.getenv("AGENT_PROVIDER", "bedrock").lower()
    )

    # AWS general
    aws_region: str = field(
        default_factory=lambda: os.getenv("AWS_REGION", "us-east-1")
    )

    # Bedrock Agent
    bedrock_agent_id: str = field(
        default_factory=lambda: os.getenv("BEDROCK_AGENT_ID", "")
    )
    bedrock_agent_alias_id: str = field(
        default_factory=lambda: os.getenv("BEDROCK_AGENT_ALIAS_ID", "")
    )

    # AgentCore
    agentcore_runtime_arn: str = field(
        default_factory=lambda: os.getenv("AGENTCORE_RUNTIME_ARN", "")
    )
    agentcore_region: str = field(
        default_factory=lambda: os.getenv(
            "AGENTCORE_REGION", os.getenv("AWS_REGION", "us-west-2")
        )
    )
    agentcore_timeout_ms: int = field(
        default_factory=lambda: int(os.getenv("AGENTCORE_TIMEOUT_MS", "120000"))
    )

    # EC2 Agent (HTTP endpoint)
    agent_http_url: str = field(
        default_factory=lambda: os.getenv(
            "AGENT_HTTP_URL", "http://3.234.208.1:8081/chat"
        )
    )
    agent_http_timeout_ms: int = field(
        default_factory=lambda: int(os.getenv("AGENT_HTTP_TIMEOUT_MS", "20000"))
    )

    # Connect Customer Profiles
    connect_domain_name: str = field(
        default_factory=lambda: os.getenv("CONNECT_DOMAIN_NAME", "")
    )
    summary_field: str = field(
        default_factory=lambda: os.getenv("SUMMARY_FIELD", "AdditionalInformation")
    )
