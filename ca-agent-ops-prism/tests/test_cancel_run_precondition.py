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

"""cancel_run only touches a run that has not finished.

The docstring said "Cancels a RUNNING or PAUSED run" and the method never read
the status. It wrote CANCELLED and a fresh completed_at over whatever was
there, so a click on the cancel button after a run had finished rewrote its
terminal status and replaced the real completion time, which is what
Run.duration_ms is measured from. The button is still on screen at that point,
so it was one stray click away.
"""

import datetime

from prism.client.run_client import RunsClient
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.execution import RunStatus
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.run_repository import RunRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.repositories.trial_repository import TrialRepository
from prism.server.services.snapshot_service import SnapshotService
import pytest
from sqlalchemy.orm import Session

_FINISHED_AT = datetime.datetime(
    2026, 3, 1, 12, 0, tzinfo=datetime.timezone.utc
)


def _make_run(session: Session):
  """Builds a run with one trial, so there is something to leave alone."""
  agent_repo = AgentRepository(session)
  suite_repo = SuiteRepository(session)
  example_repo = ExampleRepository(session)
  snapshot_service = SnapshotService(session, suite_repo, example_repo)
  run_repo = RunRepository(session)
  trial_repo = TrialRepository(session)

  config = AgentConfig(project_id="p", location="l", agent_resource_id="r")
  agent = agent_repo.create(name="Bot", config=config)
  suite = suite_repo.create(name="Suite")
  example_repo.create(suite.id, "Q1")
  snapshot = snapshot_service.create_snapshot(suite.id)

  run = run_repo.create(snapshot.id, agent.id)
  trial = trial_repo.create(run.id, snapshot.examples[0].id)
  return run_repo, run, trial


@pytest.mark.parametrize(
    "terminal_status",
    [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED],
)
def test_cancelling_a_finished_run_leaves_its_status_and_completion_time(
    db_session: Session, terminal_status
):
  """A run that finished at noon still says it finished at noon."""
  run_repo, run, _ = _make_run(db_session)
  run.status = terminal_status
  run.completed_at = _FINISHED_AT
  db_session.commit()

  RunsClient().cancel_run(run_id=run.id, repo=run_repo)

  db_session.expire_all()
  stored = run_repo.get_by_id(run.id)
  assert stored.status == terminal_status
  assert stored.completed_at == _FINISHED_AT


def test_cancelling_a_finished_run_leaves_its_trials_alone(
    db_session: Session,
):
  """The trial UPDATE is inside the branch, so it has to be skipped too.

  A COMPLETED run with a PENDING trial is the state a partially aggregated run
  is in. Cancelling the run used to reach in and cancel that trial, which is
  what the run had already been scored without.
  """
  run_repo, run, trial = _make_run(db_session)
  run.status = RunStatus.COMPLETED
  run.completed_at = _FINISHED_AT
  db_session.commit()

  RunsClient().cancel_run(run_id=run.id, repo=run_repo)

  db_session.expire_all()
  assert (
      TrialRepository(db_session).get_trial(trial.id).status
      == RunStatus.PENDING
  )


def test_cancelling_a_running_run_still_cancels_it(db_session: Session):
  """Guards the check above. A refusal that refuses everything is no use."""
  run_repo, run, trial = _make_run(db_session)
  run.status = RunStatus.RUNNING
  db_session.commit()

  RunsClient().cancel_run(run_id=run.id, repo=run_repo)

  db_session.expire_all()
  stored = run_repo.get_by_id(run.id)
  assert stored.status == RunStatus.CANCELLED
  assert stored.completed_at is not None
  assert (
      TrialRepository(db_session).get_trial(trial.id).status
      == RunStatus.CANCELLED
  )
