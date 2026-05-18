"""Tests for the assertion engine."""

import unittest.mock
from prism.common.schemas.assertion import AIJudge
from prism.common.schemas.assertion import BaselineDataMatch
from prism.common.schemas.assertion import ChartCheckType
from prism.common.schemas.assertion import DataCheckRow
from prism.common.schemas.assertion import DataCheckRowCount
from prism.common.schemas.assertion import DurationMaxMs
from prism.common.schemas.assertion import LookerQueryMatch
from prism.common.schemas.assertion import QueryBaselineDataMatch
from prism.common.schemas.assertion import QueryContains
from prism.common.schemas.assertion import TextContains
from prism.common.schemas.trace import AskQuestionResponse
from prism.common.schemas.trace import DurationMetrics
from prism.server.services import assert_engine
from prism.server.services.assert_engine import AIJudgeResult


def make_response(messages=None, duration_ms=100):
  """Helper to create a mock AskQuestionResponse."""
  # messages should be list of dicts representing protobuf structure
  trace_data = messages or []
  return AskQuestionResponse(
      response=trace_data,
      duration=DurationMetrics(total_duration=duration_ms),
  )


def test_check_text_contains_pass():
  """Tests check_text_contains passing."""
  # Mock protobuf structure: system_message.text.parts = ["hello world"]
  trace = [{"system_message": {"text": {"parts": ["hello world"]}}}]
  response = make_response(trace)
  assertion = TextContains(value="hello")

  result = assert_engine.check_text_contains(response, assertion)

  assert result.passed
  assert result.score == 1.0
  assert "Found 'hello'" in result.reasoning


def test_check_text_contains_fail():
  """Tests check_text_contains failing."""
  trace = [{"system_message": {"text": {"parts": ["foo bar"]}}}]
  response = make_response(trace)
  assertion = TextContains(value="hello")

  result = assert_engine.check_text_contains(response, assertion)
  assert not result.passed
  assert result.score == 0.0


def test_check_text_contains_ignores_thought():
  """Tests that check_text_contains ignores THOUGHT text types."""
  trace = [{
      "system_message": {
          "text": {"parts": ["I am thinking..."], "text_type": "THOUGHT"}
      }
  }]
  response = make_response(trace)
  assertion = TextContains(value="thinking")

  result = assert_engine.check_text_contains(response, assertion)
  assert not result.passed

  assert not result.passed
  assert "Did not find 'thinking'" in result.reasoning


def test_check_query_contains_pass():
  """Tests check_query_contains passing."""
  trace = [{"system_message": {"data": {"generated_sql": "SELECT * FROM t"}}}]
  response = make_response(trace)
  assertion = QueryContains(value="SELECT *")

  result = assert_engine.check_query_contains(response, assertion)

  assert result.passed
  assert result.score == 1.0


def test_check_duration_max_ms_pass():
  """Tests check_duration_max_ms passing."""
  response = make_response(duration_ms=50)
  assertion = DurationMaxMs(value=100)

  result = assert_engine.check_duration_max_ms(response, assertion)

  assert result.passed
  assert result.score == 1.0


def test_check_data_row_count_pass():
  """Tests check_data_row_count passing."""
  # trace needs system_message.data.result.data list
  trace = [{
      "system_message": {
          "data": {"result": {"data": [{"col": "val"}, {"col": "val2"}]}}
      }
  }]
  response = make_response(trace)
  assertion = DataCheckRowCount(value=2)

  result = assert_engine.check_data_row_count(response, assertion)

  assert result.passed
  assert result.score == 1.0


def test_check_data_row_pass():
  """Tests check_data_row passing."""
  trace = [{
      "system_message": {
          "data": {
              "result": {
                  "data": [
                      {"id": 1, "name": "foo"},
                      {"id": 2, "name": "bar"},
                  ]
              }
          }
      }
  }]
  response = make_response(trace)
  assertion = DataCheckRow(columns={"id": 2, "name": "bar"})

  result = assert_engine.check_data_row(response, assertion)

  assert result.passed
  assert result.score == 1.0


def test_check_chart_type_pass():
  """Tests check_chart_type_pass."""
  trace = [{
      "system_message": {"chart": {"result": {"vega_config": {"mark": "bar"}}}}
  }]
  response = make_response(trace)
  assertion = ChartCheckType(value="bar")

  result = assert_engine.check_chart_type(response, assertion)

  assert result.passed


