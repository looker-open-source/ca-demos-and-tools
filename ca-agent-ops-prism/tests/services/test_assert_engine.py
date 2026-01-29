import unittest.mock
from prism.common.schemas.assertion import AIJudge
from prism.common.schemas.assertion import ChartCheckType
from prism.common.schemas.assertion import DataCheckRow
from prism.common.schemas.assertion import DataCheckRowCount
from prism.common.schemas.assertion import DurationMaxMs
from prism.common.schemas.assertion import LookerQueryMatch
from prism.common.schemas.assertion import QueryContains
from prism.common.schemas.assertion import TextContains
from prism.common.schemas.trace import AskQuestionResponse
from prism.common.schemas.trace import DurationMetrics
from prism.server.services import assert_engine


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
                  }
              }
          }
      }
  }]
  response = make_response(trace)
  assertion = LookerQueryMatch(
      params={
          "model": "the_model",
          "fields": ["f1"],
      }
  )


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
  from prism.server.services.assert_engine import AIJudgeResult

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
