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

"""Callbacks for the Schedule Detail page."""

import re
from typing import Any

import dash
from prism.client import get_client
from prism.common.schemas.schedule import ScheduleSchema
from prism.ui.components import schedule_components
from prism.ui.constants import CP
from prism.ui.ids import ScheduleDetailIds as Ids
from prism.ui.ids import ScheduleIds
from prism.ui.utils import typed_callback

_DETAIL_PATH = re.compile(r"^/schedules/view/(?P<schedule_id>[^/]+)/?$")
_RECENT_RUN_LIMIT = 10
_UPCOMING_RUN_COUNT = 5
_HEADER_OUTPUT_COUNT = 3
_BODY_OUTPUT_COUNT = 5


def _schedule_id_from_path(pathname: str | None) -> str | None:
  """Returns the raw id from `/schedules/view/<schedule_id>`, or None."""
  match = _DETAIL_PATH.match(pathname or "")
  return match.group("schedule_id") if match else None


def _load_schedule(raw_id: str) -> ScheduleSchema | None:
  """Returns the schedule for `raw_id`, or None if it isn't a known id."""
  if not raw_id.isdigit():
    return None
  return get_client().schedules.get_schedule(int(raw_id))


def _build_schedule_detail_header(pathname: str | None) -> tuple[Any, ...]:
  """Builds the title, breadcrumbs, and header actions."""
  raw_id = _schedule_id_from_path(pathname)
  if raw_id is None:
    return (dash.no_update,) * _HEADER_OUTPUT_COUNT
  schedule = _load_schedule(raw_id)
  if schedule is None:
    return (
        "Schedule not found",
        schedule_components.render_schedule_detail_breadcrumbs("Not found"),
        [],
    )
  return (
      schedule.name,
      schedule_components.render_schedule_detail_breadcrumbs(schedule.name),
      schedule_components.render_schedule_detail_actions(schedule),
  )


def _build_schedule_detail_body(pathname: str | None) -> tuple[Any, ...]:
  """Builds the status, stats, configuration, upcoming runs, and history."""
  raw_id = _schedule_id_from_path(pathname)
  if raw_id is None:
    return (dash.no_update,) * _BODY_OUTPUT_COUNT
  schedule = _load_schedule(raw_id)
  if schedule is None:
    return (
        None,
        [],
        schedule_components.render_schedule_not_found(raw_id),
        None,
        None,
    )

  client = get_client()
  upcoming = []
  if schedule.is_enabled and not schedule.is_archived:
    upcoming = client.schedules.preview_next_runs(
        schedule.cron_expression,
        timezone=schedule.timezone,
        count=_UPCOMING_RUN_COUNT,
    )
  runs = list(
      client.runs.list_runs(
          schedule_id=schedule.id,
          include_archived=True,
          limit=_RECENT_RUN_LIMIT,
      )
  )
  return (
      schedule_components.render_schedule_detail_status(schedule),
      schedule_components.render_schedule_detail_stats(schedule),
      schedule_components.render_schedule_config_card(schedule),
      schedule_components.render_upcoming_runs_card(schedule, upcoming),
      schedule_components.render_schedule_runs_card(schedule, runs),
  )


@typed_callback(
    output=[
        (Ids.TITLE, CP.CHILDREN),
        (Ids.BREADCRUMBS, CP.CHILDREN),
        (Ids.ACTIONS, CP.CHILDREN),
    ],
    inputs=[
        ("url", CP.PATHNAME),
        (ScheduleIds.UPDATE_SIGNAL, CP.DATA),
        (Ids.HEADER_REPAINT, CP.DATA),
    ],
)
def render_schedule_detail_header(
    pathname: str | None, unused_signal: Any, unused_repaint: Any
):
  """Renders the title, breadcrumbs, and header actions.

  These redraw on load and after a user action, never on the poll. Redrawing
  them on every tick replaced the Run Now button while its click was in flight.
  Sharing one callback with the poll was no better: Dash keeps only the newest
  response per callback, so a tick that landed during an action's redraw
  dropped it and left the Pause/Resume button showing the old label.

  Args:
    pathname: The page path, which carries the schedule id.
    unused_signal: The update signal written after a schedule action.
    unused_repaint: Bumped by the poll while the header is still unrendered.

  Returns:
    New children for the title, breadcrumbs, and actions, or no_update.
  """
  del unused_signal, unused_repaint
  return _build_schedule_detail_header(pathname)


# If the header's load request dies, nothing else redraws it, so the page sits
# with no title or buttons. The poll asks for a repaint only while the actions
# container still holds the skeleton's None. A rendered header always has
# children (a not-found schedule gets []), so there is no button to replace
# mid-click.
dash.clientside_callback(
    """
    function(nIntervals, actions) {
        if (actions === null || actions === undefined) {
            return nIntervals;
        }
        return window.dash_clientside.no_update;
    }
    """,
    dash.Output(Ids.HEADER_REPAINT, CP.DATA),
    dash.Input(Ids.POLL_INTERVAL, "n_intervals"),
    dash.State(Ids.ACTIONS, CP.CHILDREN),
    prevent_initial_call=True,
)


@typed_callback(
    output=[
        (Ids.STATUS_CONTAINER, CP.CHILDREN),
        (Ids.STATS, CP.CHILDREN),
        (Ids.CONFIG_CONTAINER, CP.CHILDREN),
        (Ids.UPCOMING_CONTAINER, CP.CHILDREN),
        (Ids.RUNS_CONTAINER, CP.CHILDREN),
    ],
    inputs=[
        ("url", CP.PATHNAME),
        (Ids.POLL_INTERVAL, "n_intervals"),
        (ScheduleIds.UPDATE_SIGNAL, CP.DATA),
    ],
)
def render_schedule_detail(
    pathname: str | None,
    unused_intervals: int | None,
    unused_signal: Any,
):
  """Renders the Schedule Detail body on load, poll, and after any action.

  Args:
    pathname: The page path, which carries the schedule id.
    unused_intervals: The poll tick count.
    unused_signal: The update signal written after a schedule action.

  Returns:
    New children for every body container, or no_update for each.
  """
  del unused_intervals, unused_signal
  return _build_schedule_detail_body(pathname)
