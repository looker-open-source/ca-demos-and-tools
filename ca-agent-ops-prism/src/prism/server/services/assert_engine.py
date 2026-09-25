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
import logging
import multiprocessing
import re
import signal
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
from prism.common.schemas.assertion import MatchMode
from prism.common.schemas.assertion import QueryContains
from prism.common.schemas.assertion import TextContains
from prism.common.schemas.execution import AssertionResult
from prism.common.schemas.trace import AskQuestionResponse
import pydantic

logger = logging.getLogger(__name__)

LOOKER_QUERY_MATCH_THRESHOLD = 0.75

# How much of the trace the AI judge prompt may carry. The trace holds every
# event of the trial, and a single data event with a 4,000 row answer in it is
# millions of tokens, which the model rejects. Events are in the order they
# happened, so the cut falls at the end of the trial.
AI_JUDGE_TRACE_CHAR_BUDGET = 20000

# How long a single regex assertion may run. A pattern comes from a test case,
# so it is user input, and re has no execution limit of its own. One with
# nested quantifiers backtracks exponentially, which takes the worker with it.
# No real pattern needs anywhere near this long against a trace.
REGEX_TIMEOUT_SECONDS = 5

# How long the child process below gets to come up before the search it was
# spawned for is considered lost. A spawned interpreter re-imports this module
# and the client libraries under it, which is two or three seconds warm and
# more than that on a container that has just started. That is not the
# pattern's time, so it is not taken out of the pattern's budget.
CHILD_STARTUP_SECONDS = 60


def _search(pattern: str, text: str) -> bool:
  """Runs one regex search, with no bound of its own."""
  return re.search(pattern, text, re.IGNORECASE) is not None


def _search_in_child(pattern: str, text: str, answer: Any) -> None:
  """Entry point of the child process, which sends the answer down the pipe."""
  # Sent before the match starts, and down a pipe rather than a queue: a queue
  # hands the write to a feeder thread, and that thread does not run again
  # until re gives the GIL back, which is the thing being waited on.
  answer.send(None)
  answer.send(_search(pattern, text))


def _search_in_process(pattern: str, text: str) -> bool:
  """Runs one regex search in a child process, and kills it on the deadline.

  The only way to stop a running match is to stop the interpreter running it.
  A thread cannot do it: re holds the GIL for the whole match, so a waiting
  thread is not scheduled until the match it is waiting on has finished.

  The deadline runs from the child's first message, not from the spawn, so
  startup gets its own budget. Charging the import to the pattern failed
  patterns that had not started yet.

  Raises:
    TimeoutError: if the search outran REGEX_TIMEOUT_SECONDS, if the child
      never came up, or if the child exited without answering.
  """
  ctx = multiprocessing.get_context("spawn")
  reader, writer = ctx.Pipe(duplex=False)
  child = ctx.Process(
      target=_search_in_child, args=(pattern, text, writer), daemon=True
  )
  child.start()
  writer.close()

  def receive(timeout: float, whats_wrong: str) -> Any:
    if not reader.poll(timeout):
      raise TimeoutError(whats_wrong)
    try:
      return reader.recv()
    except EOFError as gone:
      # The parent closed its write end above, so a child that exits without
      # answering leaves the pipe at EOF: poll returns True at once and recv
      # raises. A memory capped playground instance killed the spawned
      # interpreter while it was still importing, and the EOFError came out of
      # evaluate_all and took every other assertion's result with it.
      raise TimeoutError("the search process died before it answered") from gone

  try:
    receive(
        CHILD_STARTUP_SECONDS,
        f"the search process did not start within {CHILD_STARTUP_SECONDS}s",
    )
    return receive(
        REGEX_TIMEOUT_SECONDS,
        f"did not finish within {REGEX_TIMEOUT_SECONDS}s",
    )
  finally:
    # Terminated whether it answered or not. A child that has already exited
    # does not mind, and one that is still backtracking would otherwise hold a
    # core for as long as the pattern takes.
    child.terminate()
    child.join()
    reader.close()


