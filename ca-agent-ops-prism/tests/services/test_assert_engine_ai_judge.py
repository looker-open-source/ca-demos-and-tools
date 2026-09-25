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

"""The ways an AI_JUDGE assertion can come back other than a pass.

check_ai_judge has five outcomes and four of them score zero: no LLM client, no
question, a judge that returned nothing, and a judge that raised. Only the
verdict arm is a real answer about the agent. The other four are prism failing
to run the check at all, and they reach the trial row looking identical to a
judged failure: passed false, score 0.

So the reasoning string is the whole difference. If it says the wrong thing, a
missing GCP project or a quota error reads as "the agent got it wrong", and the
run's accuracy is a number about prism's configuration. test_assert_engine.py
covers the pass arm; this file covers the rest.
"""

import unittest.mock

from prism.common.schemas.assertion import AIJudge
from prism.common.schemas.trace import AskQuestionResponse
from prism.common.schemas.trace import DurationMetrics
from prism.server.services import assert_engine
from prism.server.services.assert_engine import AIJudgeResult
import pytest


def make_response():
  """The same one-message trace the pass-arm test judges."""
  return AskQuestionResponse(
      response=[{"system_message": {"text": {"parts": ["hello"]}}}],
      duration=DurationMetrics(total_duration=100),
  )


@pytest.fixture(name="assertion")
def _assertion() -> AIJudge:
  return AIJudge(value="The response should be hello")


def test_no_llm_client_is_reported_as_prisms_problem(assertion: AIJudge):
  """evaluate_all passes llm_client through, and it can arrive as None.

  That is what a run started without a configured Gen AI project looks like.
  """
  result = assert_engine.check_ai_judge(
      make_response(), assertion, llm_client=None, question="Say hello"
  )

  assert not result.passed
  assert result.score == 0.0
  assert "LLM client not provided" in result.reasoning


def test_a_missing_question_is_reported_as_prisms_problem(assertion: AIJudge):
  """The judge prompt needs the question the agent was asked.

  Every other assertion type reads the response alone, so a caller that never
  threaded the question through gets no complaint from them.
  """
  mock_llm = unittest.mock.MagicMock()

  result = assert_engine.check_ai_judge(
      make_response(), assertion, llm_client=mock_llm, question=None
  )

  assert not result.passed
  assert result.score == 0.0
  assert "question not provided" in result.reasoning
  assert not mock_llm.generate_structured.called


def test_a_judge_that_returned_nothing_is_not_a_failed_assertion(
    assertion: AIJudge,
):
  """generate_structured returns None when the model output will not parse."""
  mock_llm = unittest.mock.MagicMock()
  mock_llm.generate_structured.return_value = None

  result = assert_engine.check_ai_judge(
      make_response(), assertion, llm_client=mock_llm, question="Say hello"
  )

  assert not result.passed
  assert result.score == 0.0
  assert "failed to generate a verdict" in result.reasoning


def test_a_judge_that_raised_keeps_the_error_on_the_result(assertion: AIJudge):
  """A quota or permission error has to reach the trial row.

  The exception is swallowed here so one bad assertion does not end the run,
  which leaves the reasoning as the only place the cause is written down.
  """
  mock_llm = unittest.mock.MagicMock()
  mock_llm.generate_structured.side_effect = RuntimeError(
      "429 Resource exhausted"
  )

  result = assert_engine.check_ai_judge(
      make_response(), assertion, llm_client=mock_llm, question="Say hello"
  )

  assert not result.passed
  assert result.score == 0.0
  # The type, not the text. reasoning is rendered on the trial page, and what
  # the judge client raises carries the project and the model it was refused.
  # The message itself is in the log.
  assert result.reasoning == "The AI judge raised RuntimeError."
  assert "429 Resource exhausted" not in result.reasoning


def test_a_negative_verdict_carries_the_judges_own_explanation(
    assertion: AIJudge,
):
  """The one arm here that is an answer about the agent.

  Its reasoning is the model's explanation verbatim, which is what the trial
  row shows the user, so nothing may be prepended to it.
  """
  mock_llm = unittest.mock.MagicMock()
  mock_llm.generate_structured.return_value = AIJudgeResult(
      verdict=False, explanation="The trace never says hello."
  )

  result = assert_engine.check_ai_judge(
      make_response(), assertion, llm_client=mock_llm, question="Say hello"
  )

  assert not result.passed
  assert result.score == 0.0
  assert result.reasoning == "The trace never says hello."
