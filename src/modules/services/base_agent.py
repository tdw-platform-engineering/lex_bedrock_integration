"""
Abstract base class for agent services and the factory function.

The strategy pattern allows swapping the AI backend (Bedrock, AgentCore, EC2)
via the AGENT_PROVIDER environment variable without touching handler logic.
"""

from abc import ABC, abstractmethod


class BaseAgentService(ABC):
    """Interface that every agent backend must implement."""

    @abstractmethod
    def process_with_agent(self, user_input: str, context: dict) ->  dict:
        """
        Send *user_input* to the AI agent and return the response.

        Parameters
        ----------
        user_input : str
            The fully constructed prompt (utterance + lex context).
        context : dict
            The ``lex_context`` dict produced by ``LexHandler.extract_lex_data``.

        Returns
        -------
        str | dict
            The agent's response — either a plain text string or a
            structured dict with keys like ``txt``, ``end``, ``st``, etc.
        """


def create_agent_service(provider: str) -> BaseAgentService:
    """Factory — lazy imports to avoid loading unused SDK clients."""

    if provider == "agentcore":
        from src.modules.services.agentcore_agent import AgentCoreService

        return AgentCoreService()
    if provider == "ec2":
        from src.modules.services.ec2_agent import Ec2AgentService

        return Ec2AgentService()

    # default → bedrock
    from src.modules.services.bedrock_agent import BedrockAgentService

    return BedrockAgentService()