def test_normalize_filter_value():
  """Tests filter normalization logic."""
  # pylint: disable=protected-access
  # Base case
  assert assert_engine._normalize_filter_value("hello") == frozenset(["hello"])

  # URL encoding
  assert assert_engine._normalize_filter_value("hello+world") == frozenset(
      ["hello world"]
  )

  # Quotes
  assert assert_engine._normalize_filter_value('"foo bar"') == frozenset(
      ["foo bar"]
  )
  assert assert_engine._normalize_filter_value("'foo bar'") == frozenset(
      ["foo bar"]
  )

  # Commas (list/OR values)
  assert assert_engine._normalize_filter_value("a, b, c") == frozenset(
      ["a", "b", "c"]
  )

  # Escaped commas (Should not be split)
  assert assert_engine._normalize_filter_value("San Jose^, CA") == frozenset(
      ["San Jose, CA"]
  )

  # Combination
  assert assert_engine._normalize_filter_value(
      "110,+FULL+LINE+STORES"
  ) == frozenset(["110", "FULL LINE STORES"])
  assert assert_engine._normalize_filter_value(
      "110^, FULL LINE STORES"
  ) == frozenset(["110, FULL LINE STORES"])


def test_check_looker_query_match_pass():
  """Tests looker query match passing."""
  trace = [{
      "system_message": {
          "data": {
              "query": {
                  "looker": {
                      "model": "the_model",
                      "explore": "the_explore",
                      "fields": ["f1", "f2"],
                      "filters": [
                          {"field": "country", "value": "US, CA"},
                          {"field": "city", "value": "San Jose^, CA"},
                      ],
                  }
              }
          }
      }
  }]
  response = make_response(trace)

  # Full match
  assertion_full = LookerQueryMatch(
      params={
          "model": "the_model",
          "fields": ["f1"],
          "filters": [
              # Different order
              {"field": "country", "value": "CA, US"},
              # Different escaping/quotes
              {"field": "city", "value": '"San Jose, CA"'},
          ],
      }
  )
  result_full = assert_engine.check_looker_query_match(response, assertion_full)
  assert result_full.passed
  assert result_full.score == 1.0

  # Partial match
  assertion_partial = LookerQueryMatch(
      params={
          "model": "the_model",  # matches (1 pt)
          "limit": "100",  # misses (1 pt)
          "fields": ["f1", "f3"],  # misses (1 pt)
      }
  )
  result_partial = assert_engine.check_looker_query_match(
      response, assertion_partial
  )
  assert not result_partial.passed
  assert result_partial.score == 0.0
  assert "limit: expected" in result_partial.reasoning
  assert "fields: missing {'f3'}" in result_partial.reasoning


def test_check_chart_type_last_result():
  """Tests that check_chart_type uses the last chart result."""
  trace = [
      {
          "system_message": {
              "chart": {"result": {"vega_config": {"mark": {"type": "bar"}}}}
          }
      },
      {
          "system_message": {
              "chart": {"result": {"vega_config": {"mark": {"type": "line"}}}}
          }
      },
  ]
  response = make_response(trace)
  # Should match "line" (the last one), not "bar"
  assertion = ChartCheckType(value="line")
  result = assert_engine.check_chart_type(response, assertion)
  assert result.passed

  assertion_fail = ChartCheckType(value="bar")
  result_fail = assert_engine.check_chart_type(response, assertion_fail)
  assert not result_fail.passed

  assert result.passed


def test_evaluate_all():
  """Tests evaluate_all aggregator."""
  trace = [
      {"system_message": {"text": {"parts": ["hello"]}}},
      {"system_message": {"data": {"generated_sql": "SELECT 1"}}},
  ]
  response = make_response(trace, duration_ms=50)

  assertions = [
      TextContains(value="hello"),
      QueryContains(value="SELECT"),
      DurationMaxMs(value=100),
  ]

  results = assert_engine.evaluate_all(response, assertions)

  assert len(results) == 3
  assert all(r.passed for r in results)


