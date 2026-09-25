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

"""The run status the worker's claim writes, and the cancel that races it.

pick_next_pending_trial takes a PENDING trial and promotes its run to RUNNING
on the way past. That promotion reads the run's status and writes it back in
two separate statements, and cancel arrives on the web request thread, so it
lands in between. The unguarded write put the run back to RUNNING with every
one of its trials already CANCELLED, and the aggregator then read it as done
and completed it. It is the same lost update that was closed in
RunRepository.promote_next_run.
"""

from unittest import mock

from prism.common.schemas import execution
from prism.common.schemas.agent import AgentConfig, BigQueryConfig
from prism.server.repositories import trial_repository
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.execution_service import ExecutionService
from prism.server.services.snapshot_service import SnapshotService
import pytest
import sqlalchemy
from sqlalchemy import orm


@pytest.fixture(name="gda_client")
def _gda_client():
  """Answers the two calls create_run makes on the way past."""
  client = mock.MagicMock()
  client.get_agent_context.return_value = {"sys": "test"}
  return client


def _pending_run(db_session: orm.Session, gda_client):
  """A PENDING run with one PENDING trial, which is what a claim promotes."""
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snap_service = SnapshotService(db_session, suite_repo, example_repo)
  exec_service = ExecutionService(db_session, snap_service, gda_client)

  agent = AgentRepository(db_session).create(
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

  run = exec_service.create_run(agent.id, suite.id, concurrency=1)
  db_session.commit()
  return run


def _cancel_before_the_run_is_promoted(worker_session, db_session, run):
  """Cancels the run in the gap the claim leaves between its two statements.

  The claim reads the run's status through the trial it has just taken, then
  writes RUNNING in a statement of its own. This fires as that write reaches
  the database, which is the last moment a cancel can still be lost. It commits
  from the other session, so the claim sees a cancelled row rather than waiting
  on a lock this one holds.
  """
  fired = []

  def before_cursor_execute(
      conn, cursor, statement, parameters, context, executemany
  ):
    del conn, cursor, parameters, context, executemany
    if fired or not statement.lstrip().startswith("UPDATE runs"):
      return
    fired.append(statement)
    run.status = execution.RunStatus.CANCELLED
    db_session.commit()

  sqlalchemy.event.listen(
      worker_session.connection(),
      "before_cursor_execute",
      before_cursor_execute,
  )


def _reread(db_session: orm.Session, row):
  """Reads a row back after the claim committed from its own session."""
  db_session.commit()
  db_session.expire_all()
  return db_session.get(type(row), row.id)


def test_a_cancel_landing_inside_the_claim_is_not_written_over(
    db_session, gda_client, session_factory
):
  """The run came back RUNNING with all of its trials CANCELLED.

  Nothing was left to execute it, so it never reached a terminal status of its
  own, and promote_next_run will not promote past a run that is still going.
  One cancel on the wrong tick stopped the whole queue behind it.
  """
  run = _pending_run(db_session, gda_client)

  worker_session = session_factory()
  try:
    _cancel_before_the_run_is_promoted(worker_session, db_session, run)
    trial_repository.TrialRepository(worker_session).pick_next_pending_trial(
        run_id=run.id
    )
  finally:
    worker_session.close()

  after = _reread(db_session, run)
  assert after.status == execution.RunStatus.CANCELLED, (
      "The claim promoted a run that had just been cancelled, so it is RUNNING"
      " with nothing to run."
  )
  assert after.started_at is None


def test_a_claim_still_promotes_the_run_it_took_the_trial_from(
    db_session, gda_client, session_factory
):
  """Guards the check above. Promoting on the first claim is the normal path.

  The worker reads its run once at the top of a pass, so a run left PENDING
  here is one nothing ever starts.
  """
  run = _pending_run(db_session, gda_client)

  worker_session = session_factory()
  try:
    trial = trial_repository.TrialRepository(
        worker_session
    ).pick_next_pending_trial(run_id=run.id)
  finally:
    worker_session.close()

  assert trial is not None
  after = _reread(db_session, run)
  assert after.status == execution.RunStatus.RUNNING
  assert after.started_at is not None
