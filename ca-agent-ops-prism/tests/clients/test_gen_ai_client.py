# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""What GenAIClient answers with, and what it lets through.

The two generate methods return None on an empty response and raise whatever
the SDK raised. Both are read as a result by their callers, so the difference
between "the model said nothing" and "the call failed" has to survive the
wrapper.
"""

import unittest.mock

from google.genai import types
from prism.server.clients import gen_ai_client
import pydantic
import pytest


class TestGenAIClient:
  """The SDK client is patched out, so nothing here leaves the process."""

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
    mock_client_instance = mock_client.return_value
    mock_response = unittest.mock.MagicMock()
    mock_response.text = "Generated Text"
    mock_client_instance.models.generate_content.return_value = mock_response

    result = client.generate_text("prompt")

    assert result == "Generated Text"
    mock_client_instance.models.generate_content.assert_called_with(
        model="gemini-3.8-flash", contents="prompt"
    )

  def test_generate_structured_success(self, client, mock_client):
    mock_client_instance = mock_client.return_value
    mock_response = unittest.mock.MagicMock()
    mock_response.text = '{"foo": "bar"}'
    mock_client_instance.models.generate_content.return_value = mock_response

    class TestSchema(pydantic.BaseModel):
      foo: str

    result = client.generate_structured("prompt", TestSchema)

    assert result.foo == "bar"
    call_args = mock_client_instance.models.generate_content.call_args
    assert call_args
    _, kwargs = call_args
    config = kwargs.get("config")
    assert isinstance(config, types.GenerateContentConfig)
    assert config.response_mime_type == "application/json"

  def test_generate_text_empty_response(self, client, mock_client):
    """An empty response comes back as None."""
    mock_client_instance = mock_client.return_value
    mock_client_instance.models.generate_content.return_value = (
        unittest.mock.MagicMock(text=None)
    )

    result = client.generate_text("prompt")

    assert result is None

  def test_generate_text_exception(self, client, mock_client):
    """The client lets the API error propagate."""
    mock_client_instance = mock_client.return_value
    mock_client_instance.models.generate_content.side_effect = Exception(
        "API Error"
    )

    with pytest.raises(Exception, match="API Error"):
      client.generate_text("prompt")
