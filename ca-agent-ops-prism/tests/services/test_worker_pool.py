import datetime
import logging
import multiprocessing
import os
import threading
import time
from typing import Any
import unittest.mock

from prism.common.schemas import execution
from prism.common.schemas.agent import AgentConfig, AgentEnv, BigQueryConfig
from prism.server import db
from prism.server.models import run as run_models
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.repositories.trial_repository import TrialRepository
from prism.server.services.execution_service import ExecutionService
from prism.server.services.snapshot_service import SnapshotService
from prism.server.services.worker import WorkerProcessManager
import psutil
import pytest


class MockProcess:
  """Mock for multiprocessing.Process that runs in a thread."""

  def __init__(self, target, args=(), kwargs=None, daemon=False):
    self.target = target
    self.args = args
    self.kwargs = kwargs or {}
    self.daemon = daemon
    self.pid = 12345
    self._thread = None

  def start(self):
    self._thread = threading.Thread(
        target=self.target, args=self.args, kwargs=self.kwargs, daemon=True
    )
    self._thread.start()

  def is_alive(self):
    return self._thread.is_alive() if self._thread else False

  def join(self, timeout=None):
    if self._thread:
      self._thread.join(timeout)


@pytest.fixture
def mock_gda_client():
  with unittest.mock.patch(
      "prism.server.clients.gemini_data_analytics_client.GeminiDataAnalyticsClient"
  ) as mock:
    client_instance = mock.return_value
    client_instance.get_agent_context.return_value = {"sys": "test"}
    # Mock ask_question
    response_mock = unittest.mock.MagicMock()
    response_mock.protobuf_response = []
    response_mock.duration = unittest.mock.MagicMock(total_duration=50)
    response_mock.error_message = None
    client_instance.ask_question.return_value = response_mock
    yield client_instance


def test_worker_pool_resiliency(
    db_session: db.SessionLocal,
    mock_gda_client: unittest.mock.MagicMock,
    session_factory: Any,
):
  """Tests that worker manager picks up trials and handles basic execution."""
  # Reset singleton
  WorkerProcessManager._instance = None
  worker_service = WorkerProcessManager(
      max_concurrent_trials=2, session_factory=session_factory
  )

  # Mock multiprocessing and psutil
  mock_ctx = unittest.mock.MagicMock()
  mock_ctx.Process = MockProcess

  mock_psutil_p = unittest.mock.MagicMock()
  mock_psutil_p.is_running.return_value = True
  mock_psutil_p.status.return_value = psutil.STATUS_RUNNING

  with (
      unittest.mock.patch("multiprocessing.get_context", return_value=mock_ctx),
      unittest.mock.patch("psutil.Process", return_value=mock_psutil_p),
  ):
    # Start manager
    worker_service.start()
    try:
      # 1. Setup Data
      agent_repo = AgentRepository(db_session)
      suite_repo = SuiteRepository(db_session)
      example_repo = ExampleRepository(db_session)
      snap_service = SnapshotService(db_session, suite_repo, example_repo)
      exec_service = ExecutionService(db_session, snap_service, mock_gda_client)

      config = AgentConfig(
          project_id="p",
          location="l",
          agent_resource_id="r",
          env=AgentEnv.STAGING,
          datasource=BigQueryConfig(tables=["t1"]),
      )
      agent = agent_repo.create(name="Bot", config=config)
      suite = suite_repo.create(name="Suite")
      example_repo.create(suite.id, "Q1")
      db_session.commit()

      run = exec_service.create_run(agent.id, suite.id)
      run.status = execution.RunStatus.RUNNING
      db_session.commit()
      trial_id = run.trials[0].id

      # 2. Wait for manager to spawn and thread to finish
      max_wait = 20
      start_time = time.time()
      found = False
      while time.time() - start_time < max_wait:
        db_session.expire_all()
        t = db_session.get(run_models.Trial, trial_id)
        if t and t.status == execution.RunStatus.COMPLETED:
          found = True
          break
        time.sleep(1.0)

      assert found is True
      assert t.trial_pid == 12345

    finally:
      worker_service.stop()


def test_stale_trial_recovery(
    db_session: db.SessionLocal,
    session_factory: Any,
    mock_gda_client: unittest.mock.MagicMock,
):
  """Tests fallback recovery for very old trials."""
  WorkerProcessManager._instance = None

  # Setup Data
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snap_service = SnapshotService(db_session, suite_repo, example_repo)
  exec_service = ExecutionService(db_session, snap_service, mock_gda_client)

  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
      env=AgentEnv.STAGING,
      datasource=BigQueryConfig(tables=["t1"]),
  )
  agent = agent_repo.create(name="Stale Bot", config=config)
  suite = suite_repo.create(name="Stale Suite")
  example_repo.create(suite.id, "Q1")
  db_session.commit()

  run = exec_service.create_run(agent.id, suite.id)
  run.status = execution.RunStatus.RUNNING
  db_session.commit()

  stale_time = datetime.datetime.now(
      datetime.timezone.utc
  ) - datetime.timedelta(minutes=40)
  trial = run.trials[0]
  trial.status = execution.RunStatus.RUNNING
  trial.started_at = stale_time
  trial.trial_pid = 99999
  db_session.commit()

  worker_service = WorkerProcessManager(
      max_concurrent_trials=1, session_factory=session_factory
  )
  # One loop pass including recovery
  worker_service._recover_stale_trials()

  db_session.refresh(trial)
  assert trial.status == execution.RunStatus.PENDING
  assert trial.trial_pid is None
  assert trial.started_at is None
