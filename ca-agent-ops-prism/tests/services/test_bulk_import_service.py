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

from unittest import mock

from prism.common.schemas.example import TestCaseInput
from prism.server.clients.gen_ai_client import GenAIClient
from prism.server.services.bulk_import_service import BulkImportService
import pytest


def test_parse_yaml_success():
  yaml_str = """
- question: "What is the capital of France?"
  assertions:
    - type: "text-contains"
      value: "Paris"
      weight: 1.0
- question: "How tall is Everest?"
  assertions:
    - type: "duration-max-ms"
      value: 1000
      weight: 0.5
"""
  service = BulkImportService(mock.MagicMock())
  test_cases = service.parse_yaml(yaml_str)

  assert len(test_cases) == 2
  assert test_cases[0].question == "What is the capital of France?"
  assert len(test_cases[0].assertions) == 1
  assert test_cases[0].assertions[0].type == "text-contains"
  assert test_cases[1].question == "How tall is Everest?"


def test_parse_yaml_invalid_yaml():
  yaml_str = "invalid: : yaml"
  service = BulkImportService(mock.MagicMock())
  try:
    service.parse_yaml(yaml_str)
    assert False, "Should have raised ValueError"
  except ValueError as e:
    assert "Invalid format" in str(e)


def test_parse_yaml_not_a_list():
  yaml_str = "question: single"
  service = BulkImportService(mock.MagicMock())
  try:
    service.parse_yaml(yaml_str)
    assert False, "Should have raised ValueError"
  except ValueError as e:
    assert "list of test cases" in str(e)


def test_parse_yaml_schema_mismatch():
  yaml_str = "- wrong_field: oops"
  service = BulkImportService(mock.MagicMock())
  try:
    service.parse_yaml(yaml_str)
    assert False, "Should have raised ValueError"
  except ValueError as e:
    assert "question" in str(e)


def test_parse_yaml_extra_fields_forbidden():
  yaml_str = """
- question: "Extra field test"
  assertions:
    - type: "text-contains"
      value: "Paris"
      id: 123
"""
  service = BulkImportService(mock.MagicMock())
  try:
    service.parse_yaml(yaml_str)
    assert False, "Should have raised ValueError due to extra field 'id'"
  except ValueError as e:
    assert "Extra inputs are not permitted" in str(e)


def test_format_with_ai():
  mock_client = mock.MagicMock(spec=GenAIClient)
  service = BulkImportService(mock_client)

  class MockResponse:
    test_cases = [
        TestCaseInput(
            question="Q1",
            assertions=[
                {"type": "text-contains", "value": "A1", "weight": 1.0}
            ],
        ),
        TestCaseInput(
            question="Q2",
            assertions=[],
        ),
    ]

  mock_client.generate_structured.return_value = MockResponse()

  result = service.format_with_ai("Fix me")

  assert "question: Q1" in result
  assert "type: text-contains" in result
  assert "value: A1" in result
  # The model is asked for questions and assertions. Anything it invents
  # around them has to be dropped before the YAML reaches the user. A weight
  # equal to the default goes too, because re-parse puts it back.
  assert "id:" not in result
  assert "weight:" not in result

  assert "question: Q2" in result
  # Q2 has no assertions, so the key is left out rather than written empty.
  assert "assertions:" not in result.split("question: Q2")[-1]

  mock_client.generate_structured.assert_called_once()


def test_format_with_ai_keeps_a_weight_the_user_set():
  """A diagnostic assertion has to survive AI Fix.

  Every weight used to be stripped before the YAML went back to the textarea,
  so a 0.0 the user had typed came back as the schema default of 1.0 on
  re-parse and the assertion started counting toward the trial score.
  """
  mock_client = mock.MagicMock(spec=GenAIClient)
  service = BulkImportService(mock_client)

  class MockResponse:
    test_cases = [
        TestCaseInput(
            question="Q1",
            assertions=[
                {"type": "text-contains", "value": "A1", "weight": 0.0},
                {"type": "text-contains", "value": "A2", "weight": 0.25},
            ],
        ),
    ]

  mock_client.generate_structured.return_value = MockResponse()

  result = service.format_with_ai("Fix me")
  weights = [a.weight for a in service.parse_yaml(result)[0].assertions]

  assert weights == [0.0, 0.25]


def test_format_with_ai_raises_when_the_model_returns_nothing():
  """A failure has to reach the callback as one.

  format_with_ai used to hand the input text back. The callback wrote that
  into the textarea unchanged and showed nothing, so a model that returned
  nothing looked like a model that found nothing to fix, and the AI Fix Failed
  toast was never reached.
  """
  mock_client = mock.MagicMock(spec=GenAIClient)
  mock_client.generate_structured.return_value = None
  service = BulkImportService(mock_client)

  with pytest.raises(RuntimeError):
    service.format_with_ai("Fix me")


def test_format_with_ai_lets_a_client_error_out():
  """Same reason, for the quota errors that are the common case."""
  mock_client = mock.MagicMock(spec=GenAIClient)
  mock_client.generate_structured.side_effect = RuntimeError("Quota exceeded")
  service = BulkImportService(mock_client)

  with pytest.raises(RuntimeError, match="Quota exceeded"):
    service.format_with_ai("Fix me")
