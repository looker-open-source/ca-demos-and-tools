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

"""Functional assertion logic for evaluating AskQuestionResponse."""

import json
from typing import Any

from google.cloud import geminidataanalytics
from prism.common.schemas.assertion import AIJudge
from prism.common.schemas.assertion import Assertion
from prism.common.schemas.assertion import AssertionType
from prism.common.schemas.assertion import ChartCheckType
from prism.common.schemas.assertion import DataCheckRow
from prism.common.schemas.assertion import DataCheckRowCount
from prism.common.schemas.assertion import DurationMaxMs
from prism.common.schemas.assertion import LatencyMaxMs
from prism.common.schemas.assertion import LookerQueryMatch
from prism.common.schemas.assertion import QueryContains
from prism.common.schemas.assertion import TextContains
from prism.common.schemas.execution import AssertionResult
from prism.common.schemas.trace import AskQuestionResponse
import pydantic


LOOKER_QUERY_MATCH_THRESHOLD = 0.75


def check_text_contains(
    response: AskQuestionResponse, assertion: TextContains
) -> AssertionResult:
  """Checks if the result text contains a value."""
  if not assertion.value:
    return AssertionResult(
        assertion=assertion,
        passed=False,
        score=0.0,
        reasoning="Assert value is empty.",
    )

  final_response_parts = []
  for message in response.protobuf_response:
    # Check if system_message is present
    if "system_message" in message:
      sys_msg = message.system_message
      # Check if text is present
      if "text" in sys_msg:
        # Filter out THOUGHT/PROGRESS
        text_type = sys_msg.text.text_type
        if text_type not in [
            geminidataanalytics.TextMessage.TextType.THOUGHT,
        ]:
          final_response_parts.append(sys_msg.text.parts)

  # Join all parts. Note: parts is likely a repeated string field or list.
  # If it's a list of strings:
  full_text = " ".join([" ".join(parts) for parts in final_response_parts])

  if assertion.value in full_text:
    return AssertionResult(
        assertion=assertion,
        passed=True,
        score=1.0,
        reasoning=f"Found '{assertion.value}' in response text.",
    )
  return AssertionResult(
      assertion=assertion,
      passed=False,
      score=0.0,
      reasoning=f"Did not find '{assertion.value}' in response text.",
  )


def check_query_contains(
    response: AskQuestionResponse, assertion: QueryContains
) -> AssertionResult:
  """Checks if the generated query contains a value."""
  if not assertion.value:
    return AssertionResult(
        assertion=assertion,
        passed=False,
        score=0.0,
        reasoning="Assert value is empty.",
    )

  all_query_text = []
  for message in response.protobuf_response:
    if "system_message" in message:
      sys_msg = message.system_message
      if "data" in sys_msg:
        data_msg = sys_msg.data
        if "generated_sql" in data_msg:
          all_query_text.append(data_msg.generated_sql)
        if "query" in data_msg:
          # Serialize structured query to string for searching
          # We use json_format to converting proto message to dict then dump
          query_dict = type(data_msg.query).to_dict(data_msg.query)
          all_query_text.append(json.dumps(query_dict))

  combined_text = " ".join(all_query_text)

  if assertion.value.lower() in combined_text.lower():
    return AssertionResult(
        assertion=assertion,
        passed=True,
        score=1.0,
        reasoning=f"Found '{assertion.value}' in generated query/SQL.",
    )
  return AssertionResult(
      assertion=assertion,
      passed=False,
      score=0.0,
      reasoning=f"Did not find '{assertion.value}' in generated query/SQL.",
  )


def check_duration_max_ms(
    response: AskQuestionResponse, assertion: DurationMaxMs
) -> AssertionResult:
  """Checks if duration is below a threshold."""
  duration = response.duration.total_duration
  if duration <= assertion.value:
    return AssertionResult(
        assertion=assertion,
        passed=True,
        score=1.0,
        reasoning=(
            f"Duration {duration}ms is within limit of {assertion.value}ms."
        ),
    )
  return AssertionResult(
      assertion=assertion,
      passed=False,
      score=0.0,
      reasoning=f"Duration {duration}ms exceeded limit of {assertion.value}ms.",
  )


def check_latency_max_ms(
    response: AskQuestionResponse, assertion: LatencyMaxMs
) -> AssertionResult:
  """Checks if latency is below a threshold (Deprecated: Use duration)."""
  # Reuse duration logic
  return check_duration_max_ms(response, assertion)


