"""Unit tests for the validation service."""

import unittest
from prism.server.services.validation_service import parse_yaml_safely
from prism.server.services.validation_service import validate_assertion


class TestValidationService(unittest.TestCase):
  """Tests for the validation_service."""

  def test_validate_text_contains_success(self):
    data = {"type": "text-contains", "value": "hello", "weight": 1.0}
    error = validate_assertion(data)
    self.assertIsNone(error)

  def test_validate_text_contains_missing_value(self):
    data = {"type": "text-contains", "weight": 1.0}
    error = validate_assertion(data)
    self.assertIn("value", error)

  def test_validate_text_contains_extra_fields(self):
    data = {"type": "text-contains", "value": "h", "extra": "field"}
    error = validate_assertion(data)
    self.assertIn("Extra inputs are not permitted", error)

  def test_validate_latency_max_ms_success(self):
    data = {"type": "duration-max-ms", "value": 500.0, "weight": 0.0}
    error = validate_assertion(data)
    self.assertIsNone(error)

  def test_validate_latency_max_ms_invalid_type(self):
    data = {"type": "duration-max-ms", "value": "not-a-number", "weight": 0.0}
    error = validate_assertion(data)
    self.assertIn("value", error)

  def test_validate_data_check_row_success(self):
    data = {
        "type": "data-check-row",
        "columns": {"col1": "val1", "col2": 123},
        "weight": 1.0,
    }
    error = validate_assertion(data)
    self.assertIsNone(error)

  def test_validate_data_check_row_missing_columns(self):
    data = {"type": "data-check-row", "weight": 1.0}
    error = validate_assertion(data)
    self.assertIn("columns", error)

  def test_parse_yaml_success(self):
    yaml_str = "col1: val1\ncol2: 123"
    data, error = parse_yaml_safely(yaml_str)
    self.assertEqual(data, {"col1": "val1", "col2": 123})
    self.assertIsNone(error)

  def test_parse_yaml_invalid_format(self):
    yaml_str = "col1: : val1"
    data, error = parse_yaml_safely(yaml_str)
    self.assertIsNone(data)
    self.assertIn("Invalid YAML format", error)

  def test_parse_yaml_not_a_dict(self):
    yaml_str = "- item1\n- item2"
    data, error = parse_yaml_safely(yaml_str)
    self.assertIsNone(data)
    self.assertIn("must resolve to a dictionary", error)

  def test_validate_text_contains_empty_value(self):
    data = {"type": "text-contains", "value": "", "weight": 1.0}
    error = validate_assertion(data)
    self.assertIn("at least 1 character", error)

  def test_validate_data_check_row_empty_columns(self):
    data = {"type": "data-check-row", "columns": {}, "weight": 1.0}
    error = validate_assertion(data)
    self.assertIn("at least 1 item", error)

  def test_validate_looker_query_match_empty_params(self):
    data = {"type": "looker-query-match", "params": {}, "weight": 1.0}
    error = validate_assertion(data)
    self.assertIn("all empty", error)

  def test_validate_looker_query_match_extra_fields(self):
    data = {
        "type": "looker-query-match",
        "params": {"model": "m1", "extra_field": "oops"},
        "weight": 1.0,
    }
    error = validate_assertion(data)
    self.assertIn("Extra inputs are not permitted", error)

  def test_validate_latency_max_ms_empty_value(self):
    data = {"type": "duration-max-ms", "value": "", "weight": 1.0}
    error = validate_assertion(data)
    self.assertIn("Input should be a valid number", error)


if __name__ == "__main__":
  unittest.main()
