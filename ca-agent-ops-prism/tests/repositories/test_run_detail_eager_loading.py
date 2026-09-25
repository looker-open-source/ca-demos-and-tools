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

"""What the run detail page costs to read.

RunRepository.eager_options covered the snapshot suite, the agent, the trials
and their assertion results, but not Trial.example_snapshot or
Trial.suggested_asserts. The page reads both: _map_trial takes the question off
the example snapshot and Trial.model_validate reads the suggestions. So every
trial cost two more queries, on a page that polls every three seconds.

Both are loaded now, the way TrialRepository.eager_options already loads them.
"""

import datetime

from prism.common.schemas.assertion import AssertionType
from prism.common.schemas.execution import RunStatus
from prism.server.models.agent import Agent
from prism.server.models.assertion import AssertionResult
from prism.server.models.assertion import AssertionSnapshot
from prism.server.models.assertion import SuggestedAssertion
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.server.models.snapshot import ExampleSnapshot
from prism.server.models.snapshot import TestSuiteSnapshot
from prism.server.repositories.run_repository import RunRepository
from sqlalchemy import orm

NOW = datetime.datetime.now(datetime.timezone.utc)


def _run_with_trials(session: orm.Session, trial_count: int) -> Run:
  """One run, and trials each carrying a result and a suggestion."""
  agent = Agent(
      name="Detail Agent", project_id="p", location="l", agent_resource_id="r"
  )
  session.add(agent)
  session.flush()

  suite_snapshot = TestSuiteSnapshot(name="Suite", original_suite_id=1)
  session.add(suite_snapshot)
  session.flush()

  run = Run(
      agent_id=agent.id,
      test_suite_snapshot_id=suite_snapshot.id,
      status=RunStatus.COMPLETED,
      created_at=NOW,
      started_at=NOW,
      completed_at=NOW,
      is_archived=False,
  )
  session.add(run)
  session.flush()

  for index in range(trial_count):
    example_snapshot = ExampleSnapshot(
        snapshot_suite_id=suite_snapshot.id,
        logical_id=f"L{index}",
        question=f"Q{index}",
    )
    session.add(example_snapshot)
    session.flush()

    trial = Trial(
        run_id=run.id,
        example_snapshot_id=example_snapshot.id,
        status=RunStatus.COMPLETED,
        created_at=NOW,
        started_at=NOW,
        completed_at=NOW,
    )
    trial.assertion_results.append(
        AssertionResult(
            score=1.0,
            passed=True,
            assertion_snapshot=AssertionSnapshot(
                type=AssertionType.TEXT_CONTAINS,
                weight=1.0,
                params={"value": "x"},
                example_snapshot_id=example_snapshot.id,
            ),
        )
    )
    trial.suggested_asserts.append(
        SuggestedAssertion(
            type=AssertionType.TEXT_CONTAINS,
            weight=1.0,
            params={"value": "x"},
            reasoning="Because.",
        )
    )
    session.add(trial)

  session.commit()
  return run


def _render(run: Run) -> list[str]:
  """The two relationships the run detail page reads off every trial."""
  return [
      f"{trial.example_snapshot.question}:{len(trial.suggested_asserts)}"
      for trial in run.trials
  ]


def test_reading_a_run_costs_the_same_however_many_trials_it_has(
    db_session: orm.Session, statement_counter
):
  small = _run_with_trials(db_session, trial_count=1)
  large = _run_with_trials(db_session, trial_count=8)
  repository = RunRepository(db_session)

  # Expired first, so neither read is served out of the identity map the other
  # one filled.
  db_session.expire_all()
  with statement_counter() as small_counter:
    small_rendered = _render(repository.get_by_id(small.id))

  db_session.expire_all()
  with statement_counter() as large_counter:
    large_rendered = _render(repository.get_by_id(large.id))

  assert len(small_rendered) == 1
  assert len(large_rendered) == 8
  assert large_counter.count == small_counter.count


def test_the_eagerly_loaded_trials_still_carry_their_questions(
    db_session: orm.Session,
):
  """Loading it in one query has to return the same thing lazy loading did."""
  run = _run_with_trials(db_session, trial_count=3)
  db_session.expire_all()

  loaded = RunRepository(db_session).get_by_id(run.id)

  assert _render(loaded) == ["Q0:1", "Q1:1", "Q2:1"]
