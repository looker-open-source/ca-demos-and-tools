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

"""Regression tests for the deadline on a regex assertion.

A pattern is user input, and re has no execution limit. Before the deadline
went in, the pattern below ran until someone killed the process.
"""

import multiprocessing
import signal
import threading
import time
import types

from prism.common.schemas.assertion import QueryContains
from prism.common.schemas.assertion import TextContains
from prism.common.schemas.trace import AskQuestionResponse
from prism.common.schemas.trace import DurationMetrics
from prism.server.services import assert_engine

# Nested quantifiers with no match. Backtracking is exponential in the length
# of the subject, so 40 characters is already longer than the age of the
# repository.
CATASTROPHIC_PATTERN = r"^(a+)+$"
SUBJECT = "a" * 40 + "!"


def text_response(text):
  """Builds a response whose final text is ``text``."""
  return AskQuestionResponse(
      response=[{"system_message": {"text": {"parts": [text]}}}],
      duration=DurationMetrics(total_duration=100),
  )


def sql_response(sql):
  """Builds a response whose generated SQL is ``sql``."""
  return AskQuestionResponse(
      response=[{"system_message": {"data": {"generated_sql": sql}}}],
      duration=DurationMetrics(total_duration=100),
  )


def test_text_contains_gives_up_on_a_pathological_pattern(monkeypatch):
  """The assertion fails on the deadline instead of hanging the worker."""
  # One second rather than the real five, so the suite does not wait.
  monkeypatch.setattr(assert_engine, "REGEX_TIMEOUT_SECONDS", 1)
  response = text_response(SUBJECT)
  assertion = TextContains(value=CATASTROPHIC_PATTERN, mode="regex")

  started = time.monotonic()
  result = assert_engine.check_text_contains(response, assertion)
  elapsed = time.monotonic() - started

  assert not result.passed
  assert result.score == 0.0
  assert "did not finish within 1s" in result.reasoning
  assert elapsed < 10


def test_query_contains_gives_up_on_a_pathological_pattern(monkeypatch):
  """The query variant shares the code path, so it shares the deadline."""
  monkeypatch.setattr(assert_engine, "REGEX_TIMEOUT_SECONDS", 1)
  response = sql_response(SUBJECT)
  assertion = QueryContains(value=CATASTROPHIC_PATTERN, mode="regex")

  result = assert_engine.check_query_contains(response, assertion)

  assert not result.passed
  assert "generated query/SQL" in result.reasoning


def test_a_normal_pattern_is_unaffected(monkeypatch):
  """The deadline is armed and disarmed around every regex assertion."""
  monkeypatch.setattr(assert_engine, "REGEX_TIMEOUT_SECONDS", 1)
  response = text_response("There were 42 orders last week.")
  assertion = TextContains(value=r"\d+ orders", mode="regex")

  result = assert_engine.check_text_contains(response, assertion)

  assert result.passed
  # A timer left running would fire here, a second after the search returned.
  time.sleep(1.5)


def test_the_alarm_handler_is_put_back(monkeypatch):
  """The deadline borrows SIGALRM, and has to give it back.

  The handler is installed per search. Leaving it installed means the next
  SIGALRM the process takes, from anything at all, raises TimeoutError out of
  whatever was running at the time.
  """
  monkeypatch.setattr(assert_engine, "REGEX_TIMEOUT_SECONDS", 1)
  before = signal.getsignal(signal.SIGALRM)
  assertion = TextContains(value=CATASTROPHIC_PATTERN, mode="regex")

  assert_engine.check_text_contains(text_response(SUBJECT), assertion)

  assert signal.getsignal(signal.SIGALRM) is before


def _off_the_main_thread(call):
  """Runs ``call`` on another thread and returns what it returned."""
  box = {}

  def run():
    box["result"] = call()

  thread = threading.Thread(target=run)
  thread.start()
  thread.join(120)
  assert not thread.is_alive(), "the search never came back"
  return box["result"]


def test_a_pathological_pattern_is_bounded_off_the_main_thread():
  """A SIGALRM handler can only be installed on the main thread.

  The playground evaluates its assertions on a Dash request thread, and that
  path used to fall back to an unbounded re.search: the deadline did not exist
  where the untrusted pattern was most likely to be typed. It runs the search
  in a child process now, and kills it on the deadline.
  """
  response = text_response(SUBJECT)
  assertion = TextContains(value=CATASTROPHIC_PATTERN, mode="regex")

  started = time.monotonic()
  result = _off_the_main_thread(
      lambda: assert_engine.check_text_contains(response, assertion)
  )
  elapsed = time.monotonic() - started

  assert not result.passed
  assert "did not finish" in result.reasoning
  # Spawning the child costs a second or two on top of the deadline itself.
  assert elapsed < 60


def test_a_normal_pattern_still_answers_off_the_main_thread(monkeypatch):
  """The child process is an implementation detail, not a different answer.

  One second, well under what spawning an interpreter costs. Starting the
  child used to come out of the pattern's budget, so a pattern that matched
  immediately was reported as one that never finished.
  """
  monkeypatch.setattr(assert_engine, "REGEX_TIMEOUT_SECONDS", 1)
  matching = text_response("There were 42 orders last week.")
  missing = text_response("Nothing was ordered last week.")
  assertion = TextContains(value=r"\d+ orders", mode="regex")

  found = _off_the_main_thread(
      lambda: assert_engine.check_text_contains(matching, assertion)
  )
  not_found = _off_the_main_thread(
      lambda: assert_engine.check_text_contains(missing, assertion)
  )

  assert found.passed
  assert not not_found.passed


class _DeadChild:
  """A spawned interpreter that was killed before it wrote anything."""

  def start(self):
    pass

  def terminate(self):
    pass

  def join(self):
    pass


def _child_dies_before_answering(monkeypatch):
  """Points the regex search at a child that exits without an answer.

  The pipe is real, so the parent sees what it saw in production: its own
  write end closed, no write end left open anywhere, and a reader at EOF.
  """
  spawn = multiprocessing.get_context("spawn")
  context = types.SimpleNamespace(
      Pipe=spawn.Pipe,
      Process=lambda target, args, daemon: _DeadChild(),
  )
  monkeypatch.setattr(
      assert_engine,
      "multiprocessing",
      types.SimpleNamespace(get_context=lambda method: context),
  )


def test_a_child_that_dies_without_answering_fails_that_assertion(monkeypatch):
  """A memory capped instance killed the child during its imports.

  The parent has closed its write end, so the pipe is at EOF: poll returns
  True at once and recv raises EOFError, not TimeoutError. Nothing on this
  path caught EOFError, so it came out of the assertion.
  """
  response = text_response("There were 42 orders last week.")
  assertion = TextContains(value=r"\d+ orders", mode="regex")
  _child_dies_before_answering(monkeypatch)

  result = _off_the_main_thread(
      lambda: assert_engine.check_text_contains(response, assertion)
  )

  assert not result.passed
  assert result.score == 0.0
  assert "died before it answered" in result.reasoning


def test_a_dead_child_does_not_lose_the_other_assertions(monkeypatch):
  """evaluate_all catches nothing, so the EOFError ended the simulation.

  Every assertion already scored went with it, including the ones that had
  nothing to do with the regex.
  """
  response = text_response("There were 42 orders last week.")
  assertions = [
      TextContains(value=r"\d+ orders", mode="regex"),
      TextContains(value="orders"),
  ]
  _child_dies_before_answering(monkeypatch)

  results = _off_the_main_thread(
      lambda: assert_engine.evaluate_all(response, assertions)
  )

  assert len(results) == 2
  assert not results[0].passed
  assert results[1].passed
