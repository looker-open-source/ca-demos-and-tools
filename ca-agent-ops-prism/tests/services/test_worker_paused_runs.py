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

"""Tests that pausing a run actually stops it and can still be undone.

Pausing used to be a badge change and nothing else. Two things went wrong for
whoever pressed the button. The queue treated the paused run as gone and
started the next one, so two runs called the agent API at once. And a run
paused after its last trial had finished never came back: the aggregator only
looked at PENDING and RUNNING runs, so there was nothing left to move it to
COMPLETED and resuming it did not help.
"""

from typing import Any, Sequence

from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.execution import RunStatus
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.run_repository import RunRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.repositories.trial_repository import TrialRepository
from prism.server.services.snapshot_service import SnapshotService
from prism.server.services.worker import WorkerProcessManager
import pytest
from sqlalchemy import orm


@pytest.fixture
def worker(session_factory: Any):
  # The manager is a singleton, so without this the constructor hands back a
  # leftover from an earlier test, session factory and all. Cleared on the way
  # out too: this one is bound to a session factory whose tables are dropped at
  # teardown, and get_worker_pool_service would hand it to whichever test runs
  # next.
  WorkerProcessManager._instance = None
  manager = WorkerProcessManager(session_factory=session_factory)
  yield manager
  manager.stop()
  WorkerProcessManager._instance = None


def create_agent_and_snapshot(session: orm.Session):
  """Builds the agent and the frozen one question suite runs are made from."""
  agent_repo = AgentRepository(session)
  suite_repo = SuiteRepository(session)
  example_repo = ExampleRepository(session)
  snap_service = SnapshotService(session, suite_repo, example_repo)

  config = AgentConfig(project_id="p", location="l", agent_resource_id="r")
  agent = agent_repo.create(name="Bot", config=config)
  suite = suite_repo.create(name="Suite")
  example_repo.create(suite.id, "Q1")
  return agent, snap_service.create_snapshot(suite.id)


def create_run(
    session: orm.Session,
    agent,
    snapshot,
    status: RunStatus,
    trial_statuses: Sequence[RunStatus] = (),
):
  """Creates a run in the given status, with a trial per status listed."""
  run_repo = RunRepository(session)
  trial_repo = TrialRepository(session)

  run = run_repo.create(snapshot.id, agent.id)
  for trial_status in trial_statuses:
    trial = trial_repo.create(run.id, snapshot.examples[0].id)
    trial.status = trial_status
  run.status = status
  session.commit()
  return run


def test_a_paused_run_keeps_the_queue_slot(db_session: orm.Session):
  agent, snapshot = create_agent_and_snapshot(db_session)
  create_run(db_session, agent, snapshot, RunStatus.PAUSED)
  pending = create_run(db_session, agent, snapshot, RunStatus.PENDING)

  run_repo = RunRepository(db_session)
  assert run_repo.promote_next_run() is None

  db_session.refresh(pending)
  assert pending.status == RunStatus.PENDING


def test_the_queue_moves_on_once_the_paused_run_is_done(
    db_session: orm.Session,
):
  """Pairs with the test above: the slot is held, not blocked for good."""
  agent, snapshot = create_agent_and_snapshot(db_session)
  paused = create_run(db_session, agent, snapshot, RunStatus.PAUSED)
  pending = create_run(db_session, agent, snapshot, RunStatus.PENDING)

  run_repo = RunRepository(db_session)

  # Resume, then let it finish the way the aggregator would.
  paused.status = RunStatus.RUNNING
  db_session.commit()
  assert run_repo.promote_next_run() is None

  paused.status = RunStatus.COMPLETED
  db_session.commit()

  promoted = run_repo.promote_next_run()
  assert promoted is not None
  assert promoted.id == pending.id
  assert promoted.status == RunStatus.RUNNING
  assert promoted.started_at is not None


