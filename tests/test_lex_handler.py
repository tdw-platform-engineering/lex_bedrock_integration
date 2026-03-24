"""
Tests for the LexHandler — extraction, prompt building, and response formatting.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.modules.handlers.lex_handler import LexHandler


# ---------------------------------------------------------------------------
# Fixture: handler with a mocked agent
# ---------------------------------------------------------------------------

@pytest.fixture
def handler():
    """Return a LexHandler with a mocked agent service."""
    with (
        patch("src.modules.handlers.lex_handler.create_agent_service") as mock_factory,
        patch(
            "src.modules.handlers.lex_handler.CustomerProfilesService"
        ) as mock_cp_cls,
    ):
        mock_agent = MagicMock()
        mock_agent.process_with_agent.return_value = "Respuesta de prueba"
        mock_factory.return_value = mock_agent
        h = LexHandler()
        h._mock_agent = mock_agent
        h._mock_cp = mock_cp_cls.return_value
        yield h


@pytest.fixture
def basic_event():
    return {
        "inputTranscript": "quiero pagar",
        "sessionId": "ses-001",
        "requestAttributes": {"platform": "Connect"},
        "sessionState": {
            "sessionAttributes": {"contactId": "contact-abc"},
            "intent": {
                "name": "PagoIntent",
                "slots": {
                    "monto": {"value": {"originalValue": "500"}},
                    "moneda": {"value": {"originalValue": "dólares"}},
                    "vacioSlot": None,
                },
            },
        },
    }


# ---------------------------------------------------------------------------
# extract_lex_data
# ---------------------------------------------------------------------------

class TestExtractLexData:

    def test_extracts_intent_and_transcript(self, handler, basic_event):
        data = handler.extract_lex_data(basic_event)
        assert data["intent"] == "PagoIntent"
        assert data["userInput"] == "quiero pagar"
        assert data["originalUtterance"] == "quiero pagar"

    def test_extracts_slot_values(self, handler, basic_event):
        data = handler.extract_lex_data(basic_event)
        assert data["slots"]["monto"] == "500"
        assert data["slots"]["moneda"] == "dólares"
        assert "vacioSlot" not in data["slots"]

    def test_resolves_session_id_from_contact_id(self, handler, basic_event):
        data = handler.extract_lex_data(basic_event)
        assert data["conversationHistory"]["sessionId"] == "contact-abc"

    def test_falls_back_to_session_id(self, handler, basic_event):
        del basic_event["sessionState"]["sessionAttributes"]["contactId"]
        data = handler.extract_lex_data(basic_event)
        assert data["conversationHistory"]["sessionId"] == "ses-001"

    def test_generates_fallback_session_id(self, handler):
        event = {
            "inputTranscript": "hola",
            "sessionState": {"intent": {"name": "Test", "slots": {}}},
        }
        data = handler.extract_lex_data(event)
        assert data["conversationHistory"]["sessionId"].startswith("lex-")


# ---------------------------------------------------------------------------
# build_agent_input
# ---------------------------------------------------------------------------

class TestBuildAgentInput:

    def test_builds_prompt_with_slots(self, handler):
        lex_data = {
            "originalUtterance": "quiero pagar 500",
            "intent": "PagoIntent",
            "slots": {"monto": "500", "moneda": "USD"},
        }
        result = handler.build_agent_input(lex_data)
        assert "Cliente:" in result
        assert "Utterance original: quiero pagar 500" in result
        assert "Intent: PagoIntent" in result
        assert "- monto: 500" in result
        assert "- moneda: USD" in result

    def test_builds_prompt_without_slots(self, handler):
        lex_data = {
            "originalUtterance": "hola",
            "intent": "Greeting",
            "slots": {},
        }
        result = handler.build_agent_input(lex_data)
        assert "Parámetros:" not in result


# ---------------------------------------------------------------------------
# format_lex_response
# ---------------------------------------------------------------------------

class TestFormatLexResponse:

    def _make_event(self, intent_name="FallbackIntent", session_attrs=None):
        return {
            "sessionState": {
                "sessionAttributes": session_attrs or {},
                "intent": {"name": intent_name},
            }
        }

    def test_elicit_intent_on_normal_response(self, handler):
        event = self._make_event()
        resp = handler.format_lex_response(event, "Hola, ¿cómo estás?", {})
        assert resp["sessionState"]["dialogAction"]["type"] == "ElicitIntent"
        assert resp["sessionState"]["intent"]["state"] == "InProgress"
        assert resp["sessionState"]["sessionAttributes"]["EsPositivo"] == "false"

    def test_fulfilled_on_agente_humano(self, handler):
        event = self._make_event()
        resp = handler.format_lex_response(
            event, "Te conecto con un agente humano.", {}
        )
        assert resp["sessionState"]["dialogAction"]["type"] == "Close"
        assert resp["sessionState"]["intent"]["state"] == "Fulfilled"
        assert resp["sessionState"]["sessionAttributes"]["EsPositivo"] == "true"

    def test_fulfilled_on_transferir(self, handler):
        event = self._make_event()
        resp = handler.format_lex_response(
            event, "Voy a transferir tu llamada.", {}
        )
        assert resp["sessionState"]["dialogAction"]["type"] == "Close"
        assert resp["sessionState"]["sessionAttributes"]["EsPositivo"] == "true"

    def test_fulfilled_on_procesada(self, handler):
        event = self._make_event()
        resp = handler.format_lex_response(
            event, "Tu solicitud ha sido procesada correctamente.", {}
        )
        assert resp["sessionState"]["dialogAction"]["type"] == "Close"
        assert resp["sessionState"]["sessionAttributes"]["EsPositivo"] == "true"

    def test_fulfilled_but_not_positive_on_sido_de_ayuda(self, handler):
        event = self._make_event()
        resp = handler.format_lex_response(
            event, "Espero haber sido de ayuda. ¡Hasta luego!", {}
        )
        assert resp["sessionState"]["dialogAction"]["type"] == "Close"
        assert resp["sessionState"]["intent"]["state"] == "Fulfilled"
        assert resp["sessionState"]["sessionAttributes"]["EsPositivo"] == "false"

    def test_preserves_session_attributes(self, handler):
        event = self._make_event(session_attrs={"foo": "bar", "baz": "qux"})
        resp = handler.format_lex_response(event, "Hola", {})
        assert resp["sessionState"]["sessionAttributes"]["foo"] == "bar"
        assert resp["sessionState"]["sessionAttributes"]["baz"] == "qux"
        assert "EsPositivo" in resp["sessionState"]["sessionAttributes"]

    def test_cotizacion_extraction_and_profile_update(self, handler):
        event = self._make_event(
            session_attrs={"profileId": "prof-123"}
        )
        handler.config = MagicMock()
        handler.config.connect_domain_name = "my-domain"
        resp = handler.format_lex_response(
            event,
            "Hemos procesado tu solicitud: Cotización ABC-123. Ahora procederemos.",
            {},
        )
        handler.customer_profiles_service.update_profile.assert_called_once_with(
            "prof-123", "Cotización ABC-123"
        )
