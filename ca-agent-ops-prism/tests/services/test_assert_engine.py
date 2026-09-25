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

"""Tests for the assertion engine."""

import unittest.mock
from prism.common.schemas.assertion import AIJudge
from prism.common.schemas.assertion import AssertionType
from prism.common.schemas.assertion import ChartCheckType
from prism.common.schemas.assertion import DataCheckRow
from prism.common.schemas.assertion import DataCheckRowCount
from prism.common.schemas.assertion import DurationMaxMs
from prism.common.schemas.assertion import LookerQueryMatch
from prism.common.schemas.assertion import MatchMode
from prism.common.schemas.assertion import QueryContains
from prism.common.schemas.assertion import TextContains
from prism.common.schemas.trace import AskQuestionResponse
from prism.common.schemas.trace import DurationMetrics
from prism.server.models.assertion import AssertionSnapshot
from prism.server.services import assert_engine
from prism.server.services import assertion_mappers
from prism.server.services.assert_engine import AIJudgeResult
import pydantic
import pytest


def make_response(messages=None, duration_ms=100):
  """A response carrying ``messages``, the dict form of a proto trace."""
  trace_data = messages or []
  return AskQuestionResponse(
      response=trace_data,
      duration=DurationMetrics(total_duration=duration_ms),
  )


def text_response(text, text_type=None):
  """A response whose final text is ``text``."""
  message = {"text": {"parts": [text]}}
  if text_type:
    message["text"]["text_type"] = text_type
  return make_response([{"system_message": message}])


def sql_response(sql):
  """A response whose generated SQL is ``sql``."""
  return make_response([{"system_message": {"data": {"generated_sql": sql}}}])


def test_check_text_contains_pass():
  trace = [{"system_message": {"text": {"parts": ["hello world"]}}}]
  response = make_response(trace)
  assertion = TextContains(value="hello")

  result = assert_engine.check_text_contains(response, assertion)

  assert result.passed
  assert result.score == 1.0
  assert "Found 'hello'" in result.reasoning


def test_check_text_contains_fail():
  trace = [{"system_message": {"text": {"parts": ["foo bar"]}}}]
  response = make_response(trace)
  assertion = TextContains(value="hello")

  result = assert_engine.check_text_contains(response, assertion)
  assert not result.passed
  assert result.score == 0.0


def test_check_text_contains_ignores_thought():
  trace = [{
      "system_message": {
          "text": {"parts": ["I am thinking..."], "text_type": "THOUGHT"}
      }
  }]
  response = make_response(trace)
  assertion = TextContains(value="thinking")

  result = assert_engine.check_text_contains(response, assertion)
  assert not result.passed
  assert "Did not find 'thinking'" in result.reasoning


def test_check_text_contains_ignores_progress():
  # PROGRESS text is streamed while the agent works. The trial view renders
  # FINAL_RESPONSE only, so matching it passes an assertion the response on
  # screen contradicts.
  trace = [
      {
          "system_message": {
              "text": {
                  "parts": ["Looking for orders over $500"],
                  "text_type": "PROGRESS",
              }
          }
      },
      {
          "system_message": {
              "text": {
                  "parts": ["There were no matching rows."],
                  "text_type": "FINAL_RESPONSE",
              }
          }
      },
  ]
  response = make_response(trace)

  progress = assert_engine.check_text_contains(
      response, TextContains(value="orders over $500")
  )
  final = assert_engine.check_text_contains(
      response, TextContains(value="no matching rows")
  )

  assert not progress.passed
  assert final.passed


def test_check_query_contains_pass():
  trace = [{"system_message": {"data": {"generated_sql": "SELECT * FROM t"}}}]
  response = make_response(trace)
  assertion = QueryContains(value="SELECT *")

  result = assert_engine.check_query_contains(response, assertion)

  assert result.passed
  assert result.score == 1.0


def test_check_text_contains_ignores_case():
  """The agent writes its own prose, so its casing is not the assertion's.

  Query contains has always matched case-insensitively. Text contains did not,
  which meant the same assertion behaved differently depending on which of the
  two you picked.
  """
  response = text_response("Total Revenue was $4.2M")
  assertion = TextContains(value="total revenue")

  result = assert_engine.check_text_contains(response, assertion)

  assert result.passed


def test_check_text_contains_matches_a_regex():
  """The value is a pattern when the mode says so."""
  response = text_response("There were 42 orders last week.")
  assertion = TextContains(value=r"\d+ orders", mode="regex")

  result = assert_engine.check_text_contains(response, assertion)

  assert result.passed
  assert result.score == 1.0
  assert r"Pattern '\d+ orders' matched response text." == result.reasoning


def test_check_text_contains_regex_that_does_not_match():
  """A pattern that misses reads as a pattern, not as a substring."""
  response = text_response("There were no orders last week.")
  assertion = TextContains(value=r"\d+ orders", mode="regex")

  result = assert_engine.check_text_contains(response, assertion)

  assert not result.passed
  assert "did not match" in result.reasoning


