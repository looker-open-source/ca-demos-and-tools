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

"""The two arguments that narrow what a run query hands back.

``get_agent_dashboard_stats(days=...)`` is the range dropdown on the agent
detail page, and ``list_all(limit, offset)`` is the paging on the evaluations
list. Both were only ever called with their defaults: the dropdown test asserts
``days`` reached a MagicMock, and nothing seeded more runs than the limit, so
neither argument was run against the database.
"""

import datetime

from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.execution import RunStatus
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.run_repository import RunRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.snapshot_service import SnapshotService
from sqlalchemy.orm import Session


def _agent_and_snapshot(db_session: Session):
  """One agent and one frozen suite, which is all a run needs to exist."""
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  agent = agent_repo.create(
      name="Bot",
      config=AgentConfig(project_id="p", location="l", agent_resource_id="r"),
  )
  suite = suite_repo.create(name="Suite")
  return agent, snapshot_service.create_snapshot(suite.id)


def _aged_run(
    db_session: Session,
    repo: RunRepository,
    snapshot_id: int,
    agent_id: int,
    days_old: int,
    status: RunStatus,
):
  """A run backdated by days_old, because created_at is what is filtered on."""
  run = repo.create(snapshot_id, agent_id)
  run.created_at = datetime.datetime.now(
      datetime.timezone.utc
  ) - datetime.timedelta(days=days_old)
  run.status = status
  db_session.commit()
  return run


def test_the_dashboard_window_is_the_days_the_caller_asked_for(
    db_session: Session,
):
  """Seven days and thirty days have to see different runs.

  One run three days back and one twenty days back. The seven day window holds
  only the first, so it reads as one completed run out of one. The thirty day
  window holds both, and the older one failed.
  """
  agent, snapshot = _agent_and_snapshot(db_session)
  repo = RunRepository(db_session)

  _aged_run(db_session, repo, snapshot.id, agent.id, 3, RunStatus.COMPLETED)
  _aged_run(db_session, repo, snapshot.id, agent.id, 20, RunStatus.FAILED)

  assert (
      repo.get_agent_dashboard_stats(agent.id, days=7)["execution_rate"] == 1.0
  )
  assert (
      repo.get_agent_dashboard_stats(agent.id, days=30)["execution_rate"] == 0.5
  )


def test_list_all_pages_with_limit_and_offset(db_session: Session):
  """Three runs, two at a time, newest first and no row on both pages."""
  agent, snapshot = _agent_and_snapshot(db_session)
  repo = RunRepository(db_session)

  # Distinct ages, or the newest-first order has nothing to sort on.
  newest = _aged_run(
      db_session, repo, snapshot.id, agent.id, 1, RunStatus.COMPLETED
  )
  middle = _aged_run(
      db_session, repo, snapshot.id, agent.id, 2, RunStatus.COMPLETED
  )
  oldest = _aged_run(
      db_session, repo, snapshot.id, agent.id, 3, RunStatus.COMPLETED
  )

  first_page = repo.list_all(limit=2)
  second_page = repo.list_all(limit=2, offset=2)

  assert [r.id for r in first_page] == [newest.id, middle.id]
  assert [r.id for r in second_page] == [oldest.id]
  assert not repo.list_all(limit=2, offset=3)
