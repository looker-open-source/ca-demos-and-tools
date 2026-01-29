"""Unit tests for GenAIClient."""

import unittest.mock

from google.genai import types
from prism.server.clients import gen_ai_client
import pydantic
import pytest


class TestGenAIClient:
  """Tests for GenAIClient."""

  @pytest.fixture
  def mock_client(self):
    with unittest.mock.patch(
        "prism.server.clients.gen_ai_client.genai.Client"
    ) as mock:
      yield mock

  @pytest.fixture
  def client(self, mock_client):
    return gen_ai_client.GenAIClient(
        project="test-project", location="us-central1"
    )

  def test_generate_text_success(self, client, mock_client):
    """Tests successful text generation."""
    mock_client_instance = mock_client.return_value
    mock_response = unittest.mock.MagicMock()
    mock_response.text = "Generated Text"
    mock_client_instance.models.generate_content.return_value = mock_response

    result = client.generate_text("prompt")

    assert result == "Generated Text"
    mock_client_instance.models.generate_content.assert_called_with(
        model="gemini-2.5-pro", contents="prompt"
    )

  def test_generate_structured_success(self, client, mock_client):
    """Tests structured generation success."""
    mock_client_instance = mock_client.return_value
    mock_response = unittest.mock.MagicMock()
    mock_response.text = '{"foo": "bar"}'
    mock_client_instance.models.generate_content.return_value = mock_response

    class TestSchema(pydantic.BaseModel):
      foo: str

    result = client.generate_structured("prompt", TestSchema)

    assert result.foo == "bar"
    # Verify generation_config was passed with JSON mime type
    call_args = mock_client_instance.models.generate_content.call_args
    assert call_args
    _, kwargs = call_args
    config = kwargs.get("config")
    assert isinstance(config, types.GenerateContentConfig)
    assert config.response_mime_type == "application/json"

  def test_generate_text_empty_response(self, client, mock_client):
    """Tests handling of empty response."""
    mock_client_instance = mock_client.return_value
    mock_client_instance.models.generate_content.return_value = (
        unittest.mock.MagicMock(text=None)
    )

    result = client.generate_text("prompt")

    assert result is None

  def test_generate_text_exception(self, client, mock_client):
    """Tests exception handling."""
    mock_client_instance = mock_client.return_value
    mock_client_instance.models.generate_content.side_effect = Exception(
        "API Error"
    )

    with pytest.raises(Exception, match="API Error"):
      client.generate_text("prompt")