@pytest.mark.parametrize(
    "status", [RunStatus.PAUSED, RunStatus.CANCELLED, RunStatus.COMPLETED]
)
def test_no_more_trials_are_handed_out_for_a_run_that_stopped(
    db_session: orm.Session, status: RunStatus
):
  """The claim checks the run, whether or not the caller named one.

  Naming a run used to replace the run status filter rather than narrow it,
  and the worker reads its run once at the top of a pass and then claims
  trials in a loop. A Pause or a Cancel that landed mid loop was not seen, so
  the rest of the run's capacity was spawned anyway and the user watched
  trials keep starting after pressing the button.
  """
  agent, snapshot = create_agent_and_snapshot(db_session)
  run = create_run(
      db_session, agent, snapshot, status, trial_statuses=[RunStatus.PENDING]
  )

  trial_repo = TrialRepository(db_session)
  assert trial_repo.pick_next_pending_trial(run_id=run.id) is None
  assert trial_repo.pick_next_pending_trial() is None


def test_a_running_run_still_hands_out_its_trials(db_session: orm.Session):
  """Pairs with the test above: the filter is on stopped runs, not on all."""
  agent, snapshot = create_agent_and_snapshot(db_session)
  run = create_run(
      db_session,
      agent,
      snapshot,
      RunStatus.RUNNING,
      trial_statuses=[RunStatus.PENDING],
  )

  claimed = TrialRepository(db_session).pick_next_pending_trial(run_id=run.id)

  assert claimed is not None
  assert claimed.status == RunStatus.RUNNING
  assert claimed.started_at is not None


def test_list_active_includes_a_paused_run(db_session: orm.Session):
  agent, snapshot = create_agent_and_snapshot(db_session)
  paused = create_run(db_session, agent, snapshot, RunStatus.PAUSED)

  run_repo = RunRepository(db_session)
  assert [run.id for run in run_repo.list_active()] == [paused.id]


def test_a_paused_run_with_no_trials_left_completes(
    db_session: orm.Session, worker: WorkerProcessManager
):
  """The stranding regression, through the worker pass that resolves it."""
  agent, snapshot = create_agent_and_snapshot(db_session)
  paused = create_run(
      db_session,
      agent,
      snapshot,
      RunStatus.PAUSED,
      trial_statuses=[RunStatus.COMPLETED, RunStatus.COMPLETED],
  )

  worker._aggregate_run_statuses()

  db_session.expire_all()
  db_session.refresh(paused)
  assert paused.status == RunStatus.COMPLETED
  assert paused.completed_at is not None


def test_a_cancelled_and_archived_run_does_not_keep_the_slot(
    db_session: orm.Session,
):
  """The way out of a paused run that is holding up the queue.

  Archiving a run that is still going is refused, because the worker's queries
  all skip archived runs and the run would never finish. So cancel first, then
  archive, and the run behind it starts.
  """
  agent, snapshot = create_agent_and_snapshot(db_session)
  paused = create_run(db_session, agent, snapshot, RunStatus.PAUSED)
  pending = create_run(db_session, agent, snapshot, RunStatus.PENDING)

  run_repo = RunRepository(db_session)
  paused.status = RunStatus.CANCELLED
  db_session.commit()
  run_repo.archive(paused.id)

  assert paused.id not in [run.id for run in run_repo.list_active()]

  promoted = run_repo.promote_next_run()
  assert promoted is not None
  assert promoted.id == pending.id


def test_archiving_a_paused_run_is_refused(db_session: orm.Session):
  """The guard that sends the caller through cancel first.

  Archiving took the run out of every worker query, so a paused run archived
  from the runs list was abandoned mid-flight: its pending trials were never
  claimed again and it sat there with no completion time.
  """
  agent, snapshot = create_agent_and_snapshot(db_session)
  paused = create_run(db_session, agent, snapshot, RunStatus.PAUSED)

  with pytest.raises(ValueError, match="Cancel it first"):
    RunRepository(db_session).archive(paused.id)

  db_session.refresh(paused)
  assert not paused.is_archived