def _search_with_deadline(pattern: str, text: str) -> bool:
  """Runs one regex search under a wall clock deadline.

  re holds the GIL while it matches, so a thread cannot time it out. SIGALRM
  can: the engine checks for signals as it runs. A handler can only be
  installed on the main thread, and the playground evaluates its assertions on
  a Dash request thread, so that path pays for a child process instead. A
  trial runs on the main thread of its own worker process and takes the cheap
  route.

  Raises:
    TimeoutError: if the search outran REGEX_TIMEOUT_SECONDS.
  """
  deadline_live = True

  def expired(signum, frame):
    del signum, frame
    # The alarm can still be delivered a few instructions after the search
    # returned. Raising then took the TimeoutError out of the finally below
    # before the handler had been put back, so the next SIGALRM the process
    # took raised out of whatever was running at the time.
    if deadline_live:
      raise TimeoutError(f"did not finish within {REGEX_TIMEOUT_SECONDS}s")

  try:
    previous = signal.signal(signal.SIGALRM, expired)
  except ValueError:
    return _search_in_process(pattern, text)

  signal.setitimer(signal.ITIMER_REAL, REGEX_TIMEOUT_SECONDS)
  try:
    return _search(pattern, text)
  finally:
    deadline_live = False
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, previous)


def _contains_result(
    text: str, assertion: TextContains | QueryContains, where: str
) -> AssertionResult:
  """Runs one contains assertion against the text it was scoped to.

  Both modes ignore case. The agent picks the casing of its own prose and of
  the SQL it emits, so an assertion that cared would fail on a rewording that
  changed nothing. A pattern can opt back in with (?-i:...).
  """
  if assertion.mode == MatchMode.REGEX:
    # The schema rejects a pattern that does not compile, so the only failure
    # left here is one that never finishes.
    try:
      found = _search_with_deadline(assertion.value, text)
    except TimeoutError as timeout:
      # The exception carries what went wrong. A pattern that outran its
      # budget, a child that never started and a child that died all read the
      # same from here, and only the first is the author's fault.
      return AssertionResult(
          assertion=assertion,
          passed=False,
          score=0.0,
          reasoning=f"Pattern '{assertion.value}' against {where}: {timeout}.",
      )
    reasoning = (
        f"Pattern '{assertion.value}' {'matched' if found else 'did not match'}"
        f" {where}."
    )
  else:
    found = assertion.value.casefold() in text.casefold()
    reasoning = (
        f"{'Found' if found else 'Did not find'} '{assertion.value}' in"
        f" {where}."
    )

  return AssertionResult(
      assertion=assertion,
      passed=found,
      score=1.0 if found else 0.0,
      reasoning=reasoning,
  )


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
    if "system_message" in message:
      sys_msg = message.system_message
      if "text" in sys_msg:
        # Filter out THOUGHT/PROGRESS. Progress text is streamed while the agent
        # works and isn't part of the answer the user sees, so matching it would
        # pass an assertion the rendered response contradicts.
        text_type = sys_msg.text.text_type
        if text_type not in [
            geminidataanalytics.TextMessage.TextType.THOUGHT,
            geminidataanalytics.TextMessage.TextType.PROGRESS,
        ]:
          final_response_parts.append(sys_msg.text.parts)

  # parts is a repeated string field, so flatten before joining.
  full_text = " ".join([" ".join(parts) for parts in final_response_parts])

  return _contains_result(full_text, assertion, "response text")


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
          # Serialize the structured query so a contains check can search it.
          # to_dict gives a plain dict, which json.dumps can render.
          query_dict = type(data_msg.query).to_dict(data_msg.query)
          all_query_text.append(json.dumps(query_dict))

  combined_text = " ".join(all_query_text)

  return _contains_result(combined_text, assertion, "generated query/SQL")


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
  # Stripped, because an expected value typed into a cell of a CSV keeps the
  # space after the comma it was pasted next to, and no result ever has one.
  if str(actual).strip() == str(expected).strip():
    return True
  try:
    if float(actual) == float(expected):
      return True
  except (ValueError, TypeError):
    pass
  return False


_MISSING = object()


