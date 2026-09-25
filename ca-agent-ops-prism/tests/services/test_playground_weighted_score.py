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

"""The playground score has to be the score a run would have given.

execute_ephemeral_test used to average the assertion results flat. Trial.score
weights them, and it drops the assertions weighted to zero. So the same
question with the same assertions scored one number in the playground and a
different one in the run it was being rehearsed for, and an assertion the user
had weighted out still moved the playground number.

These compare the two directly: the same (score, weight) pairs go through
execute_ephemeral_test and through a detached Trial, and the numbers have to
match.
"""

from unittest import mock

from prism.common.schemas.assertion import AssertionType
from prism.common.schemas.assertion import TextContains
from prism.common.schemas.execution import AssertionResult
from prism.common.schemas.execution import RunStatus
from prism.common.schemas.trace import AskQuestionResponse
from prism.common.schemas.trace import DurationMetrics
from prism.server.models.agent import Agent
from prism.server.models.assertion import AssertionResult as AssertionResultRow
from prism.server.models.assertion import AssertionSnapshot
from prism.server.models.run import Trial
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services import execution_service as execution_service_module
from prism.server.services.execution_service import ExecutionService
from prism.server.services.snapshot_service import SnapshotService
import pytest
from sqlalchemy import orm


@pytest.fixture(name="agent")
def _agent(db_session: orm.Session) -> Agent:
  agent = Agent(
      name="Playground Agent",
      project_id="p",
      location="us-central1",
      agent_resource_id="r",
      datasource_config={"type": "bigquery", "tables": ["t"]},
  )
  db_session.add(agent)
  db_session.commit()
  return agent


@pytest.fixture(name="service")
def _service(db_session: orm.Session) -> ExecutionService:
  """The real service with the one remote call stubbed out."""
  client = mock.MagicMock()
  client.get_datasource_kind.return_value = "bigquery"
  client.ask_question.return_value = AskQuestionResponse(
      response=[], duration=DurationMetrics(total_duration=42)
  )
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snap_service = SnapshotService(db_session, suite_repo, example_repo)
  return ExecutionService(db_session, snap_service, client)


def _results(*scored_weights: tuple[float, float]) -> list[AssertionResult]:
  """What evaluate_all hands back, one entry per (score, weight) pair."""
  return [
      AssertionResult(
          assertion=TextContains(value="x", weight=weight),
          passed=score >= 1.0,
          score=score,
      )
      for score, weight in scored_weights
  ]


def _trial_score(*scored_weights: tuple[float, float]) -> float | None:
  """The same pairs, scored the way a run scores them."""
  trial = Trial(status=RunStatus.COMPLETED)
  for score, weight in scored_weights:
    trial.assertion_results.append(
        AssertionResultRow(
            assertion_snapshot=AssertionSnapshot(
                type=AssertionType.TEXT_CONTAINS, weight=weight, params={}
            ),
            passed=score >= 1.0,
            score=score,
        )
    )
  return trial.score


def _playground_score(service, agent, results, monkeypatch) -> float | None:
  monkeypatch.setattr(
      execution_service_module.assert_engine,
      "evaluate_all",
      lambda **kwargs: results,
  )
  return service.execute_ephemeral_test(agent.id, "Q?", []).score


@pytest.mark.parametrize(
    "scored_weights",
    [
        [(1.0, 3.0), (0.0, 1.0)],
        [(1.0, 1.0), (0.5, 2.0), (0.0, 5.0)],
        [(1.0, 1.0), (0.0, 0.0)],
        [(0.25, 2.5), (0.75, 0.5)],
    ],
    ids=["heavy-pass", "three-weights", "zero-weighted-fail", "fractional"],
)
def test_the_playground_scores_a_case_the_way_a_run_does(
    service, agent, monkeypatch, scored_weights
):
  results = _results(*scored_weights)

  score = _playground_score(service, agent, results, monkeypatch)

  assert score == pytest.approx(_trial_score(*scored_weights))


def test_an_assertion_weighted_to_zero_does_not_move_the_score(
    service, agent, monkeypatch
):
  """The flat mean counted it, which is what made the two disagree."""
  with_zero = _playground_score(
      service, agent, _results((1.0, 1.0), (0.0, 0.0)), monkeypatch
  )
  without = _playground_score(service, agent, _results((1.0, 1.0)), monkeypatch)

  assert with_zero == without == 1.0


def test_a_failing_assertion_weighted_to_zero_does_not_fail_the_case(
    service, agent, monkeypatch
):
  """passed is read over the scored subset, the one the score is read over.

  It used to be read over every result. A failing assertion the user had
  weighted to 0 was dropped from the score and left it at 1.0, and still set
  passed to False. The playground showed a full score on a case it called
  failed.
  """
  monkeypatch.setattr(
      execution_service_module.assert_engine,
      "evaluate_all",
      lambda **kwargs: _results((1.0, 1.0), (0.0, 0.0)),
  )

  result = service.execute_ephemeral_test(agent.id, "Q?", [])

  assert result.score == 1.0
  assert result.passed


def test_nothing_scored_leaves_the_score_none(service, agent, monkeypatch):
  """No weighted assertion means no score, not a zero.

  Trial.score is None here too. A 0.0 would read as an answer that failed
  everything.
  """
  score = _playground_score(
      service, agent, _results((1.0, 0.0), (0.0, 0.0)), monkeypatch
  )

  assert score is None
  assert _trial_score((1.0, 0.0), (0.0, 0.0)) is None


def test_a_failed_agent_call_is_not_a_pass(service, agent, monkeypatch):
  """The error path drops every result, and an empty set read as all passed.

  Asking a question with no assertions on it is the ordinary way to use the
  playground, so there was nothing left to disagree with. The panel painted a
  green check and "0 of 0 passed" over a call that never reached the agent.
  """
  service.client.ask_question.return_value = AskQuestionResponse(
      response=[],
      duration=DurationMetrics(total_duration=42),
      error_message="The agent returned 503.",
  )
  monkeypatch.setattr(
      execution_service_module.assert_engine, "evaluate_all", lambda **kw: []
  )

  result = service.execute_ephemeral_test(agent.id, "Q?", [])

  assert result.error_message == "The agent returned 503."
  assert result.passed is False
