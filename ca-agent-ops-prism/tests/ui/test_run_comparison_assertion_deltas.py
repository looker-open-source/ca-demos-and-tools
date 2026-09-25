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

"""The assertion delta panel on /compare, paired one assertion at a time.

The panel above the trial list averages a score delta per assertion type. The
pairing behind it used to key on the type alone, so a test case carrying two
assertions of one type kept only the last of them and the other delta never
reached the average. What that looks like to someone reading the page is a
percentage that does not match what the runs did, on any suite where two of
the checks happen to be the same kind.

The runs here snapshot the live suite separately, which is what starting a run
does. Their assertion snapshot ids differ, so ``original_assertion_id`` is the
only thing left that says which live check a result came from.
"""

from __future__ import annotations

import datetime
from typing import Any, Iterator

from prism.common.schemas.assertion import DataCheckRowCount
from prism.common.schemas.assertion import TextContains
from prism.common.schemas.execution import RunStatus
from prism.server.models.agent import Agent
from prism.server.models.assertion import Assertion
from prism.server.models.assertion import AssertionResult
from prism.server.models.example import Example
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.server.models.snapshot import TestSuiteSnapshot
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.snapshot_service import SnapshotService
from prism.ui.ids import ComparisonIds
from sqlalchemy import orm
from tests.ui import dash_http

_T0 = datetime.datetime(2026, 3, 1, 12, 0, tzinfo=datetime.timezone.utc)


def _seed_agent(session: orm.Session) -> Agent:
  """An agent for the runs to belong to."""
  agent = Agent(
      name="Compare Agent", project_id="p", location="l", agent_resource_id="r"
  )
  session.add(agent)
  session.flush()
  return agent


def _seed_example(session: orm.Session, suite_name: str) -> Example:
  """A live suite with one question in it."""
  suite = SuiteRepository(session).create(name=suite_name)
  return ExampleRepository(session).create(
      suite.id, "How many orders are there?"
  )


def _add_assertion(
    session: orm.Session, example: Example, assertion: Any
) -> Assertion:
  """Adds one live assertion to the question.

  Through the repository rather than as a row, because the editor's own path
  is what fills ``params``. ``sync_suite`` parses the store into the persisted
  schema and dumps every field but id, type and weight, so the column ends up
  carrying ``original_assertion_id`` as well.
  """
  return ExampleRepository(session).add_assertion(example.id, assertion)


def _snapshot(session: orm.Session, suite_id: int) -> TestSuiteSnapshot:
  """Freezes the live suite, the way starting a run does."""
  service = SnapshotService(
      session, SuiteRepository(session), ExampleRepository(session)
  )
  return service.create_snapshot(suite_id)


def _seed_run(
    session: orm.Session,
    agent: Agent,
    snapshot: TestSuiteSnapshot,
    scores: dict[int, float],
    *,
    created_at: datetime.datetime = _T0,
) -> Run:
  """One completed run of the snapshot, scoring every assertion in it.

  ``scores`` is keyed by live assertion id, not by snapshot id, because the
  live id is the only name the two runs' snapshots have in common.
  """
  run = Run(
      agent_id=agent.id,
      test_suite_snapshot_id=snapshot.id,
      status=RunStatus.COMPLETED,
      created_at=created_at,
  )
  session.add(run)
  session.flush()

  for example in snapshot.examples:
    trial = Trial(
        run_id=run.id,
        example_snapshot_id=example.id,
        status=RunStatus.COMPLETED,
        output_text=f"Run {run.id} answered {example.logical_id}.",
        started_at=created_at,
        completed_at=created_at + datetime.timedelta(seconds=1),
    )
    session.add(trial)
    session.flush()

    for assertion in example.asserts:
      score = scores[assertion.original_assertion_id]
      session.add(
          AssertionResult(
              trial_id=trial.id,
              assertion_snapshot_id=assertion.id,
              passed=score >= 0.5,
              score=score,
          )
      )

  session.commit()
  return run


def _walk(fragment: Any) -> Iterator[dict[str, Any]]:
  """Every serialized component in a response fragment, in document order."""
  if isinstance(fragment, list):
    for item in fragment:
      yield from _walk(item)
  elif isinstance(fragment, dict):
    if "type" in fragment and "props" in fragment:
      yield fragment
      yield from _walk(fragment["props"])
    else:
      for value in fragment.values():
        yield from _walk(value)


