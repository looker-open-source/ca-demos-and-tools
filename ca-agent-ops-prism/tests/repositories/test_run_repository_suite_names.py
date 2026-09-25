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

"""Each suite appears once, under the name it has now.

get_unique_suites_from_snapshots grouped snapshots by original_suite_id and
took max(name), which is the lexicographically greatest name the suite has ever
carried, not the current one. Renaming "Sales QA" to "Adhoc Checks" left the
dropdown on the runs page showing "Sales QA" for good, because S sorts after A
and every past snapshot still holds the old name.

The agent dashboard chart had the other half of the same bug. It keyed its
series on the snapshot's name, so a rename split one suite's history into two
lines. It groups on original_suite_id now and resolves the name at the end.
"""

import datetime

from prism.common.schemas.assertion import AssertionType
from prism.server.models.agent import Agent
from prism.server.models.assertion import AssertionResult
from prism.server.models.assertion import AssertionSnapshot
from prism.server.models.run import Run
from prism.server.models.run import RunStatus
from prism.server.models.run import Trial
from prism.server.models.snapshot import ExampleSnapshot
from prism.server.models.snapshot import TestSuiteSnapshot
from prism.server.repositories.run_repository import RunRepository
from sqlalchemy.orm import Session

_EARLIER = datetime.datetime(2026, 2, 1, 9, 0, tzinfo=datetime.timezone.utc)
_LATER = datetime.datetime(2026, 2, 8, 9, 0, tzinfo=datetime.timezone.utc)

# The chart only looks back 30 days, so its runs have to be recent.
_NOW = datetime.datetime.now(datetime.timezone.utc)
_RUN_DAY = _NOW - datetime.timedelta(days=1)


def _snapshot(
    session: Session, suite_id: int, name: str, created_at: datetime.datetime
) -> TestSuiteSnapshot:
  snapshot = TestSuiteSnapshot(
      original_suite_id=suite_id,
      name=name,
      tags={},
      created_at=created_at,
  )
  session.add(snapshot)
  session.commit()
  return snapshot


def test_the_suite_name_comes_from_the_newest_snapshot_not_the_greatest(
    db_session: Session,
):
  """Sales QA renamed to Adhoc Checks, which sorts before it."""
  _snapshot(db_session, 3, "Sales QA", _EARLIER)
  _snapshot(db_session, 3, "Adhoc Checks", _LATER)

  suites = RunRepository(db_session).get_unique_suites_from_snapshots()

  assert suites == [{"original_suite_id": 3, "name": "Adhoc Checks"}]


def test_a_rename_that_sorts_later_is_picked_up_too(db_session: Session):
  """Guards against a fix that only reversed the comparison."""
  _snapshot(db_session, 4, "Adhoc Checks", _EARLIER)
  _snapshot(db_session, 4, "Sales QA", _LATER)

  suites = RunRepository(db_session).get_unique_suites_from_snapshots()

  assert suites == [{"original_suite_id": 4, "name": "Sales QA"}]


def test_each_suite_appears_once_and_snapshots_with_no_suite_are_left_out(
    db_session: Session,
):
  """The dropdown is a set of suites. A deleted suite has no entry to show."""
  _snapshot(db_session, 5, "First", _EARLIER)
  _snapshot(db_session, 5, "First Renamed", _LATER)
  _snapshot(db_session, 6, "Second", _LATER)
  orphan = TestSuiteSnapshot(
      original_suite_id=None, name="Orphan", tags={}, created_at=_LATER
  )
  db_session.add(orphan)
  db_session.commit()

  suites = RunRepository(db_session).get_unique_suites_from_snapshots()

  assert sorted(s["original_suite_id"] for s in suites) == [5, 6]
  by_id = {s["original_suite_id"]: s["name"] for s in suites}
  assert by_id[5] == "First Renamed"