def test_check_ai_judge_pass():
  """Tests check_ai_judge passing."""
  response = make_response([{"system_message": {"text": {"parts": ["hello"]}}}])
  assertion = AIJudge(value="The response should be hello")
  mock_llm = unittest.mock.MagicMock()

  mock_llm.generate_structured.return_value = AIJudgeResult(
      verdict=True, explanation="It said hello"
  )

  result = assert_engine.check_ai_judge(
      response, assertion, llm_client=mock_llm, question="Say hello"
  )

  assert result.passed
  assert result.score == 1.0
  assert result.reasoning == "It said hello"
  mock_llm.generate_structured.assert_called_once()


def test_canonical_cell_value():
  """Tests canonical cell value normalization."""
  # pylint: disable=protected-access
  precision = 2
  assert assert_engine._canonical_cell_value(None, precision) == "NULL"
  assert assert_engine._canonical_cell_value(float("nan"), precision) == "NULL"
  assert assert_engine._canonical_cell_value(123.456, precision) == "123.46"
  assert assert_engine._canonical_cell_value(123.000, precision) == "123"
  assert assert_engine._canonical_cell_value("123.456", precision) == "123.46"
  assert assert_engine._canonical_cell_value(" Hello ", precision) == "hello"
  assert assert_engine._canonical_cell_value("WORLD", precision) == "world"


def test_check_baseline_data_match_pass():
  """Tests baseline data match passing with flexible ordering."""
  agent_data = [
      {"id": 1, "val": 10.5},
      {"id": 2, "val": 20.0},
  ]
  trace = [{"system_message": {"data": {"result": {"data": agent_data}}}}]
  response = make_response(trace)

  # Baseline has different column order and different row order
  baseline_rows = [
      {"val": 20.0, "id": 2},
      {"val": 10.5, "id": 1},
  ]
  assertion = BaselineDataMatch(baseline_rows=baseline_rows)

  result = assert_engine.check_baseline_data_match(response, assertion)
  assert result.passed
  assert result.score == 1.0


def test_check_baseline_data_match_fail_values():
  """Tests baseline data match failing due to value mismatch."""
  agent_data = [{"id": 1, "val": 10.0}]
  trace = [{"system_message": {"data": {"result": {"data": agent_data}}}}]
  response = make_response(trace)

  baseline_rows = [{"id": 1, "val": 11.0}]
  assertion = BaselineDataMatch(baseline_rows=baseline_rows)

  result = assert_engine.check_baseline_data_match(response, assertion)
  assert not result.passed
  assert "Value mismatch" in result.reasoning


def test_check_baseline_data_match_fail_columns():
  """Tests baseline data match failing due to column count mismatch."""
  agent_data = [{"id": 1, "val": 10.0}]
  trace = [{"system_message": {"data": {"result": {"data": agent_data}}}}]
  response = make_response(trace)

  baseline_rows = [{"id": 1}]  # Missing 'val' column
  assertion = BaselineDataMatch(baseline_rows=baseline_rows)

  result = assert_engine.check_baseline_data_match(response, assertion)
  assert not result.passed
  assert "Column count mismatch" in result.reasoning


def test_check_query_baseline_data_match_pass():
  """Tests query baseline data match passing with mocked BQ."""
  agent_data = [{"id": 1, "val": 10.0}]
  trace = [{"system_message": {"data": {"result": {"data": agent_data}}}}]
  response = make_response(trace)

  assertion = QueryBaselineDataMatch(value="SELECT id, val FROM table")

  mock_bq = unittest.mock.MagicMock()
  mock_job = unittest.mock.MagicMock()
  mock_bq.query.return_value = mock_job
  # mock_job.result() returns an iterable of Row-like objects
  mock_job.result.return_value = [{"id": 1, "val": 10.0}]

  result = assert_engine.check_query_baseline_data_match(
      response, assertion, bq_client=mock_bq
  )

  assert result.passed
  assert result.score == 1.0
  mock_bq.query.assert_called_once_with("SELECT id, val FROM table")
  mock_job.result.assert_called_once_with(timeout=60)


def test_check_baseline_data_match_empty_pass():
  """Tests that baseline match passes when both datasets are empty."""
  agent_data = []
  trace = [{"system_message": {"data": {"result": {"data": agent_data}}}}]
  response = make_response(trace)

  assertion = BaselineDataMatch(baseline_rows=[])

  result = assert_engine.check_baseline_data_match(response, assertion)
  assert result.passed
  assert result.score == 1.0
  assert "matches baseline (0 rows, 0 columns)" in result.reasoning