def _compare_page(client, base: Run, challenger: Run) -> dict[str, Any]:
  """Loads /compare for two runs and returns the response by component id."""
  deps = dash_http.dependencies(client)
  dep = dash_http.find(deps, f"{ComparisonIds.METRICS_CARDS}.children")
  search = (
      f"?{ComparisonIds.URL_BASE_RUN_ID}={base.id}"
      f"&{ComparisonIds.URL_CHALLENGER_RUN_ID}={challenger.id}"
  )
  response = dash_http.fire_url(client, dep, "/compare", search)
  assert response.status_code == 200, response.data[:2000]
  return dash_http.body(response)["response"]


def _panel(body: dict[str, Any]) -> dict[str, str]:
  """The delta panel, mapping each assertion type's label to its percentage.

  One Stack per type, carrying the label and the averaged delta as its only
  two bare-string Texts.
  """
  entries = {}
  for stack in _walk(body[ComparisonIds.ASSERTION_DELTA_CHART]["children"]):
    if stack["type"] != "Stack":
      continue
    label, value = [
        component["props"]["children"]
        for component in _walk(stack)
        if component["type"] == "Text"
    ]
    entries[label] = value
  return entries


def test_two_assertions_of_one_type_are_averaged_into_one_row(
    dash_client, callback_errors, db_session
):
  """Both same-type assertions get a delta, and both land in the type's row.

  The question carries two text checks and one row-count check. The text
  checks moved by +1.0 and 0.0, so the row reads their mean, +50%. Keying the
  pairing by type alone reported +30% (the moved check differenced against the
  other one's baseline) or +0% (the moved check dropped for the one that came
  after it). Bucketing is still by type, so the two text checks share a row
  and the row count keeps its own.
  """
  agent = _seed_agent(db_session)
  example = _seed_example(db_session, "Two Checks Suite")
  orders = _add_assertion(
      db_session, example, TextContains(type="text-contains", value="orders")
  )
  totals = _add_assertion(
      db_session, example, TextContains(type="text-contains", value="totals")
  )
  rows = _add_assertion(
      db_session,
      example,
      DataCheckRowCount(type="data-check-row-count", value=3),
  )

  suite_id = example.test_suite_id
  base = _seed_run(
      db_session,
      agent,
      _snapshot(db_session, suite_id),
      {orders.id: 0.0, totals.id: 0.4, rows.id: 1.0},
  )
  challenger = _seed_run(
      db_session,
      agent,
      _snapshot(db_session, suite_id),
      {orders.id: 1.0, totals.id: 0.4, rows.id: 1.0},
      created_at=_T0 + datetime.timedelta(hours=1),
  )

  body = _compare_page(dash_client, base, challenger)

  callback_errors.assert_none()
  assert _panel(body) == {
      "Text Contains": "+50.0%",
      "Data Check Row Count": "+0.0%",
  }


def test_an_assertion_the_baseline_never_ran_stays_out_of_the_average(
    dash_client, callback_errors, db_session
):
  """A check added after the baseline ran has nothing to be a delta from.

  The suite is edited between the two runs, so the candidate's snapshot has a
  text check the baseline's does not. Both checks are the same type, so only
  the assertion's own identity keeps the new one out. Pairing it against the
  other text check's baseline reports +0% here, on a pair of runs where the
  one check they share improved by half.
  """
  agent = _seed_agent(db_session)
  example = _seed_example(db_session, "Edited Suite")
  orders = _add_assertion(
      db_session, example, TextContains(type="text-contains", value="orders")
  )

  suite_id = example.test_suite_id
  base = _seed_run(
      db_session, agent, _snapshot(db_session, suite_id), {orders.id: 0.5}
  )

  totals = _add_assertion(
      db_session, example, TextContains(type="text-contains", value="totals")
  )
  challenger = _seed_run(
      db_session,
      agent,
      _snapshot(db_session, suite_id),
      {orders.id: 1.0, totals.id: 0.0},
      created_at=_T0 + datetime.timedelta(hours=1),
  )

  body = _compare_page(dash_client, base, challenger)

  callback_errors.assert_none()
  assert _panel(body) == {"Text Contains": "+50.0%"}
