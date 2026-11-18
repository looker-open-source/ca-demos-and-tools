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

"""PostgreSQL integration tests for Scheduled Evaluations."""

from concurrent import futures
import datetime
import threading
from unittest import mock

from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import BigQueryConfig
from prism.common.schemas.execution import RunStatus
from prism.common.schemas.schedule import ScheduleCadence
from prism.common.schemas.schedule import ScheduleCreate
from prism.common.schemas.schedule import SKIPPED_ACTIVE_RUN_MESSAGE
from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
from prism.server.models.run import Run
from prism.server.models.schedule import EvalSchedule
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.schedule_repository import ScheduleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.execution_service import ExecutionService
from prism.server.services.schedule_service import ScheduleService
from prism.server.services.snapshot_service import SnapshotService
from prism.server.services.worker import WorkerProcessManager
import pytest
import sqlalchemy
from sqlalchemy import orm

_UTC = datetime.timezone.utc


def _seed_agent_and_suite(session: orm.Session):
  """Seeds a BigQuery Agent and TestSuite in PostgreSQL."""
  agent = AgentRepository(session).create(
      name="PG Sched Agent",
      config=AgentConfig(
          project_id="pg-proj",
          location="global",
          agent_resource_id="pg-agent-1",
          datasource=BigQueryConfig(tables=["pg-proj.ds.orders"]),
      ),
  )
  suite = SuiteRepository(session).create(name="PG Sched Suite")
  ExampleRepository(session).create(suite.id, "Count rows in orders.")
  return agent.id, suite.id


def test_concurrent_workers_claim_due_schedules_once_with_skip_locked(
    session_factory: orm.sessionmaker,
):
  """Four concurrent threads against PostgreSQL create exactly one run per due schedule."""
  past = datetime.datetime(2026, 10, 30, 8, 0, tzinfo=_UTC)
  now = datetime.datetime(2026, 10, 30, 9, 5, tzinfo=_UTC)

  with session_factory() as seed_session:
    agent_id, suite_id = _seed_agent_and_suite(seed_session)
    sched_repo = ScheduleRepository(seed_session)
    for idx in range(3):
      sched_repo.create(
          name=f"Concurrent Schedule {idx}",
          agent_id=agent_id,
          test_suite_id=suite_id,
          cadence="HOURLY",
          cron_expression="0 * * * *",
          timezone="UTC",
          generate_suggestions=False,
          concurrency=2,
          is_enabled=True,
          next_run_at=past + datetime.timedelta(minutes=idx),
      )

  def _worker_tick() -> list[int]:
    with session_factory() as worker_session:
      gda_client = mock.MagicMock(spec=GeminiDataAnalyticsClient)
      gda_client.get_datasource_kind.return_value = "bq"
      gda_client.get_agent_context.return_value = {
          "system_instruction": "Concise SQL."
      }
      snap = SnapshotService(
          worker_session,
          SuiteRepository(worker_session),
          ExampleRepository(worker_session),
      )
      exec_svc = ExecutionService(worker_session, snap, gda_client)
      sched_svc = ScheduleService(
          worker_session,
          ScheduleRepository(worker_session),
          exec_svc,
      )
      res = sched_svc.process_due_schedules(now=now, limit=10)
      return res.triggered_run_ids

  with futures.ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(lambda _: _worker_tick(), range(4)))

  triggered_ids: list[int] = []
  for batch in results:
    triggered_ids.extend(batch)
  assert len(triggered_ids) == 3
  assert len(set(triggered_ids)) == 3

  with session_factory() as check_session:
    runs = check_session.execute(sqlalchemy.select(Run)).scalars().all()
    assert len(runs) == 3
    assert len({r.schedule_id for r in runs}) == 3
    schedules = (
        check_session.execute(sqlalchemy.select(EvalSchedule)).scalars().all()
    )
    for sched in schedules:
      assert sched.next_run_at == datetime.datetime(
          2026, 10, 30, 10, 0, tzinfo=_UTC
      )
      assert sched.last_run_id is not None