def _get_last_data_result(
    response: AskQuestionResponse,
) -> list[dict[str, Any]] | None:
  """Retrieves the last data result from the response, if any."""
  for message in reversed(response.protobuf_response):
    if "system_message" in message:
      sys_msg = message.system_message
      if "data" in sys_msg and "result" in sys_msg.data:
        # sys_msg.data.result.data is a repeated Struct (ListValue equivalent)
        # Convert to list of dicts
        return [dict(row) for row in sys_msg.data.result.data]
  return None


def check_data_row_count(
    response: AskQuestionResponse, assertion: DataCheckRowCount
) -> AssertionResult:
  """Checks the number of rows in the result."""
  last_result_rows = _get_last_data_result(response)

  if last_result_rows is None:
    return AssertionResult(
        assertion=assertion,
        passed=False,
        score=0.0,
        reasoning="No data result found in trace.",
    )

  count = len(last_result_rows)
  if count == assertion.value:
    return AssertionResult(
        assertion=assertion,
        passed=True,
        score=1.0,
        reasoning=f"Row count {count} matches expected {assertion.value}.",
    )
  return AssertionResult(
      assertion=assertion,
      passed=False,
      score=0.0,
      reasoning=f"Row count {count} does not match expected {assertion.value}.",
  )


def _values_match(actual: Any, expected: Any) -> bool:
  """Checks if two values match, handling loose numeric equality."""
  if str(actual) == str(expected):
    return True
  try:
    if float(actual) == float(expected):
      return True
  except (ValueError, TypeError):
    pass
  return False


def check_data_row(
    response: AskQuestionResponse, assertion: DataCheckRow
) -> AssertionResult:
  """Checks if a row with specific column values exists."""
  if not assertion.columns:
    return AssertionResult(
        assertion=assertion,
        passed=False,
        score=0.0,
        reasoning="Assert columns are empty.",
    )

  found_match = False
  data_rows = _get_last_data_result(response)

  if not data_rows:
    return AssertionResult(
        assertion=assertion,
        passed=False,
        score=0.0,
        reasoning="No data result found in trace.",
    )

  for row in data_rows:
    row_match = True
    for key, val in assertion.columns.items():
      row_val = row.get(key)
      if not _values_match(row_val, val):
        row_match = False
        break
    if row_match:
      found_match = True
      break

  if found_match:
    return AssertionResult(
        assertion=assertion,
        passed=True,
        score=1.0,
        reasoning=f"Found row matching {assertion.columns}.",
    )
  return AssertionResult(
      assertion=assertion,
      passed=False,
      score=0.0,
      reasoning=f"No row found matching {assertion.columns}.",
  )


def check_chart_type(
    response: AskQuestionResponse, assertion: ChartCheckType
) -> AssertionResult:
  """Checks if the chart type matches."""
  last_chart_type = None

  for message in reversed(response.protobuf_response):
    if "system_message" in message:
      sys_msg = message.system_message
      if "chart" in sys_msg and "result" in sys_msg.chart:
        # vega_config is generic Struct
        vega = dict(sys_msg.chart.result.vega_config)
        # Vega-Lite spec: 'mark' can be string or dict
        mark = vega.get("mark")
        # Handle MapComposite (proto-plus) which acts like a dict but isn't
        # always satisfying isinstance(x, dict) or needs explicit conversion
        if hasattr(mark, "get"):
          last_chart_type = mark.get("type")
        else:
          last_chart_type = mark
        break

  if not last_chart_type:
    return AssertionResult(
        assertion=assertion,
        passed=False,
        score=0.0,
        reasoning="No chart result found.",
    )

  if last_chart_type == assertion.value:
    return AssertionResult(
        assertion=assertion,
        passed=True,
        score=1.0,
        reasoning=(
            f"Chart type '{last_chart_type}' matches '{assertion.value}'."
        ),
    )
  return AssertionResult(
      assertion=assertion,
      passed=False,
      score=0.0,
      reasoning=(
          f"Chart type '{last_chart_type}' does not match '{assertion.value}'."
      ),
  )


def _normalize_filter_value(val: str) -> frozenset[str]:
  """Normalizes a Looker filter value for order-independent comparison.

  Args:
    val: The Looker filter value string to normalize.

  Returns:
    A frozenset of the normalized filter values.

  - Replaces URL-encoded spaces (+) with actual spaces.
  - Splits by unescaped commas to handle list/OR values.
  - Respects quotes (commas inside quotes are not split).
  - Replaces escaped commas (^,) with literal commas.
  """
  if not val:
    return frozenset()

  # Replace URL-encoded spaces
  val = val.replace("+", " ")

  # Strip whitespace from the entire string
  val = val.strip()

  parts = []
  current_part = []
  in_quotes = False
  i = 0
  while i < len(val):
    char = val[i]
    if char == "^":
      # Escape next character
      if i + 1 < len(val):
        current_part.append(val[i + 1])
        i += 1
      else:
        current_part.append(char)
    elif char == '"' or char == "'":
      # Toggle quotes
      in_quotes = not in_quotes
      # Do not append the quote character itself to the final value
    elif char == "," and not in_quotes:
      # Split point
      parts.append("".join(current_part).strip())
      current_part = []
    else:
      current_part.append(char)

    i += 1

  parts.append("".join(current_part).strip())

  # Filter out empty parts
  normalized = [p for p in parts if p]
  return frozenset(normalized)


