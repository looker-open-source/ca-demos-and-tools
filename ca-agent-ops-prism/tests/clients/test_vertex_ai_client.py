"""Unit tests for VertexAIClient."""

from typing import Any
from unittest.mock import MagicMock
from unittest.mock import patch

from prism.server.clients.vertex_ai_client import VertexAIClient
import pydantic
import pytest
from vertexai.generative_models import GenerationConfig


class TestVertexAIClient:
  """Tests for VertexAIClient."""

  @pytest.fixture
  def mock_generative_model(self):
    with patch("prism.server.clients.vertex_ai_client.GenerativeModel") as mock:
      yield mock

  @pytest.fixture
  def client(self):
    with patch("vertexai.init"):
      return VertexAIClient()

  def test_generate_text_success(self, client, mock_generative_model):
    """Tests successful text generation."""
    mock_model_instance = mock_generative_model.return_value
    mock_response = MagicMock()
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].content.parts = [MagicMock()]
    mock_response.candidates[0].content.parts[0].text = "Generated Text"
    mock_model_instance.generate_content.return_value = mock_response

    result = client.generate_text("prompt")

    assert result == "Generated Text"
    mock_model_instance.generate_content.assert_called_with("prompt")

  def test_generate_structured_success(self, client, mock_generative_model):
    """Tests structured generation success."""
    mock_model_instance = mock_generative_model.return_value
    mock_response = MagicMock()
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].content.parts = [MagicMock()]
    mock_response.candidates[0].content.parts[0].text = '{"foo": "bar"}'
    mock_model_instance.generate_content.return_value = mock_response

    class TestSchema(pydantic.BaseModel):
      foo: str

    result = client.generate_structured("prompt", TestSchema)

    assert result.foo == "bar"
    # Verify generation_config was passed with JSON mime type
    call_args = mock_model_instance.generate_content.call_args
    assert call_args
    _, kwargs = call_args
    gen_config = kwargs.get("generation_config")
    assert isinstance(gen_config, GenerationConfig)
    assert (
        gen_config._raw_generation_config.response_mime_type
        == "application/json"
    )

  def test_generate_text_empty_response(self, client, mock_generative_model):
    """Tests handling of empty response."""
    mock_model_instance = mock_generative_model.return_value
    mock_model_instance.generate_content.return_value = MagicMock(candidates=[])

    result = client.generate_text("prompt")

    assert result is None

  def test_generate_text_exception(self, client, mock_generative_model):
    """Tests exception handling."""
    mock_model_instance = mock_generative_model.return_value
    mock_model_instance.generate_content.side_effect = Exception("API Error")

    with pytest.raises(Exception, match="API Error"):
      client.generate_text("prompt")