def test_worker_process_manager_dispatches_due_schedule_and_respects_overlap(
    session_factory: orm.sessionmaker,
):
  """WorkerProcessManager._process_due_schedules queues due runs and skips active overlaps."""
  past = datetime.datetime.now(_UTC) - datetime.timedelta(minutes=10)
  with session_factory() as seed_session:
    agent_id, suite_id = _seed_agent_and_suite(seed_session)
    sched = ScheduleRepository(seed_session).create(
        name="Worker Managed Schedule",
        agent_id=agent_id,
        test_suite_id=suite_id,
        cadence="HOURLY",
        cron_expression="0 * * * *",
        timezone="UTC",
        generate_suggestions=False,
        concurrency=3,
        is_enabled=True,
        next_run_at=past,
    )
    sched_id = sched.id

  gda_mock = mock.MagicMock(spec=GeminiDataAnalyticsClient)
  gda_mock.__enter__.return_value = gda_mock
  gda_mock.__exit__.return_value = None
  gda_mock.get_datasource_kind.return_value = "bq"
  gda_mock.get_agent_context.return_value = {"system_instruction": "Worker ctx"}

  manager = object.__new__(WorkerProcessManager)
  manager.session_factory = session_factory

  # pylint: disable=protected-access
  with mock.patch(
      "prism.server.clients.gemini_data_analytics_client.GeminiDataAnalyticsClient",
      return_value=gda_mock,
  ):
    manager._process_due_schedules()

  with session_factory() as check_session:
    runs = (
        check_session.execute(
            sqlalchemy.select(Run).where(Run.schedule_id == sched_id)
        )
        .scalars()
        .all()
    )
    assert len(runs) == 1
    first_run_id = runs[0].id
    assert runs[0].status == RunStatus.PENDING
    assert runs[0].concurrency == 3

    # Force schedule due again while first_run_id is RUNNING: overlap skip must
    # prevent creating a second run.
    runs[0].status = RunStatus.RUNNING
    sched_row = check_session.get(EvalSchedule, sched_id)
    sched_row.next_run_at = datetime.datetime.now(_UTC) - datetime.timedelta(
        minutes=1
    )
    check_session.commit()

  with mock.patch(
      "prism.server.clients.gemini_data_analytics_client.GeminiDataAnalyticsClient",
      return_value=gda_mock,
  ):
    manager._process_due_schedules()

  with session_factory() as check_session:
    runs = (
        check_session.execute(
            sqlalchemy.select(Run).where(Run.schedule_id == sched_id)
        )
        .scalars()
        .all()
    )
    assert len(runs) == 1

    # Once first_run_id reaches COMPLETED and the schedule becomes due again,
    # the next worker tick creates Run #2.
    runs[0].status = RunStatus.COMPLETED
    sched_row = check_session.get(EvalSchedule, sched_id)
    sched_row.next_run_at = datetime.datetime.now(_UTC) - datetime.timedelta(
        minutes=1
    )
    check_session.commit()

  with mock.patch(
      "prism.server.clients.gemini_data_analytics_client.GeminiDataAnalyticsClient",
      return_value=gda_mock,
  ):
    manager._process_due_schedules()
  # pylint: enable=protected-access

  with session_factory() as check_session:
    runs = (
        check_session.execute(
            sqlalchemy.select(Run).where(Run.schedule_id == sched_id)
        )
        .scalars()
        .all()
    )
    assert len(runs) == 2
    assert {r.id for r in runs} > {first_run_id}


def test_deleting_schedule_row_sets_run_schedule_id_to_null(
    session_factory: orm.sessionmaker,
):
  """Deleting an eval_schedules row preserves historical runs via ON DELETE SET NULL."""
  with session_factory() as session:
    agent_id, suite_id = _seed_agent_and_suite(session)
    gda_client = mock.MagicMock(spec=GeminiDataAnalyticsClient)
    gda_client.get_datasource_kind.return_value = "bq"
    gda_client.get_agent_context.return_value = {"system_instruction": "Ctx"}
    snap = SnapshotService(
        session, SuiteRepository(session), ExampleRepository(session)
    )
    exec_svc = ExecutionService(session, snap, gda_client)
    sched_svc = ScheduleService(session, ScheduleRepository(session), exec_svc)

    sched = sched_svc.create_schedule(
        ScheduleCreate(
            name="Ephemeral Schedule",
            agent_id=agent_id,
            test_suite_id=suite_id,
            cadence=ScheduleCadence.DAILY,
            cron_expression="0 9 * * *",
            timezone="UTC",
        )
    )
    run = sched_svc.trigger_schedule_now(sched.id)
    run_id = run.id
    sched_id = sched.id

  with session_factory() as session:
    session.execute(
        sqlalchemy.delete(EvalSchedule).where(EvalSchedule.id == sched_id)
    )
    session.commit()

  with session_factory() as session:
    surviving = session.get(Run, run_id)
    assert surviving is not None
    assert surviving.schedule_id is None


def _slow_gda(started: threading.Event, release: threading.Event):
  """A GDA fake whose get_agent_context blocks until `release` is set.

  create_run calls it after create_snapshot has committed, which is the window
  where the schedule row lock is gone and no Run row exists yet.

  Args:
    started: Set when the call begins.
    release: Waited on before the call returns.

  Returns:
    The fake client.
  """
  gda = mock.MagicMock(spec=GeminiDataAnalyticsClient)
  gda.get_datasource_kind.return_value = "bq"

  def blocking_context(**_kwargs):
    started.set()
    assert release.wait(timeout=10), "test never released the slow GDA call"
    return {"system_instruction": "slow ctx"}

  gda.get_agent_context.side_effect = blocking_context
  return gda


