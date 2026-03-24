"""
Tests for the Lambda entry point (``src.lambda_function.lambda_handler``).

The module-level ``lex_handler`` singleton is patched via a fixture that swaps
its ``agent_service`` attribute directly, avoiding tricky reload issues.
"""

from unittest.mock import MagicMock

import pytest

from src.lambda_function import lambda_handler
import src.lambda_function as lf_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_lex_event():
    """Minimal Lex V2 fulfillment event."""
    return {
        "inputMode": "Speech",
        "sessionId": "test-session-123",
        "inputTranscript": "sí con él habla",
        "requestAttributes": {},
        "sessionState": {
            "sessionAttributes": {
                "contactId": "test-session-123",
            },
            "intent": {
                "name": "FallbackIntent",
                "slots": {},
                "state": "ReadyForFulfillment",
                "confirmationState": "None",
            },
        },
        "messageVersion": "1.0",
        "invocationSource": "FulfillmentCodeHook",
    }


@pytest.fixture
def mock_agent():
    """Swap the module-level singleton's agent_service for a MagicMock."""
    original = lf_module.lex_handler.agent_service
    mock = MagicMock()
    lf_module.lex_handler.agent_service = mock
    yield mock
    lf_module.lex_handler.agent_service = original


@pytest.fixture(autouse=True)
def mock_transcript_table(monkeypatch):
    """Mock transcript DynamoDB table used by lambda_function logging."""
    table = MagicMock()
    fake_ddb = MagicMock()
    fake_ddb.Table.return_value = table

    monkeypatch.setenv(
        "CALL_TRANSCRIPT_LOGGING_TABLE", "connect_outbound_call_transcript"
    )
    monkeypatch.setattr(lf_module, "ddb", fake_ddb)
    return table


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestLambdaHandlerHappyPath:
    """Verify the handler returns a valid Lex V2 response on success."""

    def test_handler_returns_lex_response(self, mock_agent, sample_lex_event):
        mock_agent.process_with_agent.return_value = (
            "Hola, ¿en qué puedo ayudarte?"
        )

        response = lambda_handler(sample_lex_event, None)

        assert "sessionState" in response
        assert "messages" in response
        assert response["messages"][0]["contentType"] == "PlainText"
        assert response["messages"][0]["content"] == "Hola, ¿en qué puedo ayudarte?"
        assert response["sessionState"]["dialogAction"]["type"] == "ElicitIntent"
        assert response["sessionState"]["intent"]["state"] == "InProgress"

    def test_handler_logs_user_and_bot_transcripts(
        self, mock_agent, sample_lex_event, mock_transcript_table
    ):
        mock_agent.process_with_agent.return_value = "Respuesta bot de prueba"

        lambda_handler(sample_lex_event, None)

        put_calls = mock_transcript_table.put_item.call_args_list
        assert len(put_calls) == 2

        items = [call.kwargs["Item"] for call in put_calls]
        assert [item["type"] for item in items] == ["USER", "BOT"]
        assert items[0]["message"].startswith("Cliente:")
        assert items[1]["message"] == "Respuesta bot de prueba"
        assert items[0]["pk"] == items[1]["pk"]
        assert items[0]["sk"].startswith("TIMESTAMP#")
        assert items[1]["sk"].startswith("TIMESTAMP#")

    def test_handler_fulfilled_on_transfer(self, mock_agent, sample_lex_event):
        mock_agent.process_with_agent.return_value = (
            "Te voy a transferir con un agente humano."
        )

        response = lambda_handler(sample_lex_event, None)

        assert response["sessionState"]["dialogAction"]["type"] == "Close"
        assert response["sessionState"]["intent"]["state"] == "Fulfilled"
        assert response["sessionState"]["sessionAttributes"]["EsPositivo"] == "true"

    def test_handler_fulfilled_on_should_end_call_json(
        self, mock_agent, sample_lex_event
    ):
        mock_agent.process_with_agent.return_value = """Disculpe la molestia, me equivoqué de número. Que tenga buen día.

```json
{
  "estado_conversacion": "VALIDANDO_IDENTIDAD",
  "estado_final": "CIERRE_POR_IDENTIDAD_INCORRECTA",
  "monto_comprometido": null,
  "fecha_comprometida": null,
  "numero_alternativo": null,
  "motivo": "Número equivocado",
  "should_end_call": true
}
```"""

        response = lambda_handler(sample_lex_event, None)

        assert response["sessionState"]["dialogAction"]["type"] == "Close"
        assert response["sessionState"]["intent"]["state"] == "Fulfilled"
        assert response["sessionState"]["sessionAttributes"]["COMPLETED"] == "true"
        assert response["messages"][0]["content"] == (
            "Disculpe la molestia, me equivoqué de número. Que tenga buen día."
        )

    def test_handler_keeps_in_progress_on_should_end_call_false_json(
        self, mock_agent, sample_lex_event
    ):
        mock_agent.process_with_agent.return_value = """Seguimos validando su información.

```json
{
  "estado_conversacion": "VALIDANDO_IDENTIDAD",
  "should_end_call": false
}
```"""

        response = lambda_handler(sample_lex_event, None)

        assert response["sessionState"]["dialogAction"]["type"] == "ElicitIntent"
        assert response["sessionState"]["intent"]["state"] == "InProgress"
        assert response["sessionState"]["sessionAttributes"]["COMPLETED"] == "false"
        assert response["messages"][0]["content"] == "Seguimos validando su información."


# ---------------------------------------------------------------------------
# Error path
# ---------------------------------------------------------------------------

class TestLambdaHandlerErrorPath:
    """Verify the handler returns a graceful error response on failure."""

    def test_handler_returns_error_on_exception(self, mock_agent, sample_lex_event):
        mock_agent.process_with_agent.side_effect = RuntimeError("Boom")

        response = lambda_handler(sample_lex_event, None)

        assert response["sessionState"]["intent"]["state"] == "Failed"
        assert response["sessionState"]["dialogAction"]["type"] == "Close"
        assert "error" in response["messages"][0]["content"].lower()
