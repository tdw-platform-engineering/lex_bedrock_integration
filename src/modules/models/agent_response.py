"""Structured response model returned by all agent backends."""

from dataclasses import dataclass


@dataclass
class AgentResponse:
    """Represents the structured output from an agent invocation.

    Attributes
    ----------
    sessionid : str
        UUID identifying the conversation session.
    txt : str
        The agent's textual reply.
    end : bool
        Whether the conversation has ended.
    """

    sessionid: str
    txt: str
    end: bool

    @classmethod
    def from_dict(cls, data: dict) -> "AgentResponse":
        """Build an ``AgentResponse`` from a raw dict, coercing types."""
        end_raw = data.get("end", False)
        if isinstance(end_raw, str):
            end_val = end_raw.lower() in ("true", "1", "yes")
        else:
            end_val = bool(end_raw)

        return cls(
            sessionid=str(data.get("sessionid", "")),
            txt=str(data.get("txt", "")),
            end=end_val,
        )

    def to_dict(self) -> dict:
        """Serialize back to a plain dict."""
        return {
            "sessionid": self.sessionid,
            "txt": self.txt,
            "end": self.end,
        }
