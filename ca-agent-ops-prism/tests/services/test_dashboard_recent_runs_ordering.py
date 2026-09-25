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

"""Test for the ordering of the dashboard's Recent Runs panel.

Run.started_at is NULL until a worker promotes the run, and Postgres sorts
NULLs first on DESC. The panel used a plain desc(), so queueing a handful of
runs filled all five rows with runs that had never executed and pushed the
finished ones off the home page. The query orders by nullslast() now.
"""

import datetime

from prism.common.schemas.execution import RunStatus
from prism.server.models.agent import Agent
from prism.server.models.run import Run
from prism.server.models.snapshot import TestSuiteSnapshot
from prism.server.services.dashboard_service import DashboardService
from sqlalchemy import orm


def _add_run(
    session: orm.Session,
    agent: Agent,
    suite_snap: TestSuiteSnapshot,
    status: RunStatus,
    started_at: datetime.datetime | None,
) -> Run:
  run = Run(
      agent_id=agent.id,
      test_suite_snapshot_id=suite_snap.id,
      status=status,
      started_at=started_at,
      is_archived=False,
  )
  session.add(run)
  session.commit()
  return run


def test_recent_runs_puts_started_runs_newest_first_and_pending_ones_last(
    db_session: orm.Session,
):
  agent = Agent(
      name="Test Agent",
      project_id="p",
      location="l",
      agent_resource_id="r",
  )
  db_session.add(agent)
  db_session.commit()

  suite_snap = TestSuiteSnapshot(name="S1", original_suite_id=1)
  db_session.add(suite_snap)
  db_session.flush()

  now = datetime.datetime.now(datetime.timezone.utc)
  # Queued first, so a query that sorts NULLs first hands them back first.
  pending_one = _add_run(db_session, agent, suite_snap, RunStatus.PENDING, None)
  pending_two = _add_run(db_session, agent, suite_snap, RunStatus.PENDING, None)
  oldest = _add_run(
      db_session,
      agent,
      suite_snap,
      RunStatus.COMPLETED,
      now - datetime.timedelta(hours=3),
  )
  middle = _add_run(
      db_session,
      agent,
      suite_snap,
      RunStatus.COMPLETED,
      now - datetime.timedelta(hours=2),
  )
  newest = _add_run(
      db_session,
      agent,
      suite_snap,
      RunStatus.COMPLETED,
      now - datetime.timedelta(hours=1),
  )

  stats = DashboardService(db_session).get_dashboard_stats()
  run_ids = [r.id for r in stats.recent_runs]

  assert run_ids[:3] == [newest.id, middle.id, oldest.id]
  # Two NULLs have no order between them, only a position after the rest.
  assert set(run_ids[3:]) == {pending_one.id, pending_two.id}