def test_check_text_contains_regex_is_not_read_as_a_substring():
  """Contains mode is still literal, so a pattern in it means itself."""
  response = text_response("There were 42 orders last week.")
  literal = TextContains(value=r"\d+ orders")

  result = assert_engine.check_text_contains(response, literal)

  assert not result.passed


def test_check_query_contains_matches_a_regex():
  """The SQL the agent writes varies in whitespace and aliasing."""
  response = sql_response("SELECT  SUM(amount)   AS total FROM orders")
  assertion = QueryContains(value=r"SUM\(\s*amount\s*\)", mode="regex")

  result = assert_engine.check_query_contains(response, assertion)

  assert result.passed


def test_check_query_contains_regex_ignores_case():
  """Same rule as contains mode, so switching modes is not a second surprise.

  A pattern that needs the case can still scope it back with (?-i:...).
  """
  response = sql_response("select sum(amount) from orders")
  assertion = QueryContains(value=r"SELECT SUM", mode="regex")

  result = assert_engine.check_query_contains(response, assertion)

  assert result.passed

  cased = QueryContains(value=r"(?-i:SELECT SUM)", mode="regex")
  assert not assert_engine.check_query_contains(response, cased).passed


def test_a_pattern_that_does_not_compile_cannot_be_built():
  """The engine does not guard the compile, so nothing may reach it unguarded.

  The schema is the only gate, and it has to hold on both construction and
  validation. An AssertionResult carrying a bad pattern is rejected too, so a
  guard in the engine would have nothing to return.
  """
  with pytest.raises(pydantic.ValidationError):
    QueryContains(value="SELECT (", mode="regex")


def test_a_snapshot_saved_before_the_mode_existed_still_matches_literally():
  """Every assertion snapshot written before regex mode has no mode in params.

  The snapshots are immutable, so the old rows stay as they were written and a
  rerun of an old suite hydrates them through this path. The default has to
  stay CONTAINS. Under REGEX a stored value with a paren or a dollar sign would
  either stop matching or fail to compile, and the run would report the suite
  as broken rather than the agent.
  """
  legacy = AssertionSnapshot(
      id=1,
      example_snapshot_id=1,
      original_assertion_id=1,
      type=AssertionType.TEXT_CONTAINS,
      weight=1.0,
      params={"value": "Total revenue (USD)"},
  )

  assertion = assertion_mappers.snapshot_model_to_schema(legacy)
  result = assert_engine.evaluate_all(
      text_response("Total revenue (USD) was $4.2M last quarter."), [assertion]
  )[0]

  assert assertion.mode == MatchMode.CONTAINS
  assert result.passed


def test_check_duration_max_ms_pass():
  response = make_response(duration_ms=50)
  assertion = DurationMaxMs(value=100)

  result = assert_engine.check_duration_max_ms(response, assertion)

  assert result.passed
  assert result.score == 1.0


def test_check_data_row_count_pass():
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


def data_response(rows):
  """Helper to create a response whose last data result is ``rows``."""
  return make_response(
      [{"system_message": {"data": {"result": {"data": rows}}}}]
  )


def test_check_data_row_ignores_column_name_case():
  """The agent aliases the column, so the assertion cannot rely on its case.

  An assertion written for Total_Sales used to fail against a query that
  returned total_sales, which looks like a wrong answer and is not.
  """
  response = data_response([{"total_sales": 100}])
  assertion = DataCheckRow(columns={"Total_Sales": 100})

  result = assert_engine.check_data_row(response, assertion)

  assert result.passed
  assert result.score == 1.0


def test_check_data_row_prefers_the_exact_column_name():
  """A row carrying both spellings must not be ambiguous."""
  response = data_response([{"Total_Sales": 100, "total_sales": 999}])
  assertion = DataCheckRow(columns={"Total_Sales": 100})

  result = assert_engine.check_data_row(response, assertion)

  assert result.passed


def test_check_data_row_reports_a_column_the_query_never_returned():
  """The fix for a missing column is to change the SQL, not the value."""
  response = data_response([{"id": 1, "name": "foo"}])
  assertion = DataCheckRow(columns={"revenue": 100})

  result = assert_engine.check_data_row(response, assertion)

  assert not result.passed
  assert "'revenue'" in result.reasoning
  assert "not in the result" in result.reasoning
  # The columns that were returned, so the fix does not need a second run.
  assert "'id'" in result.reasoning
  assert "'name'" in result.reasoning


