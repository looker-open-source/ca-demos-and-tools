import datetime
import unittest.mock

from prism.common.schemas import execution
from prism.common.schemas.agent import AgentConfig, BigQueryConfig
from prism.server import db
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.execution_service import ExecutionService
from prism.server.services.snapshot_service import SnapshotService
from prism.server.services.worker import WorkerProcessManager
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
    pass
    # We don't actually need to run the target for queue logic tests
    # just need to simulate the process starting if needed

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
  # Reset singleton
  WorkerProcessManager._instance = None

  # Mock multiprocessing to prevent actual spawning
  with unittest.mock.patch("multiprocessing.get_context") as mock_ctx:
    mock_ctx.return_value.Process = MockProcess
    manager = WorkerProcessManager(
        max_concurrent_trials=2, session_factory=session_factory
    )
    yield manager
    manager.stop()


def create_run(
    db_session, agent, suite, exec_service, status=execution.RunStatus.PENDING
):
  run = exec_service.create_run(agent.id, suite.id)
  run.status = status
  if status == execution.RunStatus.RUNNING:
    run.started_at = datetime.datetime.now(datetime.timezone.utc)
  db_session.commit()
  return run


def test_auto_promotion(
    db_session: db.SessionLocal,
    worker_service: WorkerProcessManager,
    mock_gda_client: unittest.mock.MagicMock,
):
  """Verifies that a PENDING run is automatically promoted to RUNNING."""
  # Setup
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

  # Create PENDING run
  run = create_run(
      db_session, agent, suite, exec_service, status=execution.RunStatus.PENDING
  )

  # Run worker logic manually
  worker_service._start_new_trials()

  db_session.refresh(run)
  assert run.status == execution.RunStatus.RUNNING
  assert run.started_at is not None


def test_fifo_enforcement(
    db_session: db.SessionLocal,
    worker_service: WorkerProcessManager,
    mock_gda_client: unittest.mock.MagicMock,
):
  """Verifies that a new run waits if another run is already RUNNING."""
  # Setup
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

  # Create RUNNING run (simulation of active run)
  run1 = create_run(
      db_session, agent, suite, exec_service, status=execution.RunStatus.RUNNING
  )

  # Create PENDING run
  run2 = create_run(
      db_session, agent, suite, exec_service, status=execution.RunStatus.PENDING
  )

  # Run worker logic
  worker_service._start_new_trials()

  db_session.refresh(run1)
  db_session.refresh(run2)

  # Run 1 should still be RUNNING
  assert run1.status == execution.RunStatus.RUNNING
  # Run 2 should still be PENDING (blocked)
  assert run2.status == execution.RunStatus.PENDING


def test_queue_ordering(
    db_session: db.SessionLocal,
    worker_service: WorkerProcessManager,
    mock_gda_client: unittest.mock.MagicMock,
):
  """Verifies that the oldest PENDING run is promoted first."""
  # Setup
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

  # Create Run 1 (Older)
  run1 = create_run(
      db_session, agent, suite, exec_service, status=execution.RunStatus.PENDING
  )
  # Manually backdate creation time to ensure strict ordering
  run1.created_at = datetime.datetime.now(
      datetime.timezone.utc
  ) - datetime.timedelta(minutes=10)
  db_session.commit()

  # Create Run 2 (Newer)
  run2 = create_run(
      db_session, agent, suite, exec_service, status=execution.RunStatus.PENDING
  )

  # Run worker logic
  worker_service._start_new_trials()

  db_session.refresh(run1)
  db_session.refresh(run2)

  # Oldest run should be promoted
  assert run1.status == execution.RunStatus.RUNNING
  # Newer run should wait
  assert run2.status == execution.RunStatus.PENDING
