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

"""Unit tests for RunRepository."""

import datetime

from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.execution import RunStatus
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.server.models.snapshot import ExampleSnapshot
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.run_repository import RunRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.snapshot_service import SnapshotService
import sqlalchemy
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker


def test_create_run(db_session: Session):
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
  )
  agent = agent_repo.create(name="Bot", config=config)
  suite = suite_repo.create(name="Suite")
  snapshot = snapshot_service.create_snapshot(suite.id)

  repo = RunRepository(db_session)
  run = repo.create(
      test_suite_snapshot_id=snapshot.id,
      agent_id=agent.id,
      agent_context_snapshot={"p": "v"},
  )

  assert run.id is not None
  assert run.agent_id == agent.id
  assert run.agent_context_snapshot == {"p": "v"}
  assert not run.is_archived


def test_list_runs(db_session: Session):
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
  )
  agent = agent_repo.create(name="Bot", config=config)
  suite = suite_repo.create(name="Suite")
  snapshot = snapshot_service.create_snapshot(suite.id)

  repo = RunRepository(db_session)
  repo.create(snapshot.id, agent.id)
  repo.create(snapshot.id, agent.id)

  runs = repo.list_all()
  assert len(runs) == 2


def test_archive_run(db_session: Session):
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  agent = agent_repo.create(
      name="Bot",
      config=AgentConfig(project_id="p", location="l", agent_resource_id="r"),
  )
  suite = suite_repo.create(name="Suite")
  snapshot = snapshot_service.create_snapshot(suite.id)

  repo = RunRepository(db_session)
  run = repo.create(snapshot.id, agent.id)
  assert not run.is_archived

  run.status = RunStatus.COMPLETED
  db_session.commit()
  repo.archive(run.id)
  db_session.refresh(run)
  assert run.is_archived


def test_unarchive_run(db_session: Session):
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  agent = agent_repo.create(
      name="Bot",
      config=AgentConfig(project_id="p", location="l", agent_resource_id="r"),
  )
  suite = suite_repo.create(name="Suite")
  snapshot = snapshot_service.create_snapshot(suite.id)

  repo = RunRepository(db_session)
  run = repo.create(snapshot.id, agent.id)
  run.status = RunStatus.COMPLETED
  db_session.commit()
  repo.archive(run.id)
  db_session.refresh(run)
  assert run.is_archived

  repo.unarchive(run.id)
  db_session.refresh(run)
  assert not run.is_archived


def test_recent_evals_report_the_start_time_not_the_queue_time(
    db_session: Session,
):
  """The agent detail table reads these two fields straight through.

  Both used to come off created_at, so a run that sat in the queue for an hour
  showed the wrong start time and an hour of queueing as an hour of runtime.
  """
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  agent = agent_repo.create(
      name="Bot",
      config=AgentConfig(project_id="p", location="l", agent_resource_id="r"),
  )
  suite = suite_repo.create(name="Suite")
  snapshot = snapshot_service.create_snapshot(suite.id)

  repo = RunRepository(db_session)
  run = repo.create(snapshot.id, agent.id)
  queued = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
      hours=2
  )
  run.created_at = queued
  run.started_at = queued + datetime.timedelta(hours=1)
  run.completed_at = run.started_at + datetime.timedelta(seconds=90)
  run.status = RunStatus.COMPLETED
  db_session.commit()

  recent = repo.get_agent_dashboard_stats(agent.id)["recent_evals"]

  assert len(recent) == 1
  assert recent[0]["started_at"] == run.started_at
  assert recent[0]["duration"] == "1m 30s"


def test_a_queued_run_has_no_start_time_to_report(db_session: Session):
  """started_at is null until a worker takes the run."""
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  agent = agent_repo.create(
      name="Bot",
      config=AgentConfig(project_id="p", location="l", agent_resource_id="r"),
  )
  suite = suite_repo.create(name="Suite")
  snapshot = snapshot_service.create_snapshot(suite.id)

  repo = RunRepository(db_session)
  repo.create(snapshot.id, agent.id)
  db_session.commit()

  recent = repo.get_agent_dashboard_stats(agent.id)["recent_evals"]

  assert recent[0]["started_at"] is None
  assert recent[0]["duration"] == "--"