def _lookup_column(row: dict[str, Any], key: str) -> Any:
  """Reads a column out of a result row, ignoring the case of its name.

  The column name comes from whatever the agent's SQL aliased, so an assertion
  written for `Total_Sales` used to miss a column returned as `total_sales`.
  An exact match still wins, so a result carrying both names is unambiguous.

  Returns ``_MISSING`` when there is no such column, which a None value is not.
  """
  if key in row:
    return row[key]
  folded = key.casefold()
  for actual, value in row.items():
    if str(actual).casefold() == folded:
      return value
  return _MISSING


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

  data_rows = _get_last_data_result(response)

  if data_rows is None:
    return AssertionResult(
        assertion=assertion,
        passed=False,
        score=0.0,
        reasoning="No data result found in trace.",
    )

  if not data_rows:
    # An agent that never queried and a query that came back empty both used
    # to read "No data result found in trace". The first is a question the
    # agent answered from its own prose; the second is a filter or a dataset
    # to go and look at. Different fixes, so different messages.
    return AssertionResult(
        assertion=assertion,
        passed=False,
        score=0.0,
        reasoning=(
            "The query returned no rows, so no row could match"
            f" {assertion.columns}."
        ),
    )

  # A column the result never returned and a column whose value is wrong both
  # used to read "No row found matching {...}". They need different fixes, so
  # they get different messages.
  missing = [
      key
      for key in assertion.columns
      if all(_lookup_column(row, key) is _MISSING for row in data_rows)
  ]
  if missing:
    returned = sorted({str(key) for row in data_rows for key in row})
    return AssertionResult(
        assertion=assertion,
        passed=False,
        score=0.0,
        reasoning=(
            f"Column(s) {missing} are not in the result. The query returned"
            f" {returned}."
        ),
    )

  closest = None
  for row in data_rows:
    mismatches = []
    for key, val in assertion.columns.items():
      row_val = _lookup_column(row, key)
      if row_val is _MISSING:
        # Another row has the column, this one does not. A Struct row drops
        # its nulls, so this is how a null column arrives.
        mismatches.append(f"{key}: expected {val!r}, not in this row")
      elif not _values_match(row_val, val):
        mismatches.append(f"{key}: expected {val!r}, got {row_val!r}")
    if not mismatches:
      return AssertionResult(
          assertion=assertion,
          passed=True,
          score=1.0,
          reasoning=f"Found row matching {assertion.columns}.",
      )
    if closest is None or len(mismatches) < len(closest):
      closest = mismatches

  return AssertionResult(
      assertion=assertion,
      passed=False,
      score=0.0,
      reasoning=(
          f"No row found matching {assertion.columns}. The closest of"
          f" {len(data_rows)} row(s) differed on: {'; '.join(closest)}."
      ),
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
        # mark can arrive as a MapComposite (proto-plus), which behaves like a
        # dict but does not pass isinstance(x, dict).
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

  # Casefolded, the way every other contains check is. The mark comes out of
  # whatever Vega spec the agent wrote, so an assertion for "Bar" failed
  # against a chart the page rendered as a bar chart.
  if str(last_chart_type).casefold() == str(assertion.value).casefold():
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

  URL-encoded spaces (+) become actual spaces. The value is split on unescaped
  commas, which is how Looker writes list and OR values. Commas inside quotes
  are not split points, and an escaped comma (^,) becomes a literal comma.

  A quote only quotes when it opens a value. Every quote used to, so the
  apostrophe in O'Brien was dropped and the rest of the value stopped
  splitting on commas: "Smith, O'Brien" and "O'Brien, Smith" did not match
  each other, and "Bob's Burgers" matched "Bobs Burgers".

  Args:
    val: The Looker filter value string to normalize.

  Returns:
    A frozenset of the normalized filter values.
  """
  if not val:
    return frozenset()

  val = val.replace("+", " ")

  val = val.strip()

  parts = []
  current_part = []
  quote_char = None
  # Whether anything other than whitespace has been read for this part yet.
  part_started = False
  i = 0
  while i < len(val):
    char = val[i]
    if char == "^":
      if i + 1 < len(val):
        current_part.append(val[i + 1])
        i += 1
      else:
        current_part.append(char)
      part_started = True
    elif quote_char:
      if char == quote_char:
        quote_char = None
      else:
        current_part.append(char)
    elif char in ('"', "'") and not part_started:
      # Opens a quoted value. The quote character itself is not part of it.
      quote_char = char
    elif char == ",":
      parts.append("".join(current_part).strip())
      current_part = []
      part_started = False
    else:
      current_part.append(char)
      if not char.isspace():
        part_started = True

    i += 1

  parts.append("".join(current_part).strip())

  normalized = [p for p in parts if p]
  return frozenset(normalized)


def check_looker_query_match(
    response: AskQuestionResponse, assertion: LookerQueryMatch
) -> AssertionResult:
  """Checks whether any Looker query in the trace matches the parameters.

  Scored 1.0 or 0.0, not partially. A match rate is worked out per candidate
  query and the best one is compared against LOOKER_QUERY_MATCH_THRESHOLD; the
  rate itself only reaches the user through the reasoning text.
  """
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

  # A parameter the author left unset is not a parameter the agent can get
  # wrong, so it is worth no points either way.
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

    # Exact match.
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

    # Subset match on lists.
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

    if p.filters:
      expected_filters = {
          (f.field, _normalize_filter_value(str(f.value))) for f in p.filters
      }

      # The trace writes filters either as a list of field/value dicts or as a
      # single field-to-value dict, so both are read.
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
        # The normalized value is a frozenset, so render it back to something
        # a reader recognizes rather than printing the repr.
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


def trace_for_prompt(messages: list[dict[str, Any]]) -> str:
  """The trace as JSON, cut to AI_JUDGE_TRACE_CHAR_BUDGET characters.

  The whole trace used to go into the prompt unbounded, so a trial that
  answered with a large table built a prompt the model would not take and the
  judge failed on every assertion behind it. The marker is part of the text,
  which is how the model is told the tail is missing rather than reading a cut
  event as the end of the trial.

  The suggester sends the same traces to the same models, so it shares this.
  """
  chunks = []
  used = 0
  for message in messages:
    chunk = json.dumps(message, indent=2)
    if used + len(chunk) > AI_JUDGE_TRACE_CHAR_BUDGET:
      # Clamped at zero. used counts the newline the join puts after each
      # chunk, so a trace that filled the budget exactly left used one over it
      # and the slice went negative: chunk[:-1] kept the whole oversized event
      # bar its last character, which is the prompt the budget exists to stop.
      keep = max(AI_JUDGE_TRACE_CHAR_BUDGET - used, 0)
      chunks.append(chunk[:keep])
      chunks.append(
          f"[Trace truncated at {AI_JUDGE_TRACE_CHAR_BUDGET} characters. The"
          " events after this point are not shown.]"
      )
      break
    chunks.append(chunk)
    used += len(chunk) + 1
  return "\n".join(chunks)


def check_ai_judge(
    response: AskQuestionResponse,
    assertion: AIJudge,
    llm_client: Any | None = None,
    question: str | None = None,
) -> AssertionResult:
  """Evaluates the response using an LLM based on criteria.

  A result that carries error_message is a judge that could not be run, not a
  judge that said no. The two used to be the same row: passed false, score 0.
  Callers drop those results instead of scoring them, so a Vertex 400 or a
  quota blip no longer reads as a regression in the agent.
  """
  if not llm_client:
    return AssertionResult(
        assertion=assertion,
        passed=False,
        score=0.0,
        reasoning="LLM client not provided for AI Judge.",
        error_message="No LLM client, so the AI judge did not run.",
    )

  if not question:
    return AssertionResult(
        assertion=assertion,
        passed=False,
        score=0.0,
        reasoning="User question not provided for AI Judge.",
        error_message="No question, so the AI judge did not run.",
    )

  trace = trace_for_prompt(response.response)

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
          error_message="The AI judge returned nothing to score.",
      )

    return AssertionResult(
        assertion=assertion,
        passed=result.verdict,
        score=1.0 if result.verdict else 0.0,
        reasoning=result.explanation,
    )
  except Exception as e:  # pylint: disable=broad-exception-caught
    # reasoning is the field the assertion card shows, so it gets the same
    # treatment error_message does. The old text carried str(e), and a Vertex
    # InvalidArgument quotes the prompt it rejected, which is the question and
    # the agent's answer over the customer's data.
    logger.exception("AI judge raised while scoring an assertion")
    return AssertionResult(
        assertion=assertion,
        passed=False,
        score=0.0,
        reasoning=f"The AI judge raised {type(e).__name__}.",
        error_message=f"The AI judge raised {type(e).__name__}.",
    )


def evaluate_all(
    response: AskQuestionResponse,
    assertions: list[Assertion],
    llm_client: Any | None = None,
    question: str | None = None,
) -> list[AssertionResult]:
  """Evaluates a list of assertions against a response.

  Returns one result per assertion, in the order given. Callers zip the two
  lists together, so an assertion of a type the engine does not know still
  gets a result rather than being skipped.
  """
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
