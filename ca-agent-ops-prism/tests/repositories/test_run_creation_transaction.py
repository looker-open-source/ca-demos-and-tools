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

"""A run and its trials have to reach the database together.

RunRepository.create used to commit the run on its own and ExecutionService
then committed one trial at a time. The worker loop runs every two seconds,
and _aggregate_run_statuses works off list_active, which picks up a PENDING
run. A run committed without its trials has nothing left to wait for, so the
aggregator completed it and the run finished before its first question was
asked.

The window is small and the test does not try to hit it. It watches every
state another process could have read instead: at each commit, a second
session reads the runs table, and a run that is visible there has to have its
trials.
"""

from unittest import mock

from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import BigQueryConfig
from prism.common.schemas.execution import RunStatus
from prism.server.models.run import Run
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.run_repository import RunRepository
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


def _agent(db_session: orm.Session):
  return AgentRepository(db_session).create(
      name="Bot",
      config=AgentConfig(
          project_id="p",
          location="l",
          agent_resource_id="r",
          datasource=BigQueryConfig(tables=["t"]),
      ),
  )


def _suite(db_session: orm.Session, *questions: str):
  suite = SuiteRepository(db_session).create(name="Suite")
  example_repo = ExampleRepository(db_session)
  for question in questions:
    example_repo.create(suite.id, question)
  db_session.commit()
  return suite


def _exec_service(db_session: orm.Session, gda_client) -> ExecutionService:
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snap_service = SnapshotService(db_session, suite_repo, example_repo)
  return ExecutionService(db_session, snap_service, gda_client)


def test_no_commit_leaves_a_run_without_its_trials(
    db_session: orm.Session, session_factory: orm.sessionmaker, gda_client
):
  """What the worker would have seen, at every point it could have looked."""
  agent = _agent(db_session)
  suite = _suite(db_session, "Q1", "Q2", "Q3")

  seen = []

  # Keyed on this test's agent. The test database is shared, so reading the
  # whole runs table picks up rows another test is part way through writing.
  @sqlalchemy.event.listens_for(db_session, "after_commit")
  def _read_from_another_session(session):
    del session
    with session_factory() as observer:
      seen.append([
          (run.id, len(run.trials))
          for run in observer.scalars(
              sqlalchemy.select(Run).where(Run.agent_id == agent.id)
          ).all()
      ])

  try:
    run = _exec_service(db_session, gda_client).create_run(agent.id, suite.id)
  finally:
    sqlalchemy.event.remove(
        db_session, "after_commit", _read_from_another_session
    )

  assert len(run.trials) == 3
  assert any(
      state for state in seen
  ), "The observer never saw the run, so this proves nothing."
  for state in seen:
    for run_id, trial_count in state:
      assert trial_count == 3, (
          f"Run {run_id} was committed with {trial_count} trials. The worker"
          " would have completed it before it ran."
      )


def test_an_empty_suite_still_makes_a_trial_less_run(db_session: orm.Session):
  """The case _aggregate_run_statuses completes on purpose.

  create_run refuses an empty suite now, but the repository is what the worker
  tests and the older rows rely on, and a run with no trials must still be
  creatable or an empty suite jams the queue behind it.
  """
  agent = _agent(db_session)
  suite = _suite(db_session)
  snap_service = SnapshotService(
      db_session, SuiteRepository(db_session), ExampleRepository(db_session)
  )
  snapshot = snap_service.create_snapshot(suite.id)

  run = RunRepository(db_session).create(snapshot.id, agent.id)

  assert run.trials == []
  assert run.status == RunStatus.PENDING