def test_dashboard_kpis_count_runs_not_trials(db_session: Session):
  """A big run must not outvote a small one in the execution rate.

  The stats query joins trials, so every run-level count has to be distinct on
  the run. It was not: the four trials of the completed run counted four times
  against the one trial of the failed run, and the KPI read 80% instead of 50%.
  Both runs came off the same suite, so active_suites is 1.
  """
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  agent = agent_repo.create(
      name="Bot",
      config=AgentConfig(project_id="p", location="l", agent_resource_id="r"),
  )
  suite = suite_repo.create(name="Suite")
  repo = RunRepository(db_session)

  completed = repo.create(
      snapshot_service.create_snapshot(suite.id).id, agent.id
  )
  completed.status = RunStatus.COMPLETED
  failed = repo.create(snapshot_service.create_snapshot(suite.id).id, agent.id)
  failed.status = RunStatus.FAILED
  db_session.flush()

  for run, trial_count in ((completed, 4), (failed, 1)):
    for i in range(trial_count):
      example = ExampleSnapshot(
          snapshot_suite_id=run.test_suite_snapshot_id,
          question=f"Q{i}",
          original_example_id=i + 1,
          logical_id=f"L{run.id}-{i}",
      )
      db_session.add(example)
      db_session.flush()
      started = datetime.datetime.now(datetime.timezone.utc)
      db_session.add(
          Trial(
              run_id=run.id,
              example_snapshot_id=example.id,
              status=run.status,
              started_at=started,
              completed_at=started + datetime.timedelta(seconds=1),
          )
      )
  db_session.commit()

  stats = repo.get_agent_dashboard_stats(agent.id)

  assert stats["execution_rate"] == 0.5
  assert stats["active_suites"] == 1


def test_a_cancel_that_lands_mid_promotion_is_not_overwritten(
    db_session: Session, session_factory: sessionmaker
):
  """The run the user cancelled must not come back RUNNING.

  promote_next_run reads the oldest PENDING run and writes it RUNNING in a
  second statement. Cancel arrives on the web request thread and can land in
  the gap. The plain assignment put the cancelled run back to RUNNING with
  every trial already CANCELLED, and the aggregator then read it as done and
  completed it. The UPDATE carries its own WHERE status == PENDING for that,
  and the rowcount tells the worker it lost the race.

  Both the extra where() and the rowcount branch can be deleted with every
  other promote test still green, because they all take the rowcount == 1
  path. The cancel here is fired from a second session by a cursor event on
  the SELECT that reads the pending run, which is the one moment the gap is
  open.
  """
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  agent = agent_repo.create(
      name="Bot",
      config=AgentConfig(project_id="p", location="l", agent_resource_id="r"),
  )
  suite = suite_repo.create(name="Suite")
  snapshot = snapshot_service.create_snapshot(suite.id)

  repo = RunRepository(db_session)
  run = repo.create(snapshot.id, agent.id)
  run_id = run.id

  canceller = session_factory()
  fired = []

  def cancel_after_the_pending_select(
      conn, cursor, statement, parameters, context, executemany
  ):
    del conn, cursor, parameters, context, executemany
    # The pending read is the only select on runs that orders the rows. The
    # active read above it has no ORDER BY, and the write below it is not a
    # select at all.
    if fired or "FROM runs" not in statement or "ORDER BY" not in statement:
      return
    fired.append(statement)
    canceller.execute(
        sqlalchemy.update(Run)
        .where(Run.id == run_id)
        .values(status=RunStatus.CANCELLED)
    )
    canceller.commit()

  connection = db_session.connection()
  sqlalchemy.event.listen(
      connection, "after_cursor_execute", cancel_after_the_pending_select
  )
  try:
    promoted = repo.promote_next_run()
  finally:
    sqlalchemy.event.remove(
        connection, "after_cursor_execute", cancel_after_the_pending_select
    )
    canceller.close()

  assert fired, "the pending select never ran, so the race was not driven"
  assert promoted is None

  db_session.refresh(run)
  assert run.status == RunStatus.CANCELLED
  assert run.started_at is None