def test_check_data_row_reports_how_the_closest_row_differed():
  """The column is there and the value is wrong. A different fix."""
  response = data_response([
      {"id": 1, "name": "foo"},
      {"id": 2, "name": "bar"},
  ])
  assertion = DataCheckRow(columns={"id": 2, "name": "baz"})

  result = assert_engine.check_data_row(response, assertion)

  assert not result.passed
  assert "not in the result" not in result.reasoning
  assert "differed on:" in result.reasoning
  # The row that matched on id is the closest one, so name is the only miss.
  assert "name: expected 'baz', got 'bar'" in result.reasoning
  assert "id:" not in result.reasoning.split("differed on:")[1]


def test_check_data_row_separates_a_null_column_from_a_missing_one():
  """A column present and null is a value mismatch, not a missing column."""
  response = data_response([{"id": 1, "revenue": None}])
  assertion = DataCheckRow(columns={"revenue": 100})

  result = assert_engine.check_data_row(response, assertion)

  assert not result.passed
  assert "not in the result" not in result.reasoning
  assert "got None" in result.reasoning


def test_check_data_row_handles_a_column_missing_from_only_some_rows():
  """A Struct row drops its nulls, so rows are not always the same shape."""
  response = data_response([{"id": 1}, {"id": 2, "revenue": 100}])
  assertion = DataCheckRow(columns={"revenue": 100})

  result = assert_engine.check_data_row(response, assertion)

  assert result.passed


def test_check_data_row_without_a_data_result():
  """Nothing to compare against reads differently from a bad comparison."""
  response = make_response([{"system_message": {"text": {"parts": ["hi"]}}}])
  assertion = DataCheckRow(columns={"id": 1})

  result = assert_engine.check_data_row(response, assertion)

  assert not result.passed
  assert result.reasoning == "No data result found in trace."


def test_check_data_row_separates_an_empty_result_from_no_result():
  """A query that returned nothing is not an agent that never queried.

  Both used to read "No data result found in trace", which sent the reader
  looking for a query the trace already holds. The fixes are different: one is
  the agent's plan, the other is the filter or the data behind it.
  """
  response = data_response([])
  assertion = DataCheckRow(columns={"id": 1})

  result = assert_engine.check_data_row(response, assertion)

  assert not result.passed
  assert "No data result found in trace" not in result.reasoning
  assert "returned no rows" in result.reasoning


def test_check_data_row_ignores_surrounding_whitespace():
  """Expected values are pasted out of spreadsheets, spaces and all."""
  response = data_response([{"city": "San Jose"}])
  assertion = DataCheckRow(columns={"city": "San Jose "})

  result = assert_engine.check_data_row(response, assertion)

  assert result.passed


def test_check_chart_type_pass():
  trace = [{
      "system_message": {"chart": {"result": {"vega_config": {"mark": "bar"}}}}
  }]
  response = make_response(trace)
  assertion = ChartCheckType(value="bar")

  result = assert_engine.check_chart_type(response, assertion)

  assert result.passed


def test_check_chart_type_ignores_case():
  """The mark comes out of the agent's Vega spec, which picks its own case."""
  trace = [{
      "system_message": {"chart": {"result": {"vega_config": {"mark": "Bar"}}}}
  }]
  response = make_response(trace)
  assertion = ChartCheckType(value="bar")

  result = assert_engine.check_chart_type(response, assertion)

  assert result.passed


def test_normalize_filter_value_keeps_an_apostrophe_inside_a_word():
  """An apostrophe used to open a quote, which ate it and the next comma.

  "Smith, O'Brien" and "O'Brien, Smith" then normalized to different sets, and
  "Bob's Burgers" matched "Bobs Burgers".
  """
  # pylint: disable=protected-access
  normalize = assert_engine._normalize_filter_value

  assert normalize("Smith, O'Brien") == normalize("O'Brien, Smith")
  assert normalize("Smith, O'Brien") == frozenset(["Smith", "O'Brien"])
  assert normalize("Bob's Burgers") != normalize("Bobs Burgers")


def test_normalize_filter_value_still_quotes_a_quoted_value():
  """A quote at the start of a value quotes it, comma and all."""
  # pylint: disable=protected-access
  normalize = assert_engine._normalize_filter_value

  assert normalize('a, "b, c"') == frozenset(["a", "b, c"])
  assert normalize("'San Jose, CA'") == frozenset(["San Jose, CA"])


def test_normalize_filter_value():
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

  # Escaped commas, which are not split.
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

  # Partial match. One key of the three matches, which is under
  # LOOKER_QUERY_MATCH_THRESHOLD, so the whole assertion scores zero. There is
  # no partial credit here.
  assertion_partial = LookerQueryMatch(
      params={
          "model": "the_model",  # matches
          "limit": "100",  # misses
          "fields": ["f1", "f3"],  # misses
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
  # An agent can draw more than one chart. The assertion reads the last.
  assertion = ChartCheckType(value="line")
  result = assert_engine.check_chart_type(response, assertion)
  assert result.passed

  assertion_fail = ChartCheckType(value="bar")
  result_fail = assert_engine.check_chart_type(response, assertion_fail)
  assert not result_fail.passed


def test_evaluate_all():
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