def check_looker_query_match(
    response: AskQuestionResponse, assertion: LookerQueryMatch
) -> AssertionResult:
  """Checks if any Looker query matches parameters, with partial scoring."""
  if not assertion.params:
    return AssertionResult(
        assertion=assertion,
        passed=False,
        score=0.0,
        reasoning="Assert params are empty.",
    )

  found_queries = []
  for message in response.protobuf_response:
    if "system_message" in message:
      sys_msg = message.system_message
      if "data" in sys_msg and "query" in sys_msg.data:
        if "looker" in sys_msg.data.query:
          found_queries.append(
              type(sys_msg.data.query.looker).to_dict(sys_msg.data.query.looker)
          )

  if not found_queries:
    return AssertionResult(
        assertion=assertion,
        passed=False,
        score=0.0,
        reasoning="No Looker query found in trace.",
    )

  p = assertion.params

  # Calculate total possible points based on defined expected parameters
  total_points = 0
  if p.model is not None:
    total_points += 1
  if p.explore is not None:
    total_points += 1
  if p.limit is not None:
    total_points += 1
  if p.fields:
    total_points += 1
  if p.sorts:
    total_points += 1
  if p.filters:
    total_points += 1

  if total_points == 0:
    return AssertionResult(
        assertion=assertion,
        passed=True,
        score=1.0,
        reasoning="No specific Looker Query Match criteria defined.",
    )

  best_score = -1.0
  best_reasons = []

  for query in found_queries:
    earned_points = 0.0
    current_reasons = []

    # 1. Exact Match
    if p.model is not None:
      actual_model = str(query.get("model"))
      if actual_model == str(p.model):
        earned_points += 1.0
      else:
        current_reasons.append(
            f"model: expected '{p.model}', got '{actual_model}'"
        )

    if p.explore is not None:
      actual_explore = str(query.get("explore"))
      if actual_explore == str(p.explore):
        earned_points += 1.0
      else:
        current_reasons.append(
            f"explore: expected '{p.explore}', got '{actual_explore}'"
        )

    if p.limit is not None:
      actual_limit = str(query.get("limit"))
      if actual_limit == str(p.limit):
        earned_points += 1.0
      else:
        current_reasons.append(
            f"limit: expected '{p.limit}', got '{actual_limit}'"
        )

    # 2. Subset Match (Lists)
    if p.fields:
      expected_fields = set(p.fields)
      actual_fields = set(query.get("fields", []))
      if expected_fields.issubset(actual_fields):
        earned_points += 1.0
      else:
        current_reasons.append(
            f"fields: missing {expected_fields - actual_fields}"
        )

    if p.sorts:
      expected_sorts = set(p.sorts)
      actual_sorts = set(query.get("sorts", []))
      if expected_sorts.issubset(actual_sorts):
        earned_points += 1.0
      else:
        current_reasons.append(
            f"sorts: missing {expected_sorts - actual_sorts}"
        )

    # 3. Filters
    if p.filters:
      # Normalize expected filters
      expected_filters = {
          (f.field, _normalize_filter_value(str(f.value))) for f in p.filters
      }

      # Actual data from trace remains raw/varied
      actual_filters_raw = query.get("filters", [])
      actual_filters = set()
      if isinstance(actual_filters_raw, list):
        for f in actual_filters_raw:
          if isinstance(f, dict):
            field = f.get("field")
            value = f.get("value")
            if field and value is not None:
              actual_filters.add(
                  (str(field), _normalize_filter_value(str(value)))
              )
      elif isinstance(actual_filters_raw, dict):
        for k, v in actual_filters_raw.items():
          actual_filters.add((str(k), _normalize_filter_value(str(v))))

      missing = expected_filters - actual_filters
      if not missing:
        earned_points += 1.0
      else:
        # Simplify display of missing filters
        missing_str = ", ".join(f"{f}='{{{','.join(v)}}}'" for f, v in missing)
        current_reasons.append(f"filters: missing {missing_str}")

    score = earned_points / total_points
    if score > best_score:
      best_score = score
      best_reasons = current_reasons

  passed = best_score >= LOOKER_QUERY_MATCH_THRESHOLD
  final_score = 1.0 if passed else 0.0
  if passed:
    if best_score == 1.0:
      reasoning = "Found Looker query matching all criteria."
    else:
      reasoning = (
          "Found Looker query matching most criteria (Match Rate:"
          f" {best_score:.2f}). Minor mismatches: {'; '.join(best_reasons)}"
      )
  elif best_score > 0.0:
    reasoning = (
        f"Mismatches (Match Rate: {best_score:.2f}): {'; '.join(best_reasons)}"
    )
  else:
    reasons_str = "; ".join(best_reasons)
    reasoning = (
        "No matching Looker query criteria (Match Rate: 0.00). Failures:"
        f" {reasons_str}"
    )

  return AssertionResult(
      assertion=assertion,
      passed=passed,
      score=final_score,
      reasoning=reasoning,
  )


