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

"""Which run the worker feeds, and in what order.

Only one run executes at a time, so getting this wrong is not a scheduling
nicety. Two runs going at once means two sets of workers calling the agent API
and billing for it, and a run that is skipped never finishes, which stops
everything queued behind it as well.
"""

import datetime
import unittest.mock

from prism.common.schemas import execution
from prism.common.schemas.agent import AgentConfig, BigQueryConfig
from prism.server import db
from prism.server.models.run import Trial
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.execution_service import ExecutionService
from prism.server.services.snapshot_service import SnapshotService
from prism.server.services.worker import WorkerProcessManager
import pytest
import sqlalchemy


class MockProcess:
  """Stands in for multiprocessing.Process."""

  def __init__(self, target, args=(), kwargs=None, daemon=False):
    self.target = target
    self.args = args
    self.kwargs = kwargs or {}
    self.daemon = daemon
    self.pid = 12345
    self._thread = None

  def start(self):
    # These tests only check run promotion, so the target never has to run.
    pass

  def is_alive(self):
    return True

  def join(self, timeout=None):
    pass


@pytest.fixture
def mock_gda_client():
  with unittest.mock.patch(
      "prism.server.clients.gemini_data_analytics_client.GeminiDataAnalyticsClient"
  ) as mock:
    mock.return_value.get_agent_context.return_value = {"foo": "bar"}
    yield mock.return_value


@pytest.fixture
def worker_service(session_factory):
  # The manager is a singleton, so without this the constructor hands back a
  # leftover from an earlier test, session factory and all. Cleared on the way
  # out too: this one is bound to a session factory whose tables are dropped at
  # teardown, and get_worker_pool_service would hand it to whichever test runs
  # next.
  WorkerProcessManager._instance = None

  # Patched so nothing is actually spawned.
  with unittest.mock.patch("multiprocessing.get_context") as mock_ctx:
    mock_ctx.return_value.Process = MockProcess
    manager = WorkerProcessManager(session_factory=session_factory)
    yield manager
    manager.stop()
    WorkerProcessManager._instance = None


@pytest.fixture(name="queue")
def _queue(db_session, mock_gda_client):
  """One agent and one question, plus a create_run bound to them."""
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snap_service = SnapshotService(db_session, suite_repo, example_repo)
  exec_service = ExecutionService(db_session, snap_service, mock_gda_client)

  agent = agent_repo.create(
      name="Bot",
      config=AgentConfig(
          project_id="p",
          location="l",
          agent_resource_id="r",
          datasource=BigQueryConfig(tables=["t"]),
      ),
  )
  suite = suite_repo.create(name="Suite")
  example_repo.create(suite.id, "Q1")
  db_session.commit()

  def create_run(status=execution.RunStatus.PENDING, minutes_ago=0):
    run = exec_service.create_run(agent.id, suite.id)
    run.status = status
    now = datetime.datetime.now(datetime.timezone.utc)
    if status == execution.RunStatus.RUNNING:
      run.started_at = now
    # Runs made in one test land in the same second, and the queue orders by
    # created_at, so anything about ordering has to space them out itself.
    if minutes_ago:
      run.created_at = now - datetime.timedelta(minutes=minutes_ago)
    db_session.commit()
    return run

  return create_run


def test_auto_promotion(
    db_session: db.SessionLocal,
    worker_service: WorkerProcessManager,
    queue,
):
  """A PENDING run is promoted to RUNNING."""
  run = queue()

  worker_service._start_new_trials()

  db_session.refresh(run)
  assert run.status == execution.RunStatus.RUNNING
  assert run.started_at is not None


def test_fifo_enforcement(
    db_session: db.SessionLocal,
    worker_service: WorkerProcessManager,
    queue,
):
  """A new run waits while another run is RUNNING."""
  run1 = queue(status=execution.RunStatus.RUNNING)
  run2 = queue()

  worker_service._start_new_trials()

  db_session.refresh(run1)
  db_session.refresh(run2)

  assert run1.status == execution.RunStatus.RUNNING
  assert run2.status == execution.RunStatus.PENDING


def test_queue_ordering(
    db_session: db.SessionLocal,
    worker_service: WorkerProcessManager,
    queue,
):
  """The oldest PENDING run is promoted first."""
  run1 = queue(minutes_ago=10)
  run2 = queue()

  worker_service._start_new_trials()

  db_session.refresh(run1)
  db_session.refresh(run2)

  assert run1.status == execution.RunStatus.RUNNING
  assert run2.status == execution.RunStatus.PENDING


def test_the_older_of_two_running_runs_is_the_one_fed(
    db_session: db.SessionLocal,
    worker_service: WorkerProcessManager,
    queue,
):
  """Two RUNNING runs is rare, and it used to strand the older one.

  The pass read its run off list_all, which orders newest first, while
  promote_next_run takes the oldest. So on the rare occasion both were RUNNING
  the worker fed the run the queue had not reached yet and the older one sat
  there with its trials unclaimed, which stopped it finishing and stopped
  everything behind it too.
  """
  older = queue(status=execution.RunStatus.RUNNING, minutes_ago=10)
  newer = queue(status=execution.RunStatus.RUNNING)

  worker_service._start_new_trials()

  # MockProcess reports a PID that does not exist, so the pass claims the
  # trial, fails to record the process behind it and hands the trial back with
  # a retry spent. Which trial that happened to is what identifies the run the
  # pass chose.
  db_session.expire_all()
  touched = db_session.scalars(
      sqlalchemy.select(Trial).where(Trial.retry_count > 0)
  ).all()
  assert [trial.run_id for trial in touched] == [older.id]

  db_session.refresh(newer)
  assert [t.status for t in newer.trials] == [execution.RunStatus.PENDING]
