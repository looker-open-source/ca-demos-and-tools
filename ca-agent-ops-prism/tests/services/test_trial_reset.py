import datetime
import unittest.mock

from prism.common.schemas.execution import RunStatus
from prism.server.models.agent import Agent
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.server.models.snapshot import ExampleSnapshot
from prism.server.models.snapshot import TestSuiteSnapshot
from prism.server.services.execution_service import ExecutionService
from prism.server.services.worker import WorkerProcessManager
from sqlalchemy.orm import Session


def _setup_test_data(db_session: Session):
  """Helper to setup required FK data."""
  agent = Agent(
      name="Test Agent",
      project_id="p",
      location="l",
      agent_resource_id="r",
  )
  db_session.add(agent)
  db_session.flush()

  suite_snap = TestSuiteSnapshot(name="Test Suite", original_suite_id=1)
  db_session.add(suite_snap)
  db_session.flush()

  run = Run(
      agent_id=agent.id,
      test_suite_snapshot_id=suite_snap.id,
      status=RunStatus.RUNNING,
      is_archived=False,
  )
  db_session.add(run)
  db_session.flush()

  ex_snap = ExampleSnapshot(
      snapshot_suite_id=suite_snap.id,
      question="Test Question",
      original_example_id=1,
      logical_id="L1",
  )
  db_session.add(ex_snap)
  db_session.flush()
  return run.id, ex_snap.id


def test_worker_retry_clears_stale_data(db_session: Session):
  """Tests that worker._retry_or_fail clears stale fields."""
  run_id, ex_snap_id = _setup_test_data(db_session)

  # Setup Trial with stale data
  t = Trial(
      run_id=run_id,
      example_snapshot_id=ex_snap_id,
      status=RunStatus.FAILED,
      started_at=datetime.datetime.now(datetime.timezone.utc),
      completed_at=datetime.datetime.now(datetime.timezone.utc),
      output_text="stale",
      error_message="stale",
      trace_results=[{"stale": True}],
      retry_count=0,
      max_retries=3,
  )
  db_session.add(t)
  db_session.commit()  # Commit to start fresh

  manager = WorkerProcessManager(session_factory=lambda: db_session)

  # Reload t in the same session to be sure
  t = db_session.get(Trial, t.id)

  manager._retry_or_fail(db_session, t, "retry reason")  # pylint: disable=protected-access

  assert t.status == RunStatus.PENDING
  assert t.started_at is None
  assert t.completed_at is None
  assert t.output_text is None
  assert t.error_message is None
  assert t.trace_results is None
  assert t.retry_count == 1


def test_execution_service_clears_stale_data(db_session: Session):
  """Tests that execution_service._execute_trial clears stale fields at start."""
  run_id, ex_snap_id = _setup_test_data(db_session)

  # Setup Trial with stale data
  t = Trial(
      run_id=run_id,
      example_snapshot_id=ex_snap_id,
      status=RunStatus.PENDING,
      started_at=datetime.datetime.now(datetime.timezone.utc),
      completed_at=datetime.datetime.now(datetime.timezone.utc),
      output_text="stale",
      error_message="stale",
      trace_results=[{"stale": True}],
  )
  db_session.add(t)
  db_session.flush()

  # Mock dependencies
  mock_snap = unittest.mock.MagicMock()
  mock_client = unittest.mock.MagicMock()
  mock_response = unittest.mock.MagicMock()
  mock_response.protobuf_response = []
  mock_response.error_message = None
  mock_client.ask_question.return_value = mock_response

  service = ExecutionService(
      session=db_session, snapshot_service=mock_snap, client=mock_client
  )

  mock_agent = unittest.mock.MagicMock()
  mock_agent.project_id = "p"
  mock_agent.location = "l"
  mock_agent.agent_resource_id = "r"
  mock_agent.looker_client_id = None
  mock_agent.looker_client_secret = None

  service._execute_trial(t, mock_agent)  # pylint: disable=protected-access

  assert t.output_text == ""
  assert t.trace_results == []
  assert t.completed_at is not None
