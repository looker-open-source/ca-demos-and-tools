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
import pytest
from sqlalchemy.orm import Session


def _setup_test_data(db_session: Session):
  """The FK rows a Trial needs."""
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


@pytest.fixture(name="manager")
def _manager(db_session: Session):
  """The manager, reset either side because it is a singleton.

  Without the reset the constructor hands back a leftover from an earlier
  test, session factory and all. Clearing it on the way out matters just as
  much here: the factory below closes over one test's session, and a later
  test that reaches the manager would get a session that has been closed.
  """
  WorkerProcessManager._instance = None
  yield WorkerProcessManager(session_factory=lambda: db_session)
  WorkerProcessManager._instance = None


def test_worker_retry_clears_stale_data(
    db_session: Session, manager: WorkerProcessManager
):
  run_id, ex_snap_id = _setup_test_data(db_session)

  # A trial carrying everything a previous attempt left on it. RUNNING is the
  # state _check_active_trials hands over: _retry_or_fail no-ops on a terminal
  # status now, so a FAILED trial here would test nothing.
  t = Trial(
      run_id=run_id,
      example_snapshot_id=ex_snap_id,
      status=RunStatus.RUNNING,
      started_at=datetime.datetime.now(datetime.timezone.utc),
      completed_at=datetime.datetime.now(datetime.timezone.utc),
      output_text="stale",
      error_message="stale",
      trace_results=[{"stale": True}],
      trial_pid=424242,
      trial_pid_started_at=1.0,
      retry_count=0,
      max_retries=3,
  )
  db_session.add(t)
  db_session.commit()

  # Reloaded in the session the manager is handed.
  t = db_session.get(Trial, t.id)

  manager._retry_or_fail(db_session, t, "retry reason")  # pylint: disable=protected-access

  assert t.status == RunStatus.PENDING
  assert t.started_at is None
  assert t.completed_at is None
  assert t.output_text is None
  assert t.error_message is None
  assert t.trace_results is None
  assert t.trial_pid is None
  assert t.trial_pid_started_at is None
  assert t.retry_count == 1


def test_execution_service_clears_stale_data(db_session: Session):
  run_id, ex_snap_id = _setup_test_data(db_session)

  # A trial carrying everything a previous attempt left on it.
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

  # COMPLETED first. _execute_trial swallows everything into an except that
  # writes FAILED, so without this a trial that blew up halfway through still
  # satisfies the three assertions below.
  assert t.status == RunStatus.COMPLETED
  assert t.output_text == ""
  assert t.trace_results == []
  assert t.completed_at is not None
  # The retried attempt answered, so the previous attempt's error text must be
  # gone. Leaving it renders a failure message beside a successful answer.
  assert t.error_message is None
