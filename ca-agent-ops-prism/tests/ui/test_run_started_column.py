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

"""What the STARTED column on the run table is allowed to say.

The column used to show a relative age off ``created_at``: "2 hr ago",
"Yesterday". Two things were wrong with that. It was the time the run was
queued, not the time it began, and the two differ by however long the queue
was. And a relative age cannot be lined up against anything else, which is the
reason to look at it. It is a timestamp now, and a queued run has no start time
to show.
"""

from __future__ import annotations

import datetime
import os
import time
from typing import Any, Iterator

from dash import html
import dash_mantine_components as dmc
from prism.common.schemas.execution import RunSchema
from prism.common.schemas.execution import RunStatus
from prism.ui.components import dashboard_components
from prism.ui.components import tables
from prism.ui.utils import format_timestamp
import pytest

_UTC = datetime.timezone.utc


@pytest.fixture(name="local_timezone")
def _local_timezone() -> Iterator[None]:
  """Pins the process timezone for the duration of a test.

  Under TZ=UTC, which is what a build machine and Cloud Run both run, a
  formatter that reads the process zone and one that pins UTC produce the same
  string, so the test that tells them apart cannot fail.
  """
  previous = os.environ.get("TZ")
  os.environ["TZ"] = "America/Los_Angeles"
  time.tzset()
  try:
    yield
  finally:
    if previous is None:
      del os.environ["TZ"]
    else:
      os.environ["TZ"] = previous
    time.tzset()


def _walk(component: Any) -> Iterator[Any]:
  """Yields every component in a rendered tree, depth first."""
  yield component
  children = getattr(component, "children", None)
  if children is None:
    return
  if not isinstance(children, (list, tuple)):
    children = [children]
  for child in children:
    if child is not None and not isinstance(child, (str, int, float)):
      yield from _walk(child)


def _run(status: RunStatus, started_at: datetime.datetime | None) -> RunSchema:
  """One run, with a fixed queue time and whatever start time it was given."""
  return RunSchema(
      id=1,
      test_suite_snapshot_id=1,
      agent_id=1,
      status=status,
      created_at=datetime.datetime(2026, 9, 16, 13, 32, tzinfo=_UTC),
      started_at=started_at,
  )


def _headers(table: Any) -> list[str]:
  """The column labels, in the order the table renders them."""
  head = next(c for c in _walk(table) if isinstance(c, html.Thead))
  return [th.children for th in head.children.children]


def _started_cell(run: RunSchema) -> str:
  """The text under the STARTED header, for the one row in the table.

  Found by header position rather than by index, so reordering the columns
  moves the test with them instead of silently reading the duration.
  """
  table = tables.render_run_table([run])
  column = _headers(table).index("STARTED")
  body = next(c for c in _walk(table) if isinstance(c, html.Tbody))
  cell = body.children[0].children[column]
  assert isinstance(cell.children, dmc.Text), cell.children
  return cell.children.children


def test_a_started_run_shows_the_date_and_the_time():
  """A day alone does not separate two runs of the same suite."""
  started = datetime.datetime(2026, 9, 16, 14, 32, tzinfo=_UTC)

  cell = _started_cell(_run(RunStatus.COMPLETED, started))

  assert cell == "2026-09-16 14:32 UTC"


def test_the_timestamp_is_labelled_utc_whatever_zone_the_server_is_in(
    local_timezone,
):
  """Stored UTC, rendered UTC, and said out loud.

  The column used to call ``astimezone()`` with no argument, which resolves to
  the server's zone. On Cloud Run that is UTC, so the local time it promised
  never reached production and every reading was silently hours out. The zone
  is in the string now, so the same run reads the same way from the dev server
  and from Cloud Run.
  """
  del local_timezone  # Set on the process by the fixture.
  started = datetime.datetime(2026, 9, 16, 21, 32, tzinfo=_UTC)

  cell = _started_cell(_run(RunStatus.COMPLETED, started))

  assert cell == "2026-09-16 21:32 UTC"


