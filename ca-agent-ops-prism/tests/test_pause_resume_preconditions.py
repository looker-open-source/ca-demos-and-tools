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

"""pause_run and resume_run only act on the statuses they document.

Neither of them read the run's status. pause_run wrote PAUSED over a terminal
one, so a click on Pause that landed just after the last trial finished took a
COMPLETED run out of the finished list and left it looking like it was waiting
for trials that had all run. resume_run set any run to RUNNING, and the worker
picks its active run with list_all(status=RUNNING, limit=1), so resuming a
PENDING run gave the worker two RUNNING runs and which one made progress was
down to the order the rows came back in.

Both buttons sit on a page that keeps rendering them after the run has moved
on, so both were one stray click away.

resume_run also stamps started_at. Pause accepts a PENDING run, and resume was
the only way back out of PAUSED, so a run paused before it started came back
RUNNING with no start time and finished with no duration at all.
"""

import datetime

from prism.client.run_client import RunsClient
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.execution import RunStatus
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.run_repository import RunRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.snapshot_service import SnapshotService
import pytest
from sqlalchemy.orm import Session


def _make_runs(session: Session, *statuses: RunStatus):
  """Builds one run per status, all against the same agent and snapshot."""
  agent_repo = AgentRepository(session)
  suite_repo = SuiteRepository(session)
  example_repo = ExampleRepository(session)
  snapshot_service = SnapshotService(session, suite_repo, example_repo)
  run_repo = RunRepository(session)

  config = AgentConfig(project_id="p", location="l", agent_resource_id="r")
  agent = agent_repo.create(name="Bot", config=config)
  suite = suite_repo.create(name="Suite")
  example_repo.create(suite.id, "Q1")
  snapshot = snapshot_service.create_snapshot(suite.id)

  runs = []
  for status in statuses:
    run = run_repo.create(snapshot.id, agent.id)
    run.status = status
    runs.append(run)
  session.commit()
  return run_repo, runs


@pytest.mark.parametrize(
    "terminal_status",
    [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED],
)
def test_pausing_a_finished_run_leaves_it_in_its_terminal_status(
    db_session: Session, terminal_status
):
  """A run that has finished is not waiting for anything to be paused.

  PAUSED over COMPLETED dropped the run out of the finished list, and nothing
  moves a paused run on again except a Resume click.
  """
  run_repo, (run,) = _make_runs(db_session, terminal_status)

  RunsClient().pause_run(run_id=run.id, repo=run_repo)

  db_session.expire_all()
  assert run_repo.get_by_id(run.id).status == terminal_status


def test_pausing_a_running_run_pauses_it(db_session: Session):
  """Guards the check above. A refusal that refuses everything is no use."""
  run_repo, (run,) = _make_runs(db_session, RunStatus.RUNNING)

  RunsClient().pause_run(run_id=run.id, repo=run_repo)

  db_session.expire_all()
  assert run_repo.get_by_id(run.id).status == RunStatus.PAUSED


def test_pausing_a_pending_run_pauses_it(db_session: Session):
  """A queued run is the other thing Pause is for.

  It has not started, so pausing it is how it is kept out of the worker's way.
  """
  run_repo, (run,) = _make_runs(db_session, RunStatus.PENDING)

  RunsClient().pause_run(run_id=run.id, repo=run_repo)

  db_session.expire_all()
  assert run_repo.get_by_id(run.id).status == RunStatus.PAUSED


def test_resuming_a_pending_run_leaves_it_pending(db_session: Session):
  """A queued run has nothing to resume, and promoting it here broke the queue.

  The worker takes trials from one RUNNING run at a time and finds it with a
  limit of 1. A second RUNNING run made the choice depend on row order, and
  the run that lost sat there with its trials untouched.
  """
  run_repo, (running, pending) = _make_runs(
      db_session, RunStatus.RUNNING, RunStatus.PENDING
  )

  RunsClient().resume_run(run_id=pending.id, repo=run_repo)

  db_session.expire_all()
  assert run_repo.get_by_id(pending.id).status == RunStatus.PENDING
  assert [r.id for r in run_repo.list_all(status=RunStatus.RUNNING)] == [
      running.id
  ], "The worker picks one of these at random and starves the other."


def test_resuming_a_paused_run_makes_it_running(db_session: Session):
  """Guards the check above. PAUSED is the status Resume exists for."""
  run_repo, (run,) = _make_runs(db_session, RunStatus.PAUSED)

  RunsClient().resume_run(run_id=run.id, repo=run_repo)

  db_session.expire_all()
  assert run_repo.get_by_id(run.id).status == RunStatus.RUNNING


def test_a_run_paused_before_it_started_gets_a_start_time_on_resume(
    db_session: Session,
):
  """Pause, then Resume, on a queued run left started_at NULL for good.

  The run comes back RUNNING, so the worker never reaches promote_next_run for
  it, and the trial claim stamps the run only while it is PENDING. Nothing
  else writes the column. Run.duration_ms stayed None, so the run detail page
  and the agent dashboard showed no duration on a finished run and the
  BigQuery runs row went out with duration_ms NULL.
  """
  run_repo, (run,) = _make_runs(db_session, RunStatus.PENDING)
  RunsClient().pause_run(run_id=run.id, repo=run_repo)

  RunsClient().resume_run(run_id=run.id, repo=run_repo)

  db_session.expire_all()
  resumed = run_repo.get_by_id(run.id)
  assert resumed.status == RunStatus.RUNNING
  assert resumed.started_at is not None


def test_resuming_a_run_that_had_already_started_keeps_its_start_time(
    db_session: Session,
):
  """A run paused halfway through was stamped when it was promoted.

  Writing a fresh time here would drop the trials that ran before the pause
  out of the reported duration.
  """
  started_at = datetime.datetime.now(
      datetime.timezone.utc
  ) - datetime.timedelta(minutes=5)
  run_repo, (run,) = _make_runs(db_session, RunStatus.RUNNING)
  run.started_at = started_at
  db_session.commit()
  RunsClient().pause_run(run_id=run.id, repo=run_repo)

  RunsClient().resume_run(run_id=run.id, repo=run_repo)

  db_session.expire_all()
  assert run_repo.get_by_id(run.id).started_at == started_at
