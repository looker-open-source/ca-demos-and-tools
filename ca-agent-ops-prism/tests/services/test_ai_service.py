import json
from unittest import mock
from prism.common.schemas import agent as agent_schemas
from prism.server.clients.gen_ai_client import GenAIClient
from prism.server.services.ai_service import AIService
import pytest


def test_format_golden_queries_success():
  """Tests successful formatting of golden queries."""
  mock_client = mock.MagicMock(spec=GenAIClient)
  # Mocking the prompt template loading if necessary, but AIService loads it in __init__
  # We might need to mock open/read if we can't rely on the file being present,
  # but usually integration/unit tests in this codebase seem to rely on local files or mocks.
  # Let's see if AIService constructor reads the file.

  # We will mock the open call for the prompt template to avoid file system dependencies if possible,
  # or just assume it exists. Given the previous file view, it's a real file.
  # Let's inspect AIService init if it fails. For now, we assume we can instantiate it.

  # Actually, we should probably mock the _golden_query_template attribute if validation fails,
  # but let's try to instantiate it normally first.
  # Wait, AIService reads the file in __init__.
  # self._golden_query_template = self._load_prompt("golden_query_prompt.txt")

  # We can patch `open` or `pathlib.Path.read_text` or just let it read the real file.
  # Reading the real file is better for integration testing, but unit tests should be isolated.
  # Let's try to just instantiate it, if it fails we mock.

  service = AIService(mock_client)

  # Mock response
  mock_gq = agent_schemas.LookerGoldenQuery(
      natural_language_questions=["Show me sales"],
      looker_query=agent_schemas.LookerQuery(
          model="sales", view="sales", fields=["amount"]
      ),
  )

  # The service defines an internal class GoldenQueriesResponse.
  # The client returns an instance of that class.
  # We can just return an object with a .golden_queries attribute.
  mock_response = mock.MagicMock()
  mock_response.golden_queries = [mock_gq]
  mock_client.generate_structured.return_value = mock_response

  input_text = "Show me sales"
  result = service.format_golden_queries(input_text)

  assert result is not None
  data = json.loads(result)
  assert len(data) == 1
  assert data[0]["natural_language_questions"] == ["Show me sales"]
  assert data[0]["looker_query"]["model"] == "sales"


def test_format_golden_queries_empty_input():
  """Tests that empty input returns empty string."""
  mock_client = mock.MagicMock(spec=GenAIClient)
  service = AIService(mock_client)

  assert service.format_golden_queries("") == ""
  assert service.format_golden_queries("   ") == ""


def test_format_golden_queries_ai_error():
  """Tests that AI errors result in returning the original text."""
  mock_client = mock.MagicMock(spec=GenAIClient)
  service = AIService(mock_client)
  mock_client.generate_structured.side_effect = Exception("AI Error")

  input_text = "Show me sales"
  result = service.format_golden_queries(input_text)

  assert result == input_text


def test_format_golden_queries_empty_response():
  """Tests that empty/invalid AI response returns original text."""
  mock_client = mock.MagicMock(spec=GenAIClient)
  service = AIService(mock_client)
  mock_client.generate_structured.return_value = None

  input_text = "Show me sales"
  result = service.format_golden_queries(input_text)

  assert result == input_text