def test_a_queued_run_has_no_start_time():
  """``started_at`` is null until a worker picks the run up.

  Falling back to ``created_at`` would put a start time on a run that has not
  started, which is the bug being fixed.
  """
  assert _started_cell(_run(RunStatus.PENDING, None)) == "--"


@pytest.mark.parametrize(
    "status",
    [
        RunStatus.RUNNING,
        RunStatus.EXECUTING,
        RunStatus.EVALUATING,
        RunStatus.COMPLETED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
        RunStatus.PAUSED,
    ],
)
def test_every_status_past_pending_shows_its_start_time(status):
  """The status decides the badge, not what the STARTED column reads."""
  started = datetime.datetime(2026, 9, 16, 14, 32, tzinfo=_UTC)

  assert _started_cell(_run(status, started)) != "--"


def test_the_table_still_has_all_of_its_columns():
  """Nothing else about the table moved."""
  table = tables.render_run_table([_run(RunStatus.COMPLETED, None)])

  assert _headers(table) == [
      "RUN ID",
      "AGENT",
      "TEST SUITE",
      "STATUS",
      "ACCURACY",
      "DURATION",
      "STARTED",
      "ACTION",
  ]


def test_nothing_renders_a_relative_age_any_more():
  """The old helper is gone, so no run may read as an age."""
  now = datetime.datetime.now(_UTC)
  runs = [
      _run(RunStatus.COMPLETED, now),
      _run(RunStatus.COMPLETED, now - datetime.timedelta(hours=2)),
      _run(RunStatus.COMPLETED, now - datetime.timedelta(days=1)),
  ]

  rendered = str(tables.render_run_table(runs))

  for phrase in ("Just now", "mins ago", "hr ago", "Yesterday"):
    assert phrase not in rendered, f"{phrase} is still being rendered"


def _dashboard_started_cell(run: dict[str, Any]) -> str:
  """The STARTED cell of the agent detail copy of the same table."""
  table = dashboard_components.render_recent_evals_table([run])
  column = _headers(table).index("STARTED")
  body = next(c for c in _walk(table) if isinstance(c, html.Tbody))
  return body.children[0].children[column].children.children


def test_the_dashboard_table_shows_the_same_timestamp():
  """Agent detail renders its own copy of the run table.

  It had the same relative age off the same wrong field, so a run read one way
  on the evaluations page and another on the agent it belongs to.
  """
  started = datetime.datetime(2026, 9, 16, 14, 32, tzinfo=_UTC)
  run = {"id": 1, "score": None, "status": "COMPLETED", "started_at": started}

  cell = _dashboard_started_cell(run)

  assert cell == "2026-09-16 14:32 UTC"


def test_the_dashboard_table_dashes_a_queued_run():
  """Same fallback as the evaluations table."""
  run = {"id": 1, "score": None, "status": "PENDING", "started_at": None}

  assert _dashboard_started_cell(run) == "--"


def test_the_schema_defaults_the_start_time_to_null():
  """Runs read back from before the field existed must still validate."""
  run = RunSchema(
      id=1,
      test_suite_snapshot_id=1,
      agent_id=1,
      status=RunStatus.COMPLETED,
      created_at=datetime.datetime(2026, 9, 16, 13, 32, tzinfo=_UTC),
  )

  assert run.started_at is None


@pytest.mark.parametrize("offset_hours", [1, -5, 9])
def test_the_shared_formatter_reads_the_same_instant_every_way(offset_hours):
  """Nine call sites across the pages format a timestamp through this.

  The same instant written in any timezone has to render identically, because
  the reading is the UTC clock and not whichever zone the value arrived in.
  An offset of zero used to be one of the rows here, which asserted a string
  against itself and so passed for any implementation, ``return ""`` included.
  """
  tz = datetime.timezone(datetime.timedelta(hours=offset_hours))
  instant = datetime.datetime(2026, 9, 16, 14, 32, tzinfo=_UTC)

  assert format_timestamp(instant.astimezone(tz)) == "2026-09-16 14:32 UTC"
