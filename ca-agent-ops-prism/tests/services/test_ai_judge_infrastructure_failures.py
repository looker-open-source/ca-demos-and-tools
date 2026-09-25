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

"""An AI judge that never ran is not the agent getting the answer wrong.

check_ai_judge has five outcomes and four of them are prism failing to run the
check: no LLM client, no question, a judge that returned nothing, and a judge
that raised. All four used to reach the trial as passed false, score 0, which
is a weighted row in Trial.score and in the run accuracy. A Vertex quota blip
landed as a regression in the agent, and the accuracy chart tracked Vertex.

Those four carry error_message now, and the two callers that score results drop
the ones that have it. The result itself is still returned, so the reasoning
still reaches the page.

The judge raising on a large trial is the same story from the other end. The
whole trace went into the prompt, so a trial that answered with a few thousand
rows built a prompt the model rejects, and every AI judge on it failed.
tests/services/test_assert_engine_ai_judge.py covers the reasoning text.
"""

from __future__ import annotations

import unittest.mock

from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import BigQueryConfig
from prism.common.schemas.assertion import AIJudge
from prism.common.schemas.assertion import TextContains
from prism.common.schemas.trace import AskQuestionResponse
from prism.common.schemas.trace import DurationMetrics
from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
from prism.server.models.agent import Agent
from prism.server.models.run import RunStatus
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services import assert_engine
from prism.server.services.assert_engine import AIJudgeResult
from prism.server.services.execution_service import ExecutionService
from prism.server.services.snapshot_service import SnapshotService
import pytest
from sqlalchemy.orm import Session

_QUESTION = "How many orders shipped?"
_ANSWER = "412 orders shipped."

# The judge is the one that fails in these. Something has to be scored
# alongside it, or an empty score and a dropped result look the same.
_TEXT_ASSERTION = TextContains(value="orders")
_JUDGE_ASSERTION = AIJudge(value="The response should give a number")


def _response(text: str = _ANSWER) -> AskQuestionResponse:
  """A one-message trace carrying the agent's final answer."""
  return AskQuestionResponse(
      response=[{
          "system_message": {
              "text": {"parts": [text], "text_type": "FINAL_RESPONSE"}
          }
      }],
      duration=DurationMetrics(total_duration=120),
  )


def _failing_judge() -> unittest.mock.MagicMock:
  """An LLM client that answers with a quota error, as Vertex does."""
  llm = unittest.mock.MagicMock()
  llm.generate_structured.side_effect = RuntimeError("429 Resource exhausted")
  return llm


def _agent(db_session: Session) -> Agent:
  return AgentRepository(db_session).create(
      name="Judge Bot",
      config=AgentConfig(
          project_id="p",
          location="l",
          agent_resource_id="r",
          datasource=BigQueryConfig(tables=["t1"]),
      ),
  )


def _service(
    db_session: Session,
    response: AskQuestionResponse,
    llm: unittest.mock.MagicMock,
) -> ExecutionService:
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  client = unittest.mock.MagicMock(spec=GeminiDataAnalyticsClient)
  client.get_agent_context.return_value = {"system_instruction": "Test"}
  client.ask_question.return_value = response
  return ExecutionService(
      db_session,
      SnapshotService(db_session, suite_repo, example_repo),
      client,
      gen_ai_client=llm,
  )


def test_only_the_trace_the_prompt_has_room_for_reaches_the_judge():
  """One data event holding a few thousand result rows is megabytes.

  The prompt is rejected whole at that size, so the judge fails on a trial
  that answered perfectly well. The events are in the order they happened, so
  the cut falls at the end of the trial and the marker tells the model the
  tail is missing.
  """
  llm = unittest.mock.MagicMock()
  llm.generate_structured.return_value = AIJudgeResult(
      verdict=True, explanation="Yes."
  )
  response = AskQuestionResponse(
      response=[
          {"system_message": {"data": {"generated_sql": "x" * 200000}}},
          {"system_message": {"text": {"parts": ["after-the-cut"]}}},
      ],
      duration=DurationMetrics(total_duration=120),
  )

  assert_engine.check_ai_judge(
      response, _JUDGE_ASSERTION, llm_client=llm, question=_QUESTION
  )

  prompt = llm.generate_structured.call_args.args[0]
  assert len(prompt) < assert_engine.AI_JUDGE_TRACE_CHAR_BUDGET * 2
  assert "Trace truncated" in prompt
  assert "after-the-cut" not in prompt


@pytest.mark.parametrize(
    "llm,question",
    [
        (None, _QUESTION),
        (unittest.mock.MagicMock(), None),
        (
            unittest.mock.MagicMock(
                **{"generate_structured.return_value": None}
            ),
            _QUESTION,
        ),
        (
            unittest.mock.MagicMock(
                **{"generate_structured.side_effect": RuntimeError("429")}
            ),
            _QUESTION,
        ),
    ],
    ids=["no-client", "no-question", "no-verdict", "raised"],
)
def test_every_way_the_judge_fails_to_run_is_marked_as_such(llm, question):
  """error_message is the marker the scoring callers filter on.

  Without it the four are indistinguishable from a judged failure, which is
  how they were being counted.
  """
  result = assert_engine.check_ai_judge(
      _response(), _JUDGE_ASSERTION, llm_client=llm, question=question
  )

  assert result.error_message, "A judge that did not run has to say so"
  # The reasoning is still the user's explanation of what happened.
  assert result.reasoning


def test_a_judge_that_never_ran_is_left_off_the_trial(db_session: Session):
  """One passing text assertion and one judge that hit a quota error.

  Scored as a failure the trial is 0.5 and the run reads as a regression.
  What is being measured there is Vertex, not the agent, so the row is not
  written at all and the trial scores on the check that did run.
  """
  agent = _agent(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  suite = suite_repo.create(name="Judge Suite")
  example = example_repo.create(suite.id, _QUESTION)
  example_repo.add_assertion(example.id, _TEXT_ASSERTION)
  example_repo.add_assertion(example.id, _JUDGE_ASSERTION)
  db_session.commit()

  service = _service(db_session, _response(), _failing_judge())
  run = service.create_run(agent.id, suite.id)
  trial = service.execute_trial(run.trials[0].id)

  assert trial.status == RunStatus.COMPLETED
  assert (
      len(trial.assertion_results) == 1
  ), "The judge never answered, so there is nothing to record about it"
  assert trial.score == pytest.approx(1.0)


def test_the_playground_scores_the_same_way_over_the_same_results(
    db_session: Session,
):
  """The playground runs the assertions without persisting them.

  It is the second caller of evaluate_all and it has its own weighted mean, so
  the judge has to be dropped there too. The result still comes back in
  assertion_results: the page shows what happened, the score ignores it.
  """
  agent = _agent(db_session)
  service = _service(db_session, _response(), _failing_judge())

  result = service.execute_ephemeral_test(
      agent.id, _QUESTION, [_TEXT_ASSERTION, _JUDGE_ASSERTION]
  )

  assert result.score == pytest.approx(1.0)
  assert result.passed
  assert len(result.assertion_results) == 2