class AIJudgeResult(pydantic.BaseModel):
  """Result of an AI judge evaluation."""

  verdict: bool = pydantic.Field(
      ...,
      description="True if the assertion is met, False otherwise.",
  )
  explanation: str = pydantic.Field(
      ...,
      description="A clear and concise explanation of the reasoning.",
  )


def check_ai_judge(
    response: AskQuestionResponse,
    assertion: AIJudge,
    llm_client: Any | None = None,
    question: str | None = None,
) -> AssertionResult:
  """Evaluates the response using an LLM based on criteria."""
  if not llm_client:
    return AssertionResult(
        assertion=assertion,
        passed=False,
        score=0.0,
        reasoning="LLM client not provided for AI Judge.",
    )

  if not question:
    return AssertionResult(
        assertion=assertion,
        passed=False,
        score=0.0,
        reasoning="User question not provided for AI Judge.",
    )

  # Rehydrate trace as JSON string
  trace = "\n".join(json.dumps(m, indent=2) for m in response.response)

  prompt = f"""
You are an expert evaluator for a data agent system. Your task is to assess
whether the system's generated trace correctly addresses the User Question,
specifically in relation to a given Assertion.

**User Question:**
---
{question}
---

**System Trace:**
---
{trace}
---

**Assertion to Evaluate:**
---
{assertion.value}
---

**TASK:**
Carefully analyze the System Trace in the context of the User Question.
Determine if the System Trace fulfills the condition stated in the Assertion.
Return a boolean verdict and a concise explanation.
"""

  try:
    result = llm_client.generate_structured(prompt, AIJudgeResult)
    if not result:
      return AssertionResult(
          assertion=assertion,
          passed=False,
          score=0.0,
          reasoning="LLM failed to generate a verdict.",
      )

    return AssertionResult(
        assertion=assertion,
        passed=result.verdict,
        score=1.0 if result.verdict else 0.0,
        reasoning=result.explanation,
    )
  except Exception as e:  # pylint: disable=broad-exception-caught
    return AssertionResult(
        assertion=assertion,
        passed=False,
        score=0.0,
        reasoning=f"Error during AI Judge evaluation: {str(e)}",
    )


def evaluate_all(
    response: AskQuestionResponse,
    assertions: list[Assertion],
    llm_client: Any | None = None,
    question: str | None = None,
) -> list[AssertionResult]:
  """Evaluates a list of assertions against a response."""
  results = []
  for assertion in assertions:
    match assertion.type:
      case AssertionType.TEXT_CONTAINS:
        results.append(check_text_contains(response, assertion))
      case AssertionType.QUERY_CONTAINS:
        results.append(check_query_contains(response, assertion))
      case AssertionType.DURATION_MAX_MS:
        results.append(check_duration_max_ms(response, assertion))
      case AssertionType.LATENCY_MAX_MS:
        results.append(check_latency_max_ms(response, assertion))
      case AssertionType.DATA_CHECK_ROW_COUNT:
        results.append(check_data_row_count(response, assertion))
      case AssertionType.DATA_CHECK_ROW:
        results.append(check_data_row(response, assertion))
      case AssertionType.CHART_CHECK_TYPE:
        results.append(check_chart_type(response, assertion))
      case AssertionType.LOOKER_QUERY_MATCH:
        results.append(check_looker_query_match(response, assertion))
      case AssertionType.AI_JUDGE:
        results.append(
            check_ai_judge(response, assertion, llm_client, question)
        )
      case _:
        results.append(
            AssertionResult(
                assertion=assertion,
                passed=False,
                score=0.0,
                reasoning=f"Unsupported assert type: {assertion.type}",
            )
        )
  return results
