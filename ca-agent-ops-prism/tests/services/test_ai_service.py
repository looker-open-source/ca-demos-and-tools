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

import json
from unittest import mock
from prism.common.schemas import agent as agent_schemas
from prism.server.clients.gen_ai_client import GenAIClient
from prism.server.services.ai_service import AIService
import pytest


def test_format_golden_queries_success():
  mock_client = mock.MagicMock(spec=GenAIClient)
  # AIService loads golden_query_prompt.txt in __init__. The test lets it read
  # the real file instead of patching open.

  service = AIService(mock_client)

  mock_gq = agent_schemas.LookerGoldenQuery(
      natural_language_questions=["Show me sales"],
      looker_query=agent_schemas.LookerQuery(
          model="sales", view="sales", fields=["amount"]
      ),
  )

  # The client returns the service's internal GoldenQueriesResponse, so any
  # object with a .golden_queries attribute stands in for it.
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
  """Empty input returns an empty string."""
  mock_client = mock.MagicMock(spec=GenAIClient)
  service = AIService(mock_client)

  assert service.format_golden_queries("") == ""
  assert service.format_golden_queries("   ") == ""


def test_format_golden_queries_ai_error():
  """An AI error raises, so the caller can say the fix did not happen.

  This used to log and return the input. The callback treats a return as
  success and clears the validation error under the box, so a quota error
  looked like a model that found nothing to change.
  """
  mock_client = mock.MagicMock(spec=GenAIClient)
  service = AIService(mock_client)
  mock_client.generate_structured.side_effect = Exception("AI Error")

  with pytest.raises(Exception, match="AI Error"):
    service.format_golden_queries("Show me sales")


def test_format_golden_queries_empty_response():
  """A response with nothing in it is a failure, not a no-op."""
  mock_client = mock.MagicMock(spec=GenAIClient)
  service = AIService(mock_client)
  mock_client.generate_structured.return_value = None

  with pytest.raises(RuntimeError, match="no golden queries"):
    service.format_golden_queries("Show me sales")
