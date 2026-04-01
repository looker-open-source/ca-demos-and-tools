import logging
from typing import TYPE_CHECKING
from unittest import mock

from prism.common.schemas.example import TestCaseInput
from prism.server.clients.gen_ai_client import GenAIClient
from prism.server.services.bulk_import_service import BulkImportService
import pydantic
import pytest
import yaml


def test_parse_yaml_success():
  """Tests parsing valid structured YAML."""
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
  """Tests parsing invalid YAML."""
  yaml_str = "invalid: : yaml"
  service = BulkImportService(mock.MagicMock())
  try:
    service.parse_yaml(yaml_str)
    assert False, "Should have raised ValueError"
  except ValueError as e:
    assert "Invalid format" in str(e)


def test_parse_yaml_not_a_list():
  """Tests parsing YAML that isn't a list."""
  yaml_str = "question: single"
  service = BulkImportService(mock.MagicMock())
  try:
    service.parse_yaml(yaml_str)
    assert False, "Should have raised ValueError"
  except ValueError as e:
    assert "list of test cases" in str(e)


def test_parse_yaml_schema_mismatch():
  """Tests parsing YAML that doesn't match the schema."""
  yaml_str = "- wrong_field: oops"
  service = BulkImportService(mock.MagicMock())
  try:
    service.parse_yaml(yaml_str)
    assert False, "Should have raised ValueError"
  except ValueError as e:
    assert "question" in str(e)


def test_parse_yaml_extra_fields_forbidden():
  """Tests that extra fields in assertions are forbidden."""
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
  """Tests the AI fix functionality."""
  mock_client = mock.MagicMock(spec=GenAIClient)
  service = BulkImportService(mock_client)

  # Mock the response model
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
  assert "id:" not in result  # Ensure no ID is present
  assert "weight:" not in result  # Ensure no weight is present

  assert "question: Q2" in result
  # The YAML for Q2 should NOT have an assertions key
  assert "assertions:" not in result.split("question: Q2")[-1]

  mock_client.generate_structured.assert_called_once()