def _schedule_service(session: orm.Session, gda) -> ScheduleService:
  """Builds a ScheduleService on `session` backed by the `gda` fake."""
  snap = SnapshotService(
      session, SuiteRepository(session), ExampleRepository(session)
  )
  return ScheduleService(
      session,
      ScheduleRepository(session),
      ExecutionService(session, snap, gda),
  )


def _seed_due_schedule(session_factory: orm.sessionmaker) -> int:
  """Seeds an enabled hourly schedule that is already due, returning its id."""
  with session_factory() as seed_session:
    agent_id, suite_id = _seed_agent_and_suite(seed_session)
    sched = ScheduleRepository(seed_session).create(
        name="Race Schedule",
        agent_id=agent_id,
        test_suite_id=suite_id,
        cadence="HOURLY",
        cron_expression="0 * * * *",
        timezone="UTC",
        generate_suggestions=False,
        concurrency=2,
        is_enabled=True,
        next_run_at=datetime.datetime.now(_UTC) - datetime.timedelta(minutes=5),
    )
    return sched.id


def _runs_for(session_factory: orm.sessionmaker, sched_id: int) -> list[Run]:
  """Returns every Run the schedule has created."""
  with session_factory() as check_session:
    return list(
        check_session.execute(
            sqlalchemy.select(Run).where(Run.schedule_id == sched_id)
        ).scalars()
    )


def test_concurrent_run_now_during_slow_agent_context_starts_one_run(
    session_factory: orm.sessionmaker,
):
  """A second Run Now while the first waits on GDA is refused, not duplicated."""
  sched_id = _seed_due_schedule(session_factory)
  started, release = threading.Event(), threading.Event()
  gda = _slow_gda(started, release)

  def first_run_now():
    with session_factory() as session:
      return _schedule_service(session, gda).trigger_schedule_now(sched_id).id

  with futures.ThreadPoolExecutor(max_workers=1) as pool:
    first = pool.submit(first_run_now)
    assert started.wait(timeout=30)
    try:
      with session_factory() as session:
        with pytest.raises(ValueError, match="already has an active run"):
          _schedule_service(session, gda).trigger_schedule_now(sched_id)
      # Refused before create_run, so it never reached the slow GDA call.
      assert gda.get_agent_context.call_count == 1
    finally:
      release.set()
    first_run_id = first.result(timeout=30)

  runs = _runs_for(session_factory, sched_id)
  assert [r.id for r in runs] == [first_run_id]


def test_worker_tick_during_slow_run_now_skips_instead_of_duplicating(
    session_factory: orm.sessionmaker,
):
  """The worker skips a due schedule whose Run Now is still inside create_run."""
  sched_id = _seed_due_schedule(session_factory)
  started, release = threading.Event(), threading.Event()
  gda = _slow_gda(started, release)

  def run_now():
    with session_factory() as session:
      return _schedule_service(session, gda).trigger_schedule_now(sched_id).id

  with futures.ThreadPoolExecutor(max_workers=1) as pool:
    manual = pool.submit(run_now)
    assert started.wait(timeout=30)
    try:
      with session_factory() as session:
        tick = _schedule_service(session, gda).process_due_schedules()
      with session_factory() as check_session:
        mid_flight = check_session.get(EvalSchedule, sched_id)
        assert mid_flight.last_error_message == SKIPPED_ACTIVE_RUN_MESSAGE
        assert mid_flight.dispatch_started_at is not None
    finally:
      release.set()
    manual_run_id = manual.result(timeout=30)

  assert tick.skipped_overlap_schedule_ids == [sched_id]
  assert not tick.triggered_run_ids
  assert [r.id for r in _runs_for(session_factory, sched_id)] == [manual_run_id]
  with session_factory() as check_session:
    sched = check_session.get(EvalSchedule, sched_id)
    # The Run Now that blocked the tick succeeded, which clears the skip.
    assert sched.last_error_message is None
    assert sched.dispatch_started_at is None
    assert sched.last_run_id == manual_run_id


def test_run_now_during_slow_worker_dispatch_is_refused(
    session_factory: orm.sessionmaker,
):
  """Run Now is refused while the worker is still inside create_run."""
  sched_id = _seed_due_schedule(session_factory)
  started, release = threading.Event(), threading.Event()
  gda = _slow_gda(started, release)

  def worker_tick():
    with session_factory() as session:
      return _schedule_service(session, gda).process_due_schedules()

  with futures.ThreadPoolExecutor(max_workers=1) as pool:
    tick_future = pool.submit(worker_tick)
    assert started.wait(timeout=30)
    try:
      with session_factory() as session:
        with pytest.raises(ValueError, match="already has an active run"):
          _schedule_service(session, gda).trigger_schedule_now(sched_id)
      assert gda.get_agent_context.call_count == 1
    finally:
      release.set()
    tick = tick_future.result(timeout=30)

  runs = _runs_for(session_factory, sched_id)
  assert len(runs) == 1
  assert tick.triggered_run_ids == [runs[0].id]
  with session_factory() as check_session:
    assert check_session.get(EvalSchedule, sched_id).dispatch_started_at is None