def _scored_run(
    session: Session, agent: Agent, snapshot: TestSuiteSnapshot, score: float
) -> Run:
  """One run of the snapshot, with a single trial scoring ``score``."""
  run = Run(
      agent_id=agent.id,
      test_suite_snapshot_id=snapshot.id,
      status=RunStatus.COMPLETED,
      created_at=_RUN_DAY,
      started_at=_RUN_DAY,
      completed_at=_RUN_DAY,
      is_archived=False,
  )
  session.add(run)
  session.flush()

  example = ExampleSnapshot(
      snapshot_suite_id=snapshot.id, logical_id="L1", question="Q"
  )
  session.add(example)
  session.flush()

  trial = Trial(
      run_id=run.id,
      example_snapshot_id=example.id,
      status=RunStatus.COMPLETED,
      created_at=_RUN_DAY,
      started_at=_RUN_DAY,
      completed_at=_RUN_DAY,
  )
  trial.assertion_results.append(
      AssertionResult(
          score=score,
          passed=score >= 0.5,
          assertion_snapshot=AssertionSnapshot(
              type=AssertionType.TEXT_CONTAINS,
              weight=1.0,
              params={"value": "x"},
              example_snapshot_id=example.id,
          ),
      )
  )
  session.add(trial)
  session.commit()
  return run


def test_renaming_a_suite_does_not_split_the_agent_chart_in_two(
    db_session: Session,
):
  """Both runs are the same suite, so they belong to one series.

  Keyed on the snapshot name, the run taken before the rename and the run
  taken after drew as two lines, each with a hole where the other had its
  points. The series is the suite, and only its label changed.
  """
  agent = Agent(
      name="Chart Agent", project_id="p", location="l", agent_resource_id="r"
  )
  db_session.add(agent)
  db_session.flush()

  before = _snapshot(
      db_session, 7, "Sales QA", _RUN_DAY - datetime.timedelta(hours=2)
  )
  after = _snapshot(
      db_session, 7, "Adhoc Checks", _RUN_DAY - datetime.timedelta(hours=1)
  )
  _scored_run(db_session, agent, before, 1.0)
  _scored_run(db_session, agent, after, 0.0)

  stats = RunRepository(db_session).get_agent_dashboard_stats(agent.id)

  # The newest snapshot's name, the way the run filter picks it.
  assert stats["suites"] == ["Adhoc Checks"]
  assert len(stats["daily_accuracy"]) == 1
  point = stats["daily_accuracy"][0]
  assert set(point) == {"date", "Adhoc Checks"}
  # Both runs averaged together, not one line per name.
  assert point["Adhoc Checks"] == 0.5


def test_two_suites_stay_two_series_on_the_agent_chart(db_session: Session):
  """Guards against a fix that collapsed everything into one line."""
  agent = Agent(
      name="Chart Agent", project_id="p", location="l", agent_resource_id="r"
  )
  db_session.add(agent)
  db_session.flush()

  sales = _snapshot(db_session, 8, "Sales QA", _RUN_DAY)
  ops = _snapshot(db_session, 9, "Ops QA", _RUN_DAY)
  _scored_run(db_session, agent, sales, 1.0)
  _scored_run(db_session, agent, ops, 0.0)

  stats = RunRepository(db_session).get_agent_dashboard_stats(agent.id)

  assert stats["suites"] == ["Ops QA", "Sales QA"]
  point = stats["daily_accuracy"][0]
  assert point["Sales QA"] == 1.0
  assert point["Ops QA"] == 0.0


def test_two_suites_with_one_name_keep_their_own_points(db_session: Session):
  """Nothing stops two suites being called the same thing.

  The chart is a row per day and a column per name, so the second suite wrote
  its average over the first one's and a day that held two suites' runs drew
  one line carrying only the later suite's scores.
  """
  agent = Agent(
      name="Chart Agent", project_id="p", location="l", agent_resource_id="r"
  )
  db_session.add(agent)
  db_session.flush()

  first = _snapshot(db_session, 10, "Sales QA", _RUN_DAY)
  second = _snapshot(db_session, 11, "Sales QA", _RUN_DAY)
  _scored_run(db_session, agent, first, 1.0)
  _scored_run(db_session, agent, second, 0.0)

  stats = RunRepository(db_session).get_agent_dashboard_stats(agent.id)

  assert stats["suites"] == ["Sales QA", "Sales QA (#11)"]
  point = stats["daily_accuracy"][0]
  assert point["Sales QA"] == 1.0
  assert point["Sales QA (#11)"] == 0.0
