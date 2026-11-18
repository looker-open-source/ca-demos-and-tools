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

"""Callbacks for the Scheduled Evaluations page and modal."""

import logging
import time
from typing import Any
import urllib.parse

import dash
from prism.client import get_client
from prism.common import cron
from prism.common.schemas.schedule import ScheduleCadence
from prism.common.schemas.schedule import ScheduleCreate
from prism.common.schemas.schedule import ScheduleUpdate
from prism.ui.components import schedule_components
from prism.ui.constants import CP
from prism.ui.constants import NOTIFICATION_CONTAINER
from prism.ui.constants import REDIRECT_HANDLER
from prism.ui.ids import ScheduleIds as Ids
from prism.ui.utils import typed_callback
import pydantic

logger = logging.getLogger(__name__)


def _parse_int(raw: str | None) -> int | None:
  """Returns an integer when `raw` is a positive base-10 string, else None."""
  if raw and str(raw).isdigit():
    return int(raw)
  return None


def _extract_preset_fields(
    cadence: str, cron_expression: str
) -> tuple[str, int, int]:
  """Extracts (dow, hour, minute) defaults from a stored cron expression."""
  parts = (cron_expression or "").split()
  if len(parts) != 5:
    return "1", 9, 0
  minute = int(parts[0]) if parts[0].isdigit() else 0
  hour = int(parts[1]) if parts[1].isdigit() else 9
  dow = parts[4] if parts[4] in {"0", "1", "2", "3", "4", "5", "6"} else "1"
  if cadence == ScheduleCadence.HOURLY.value:
    return "1", 9, minute
  if cadence == ScheduleCadence.DAILY.value:
    return "1", hour, minute
  if cadence == ScheduleCadence.WEEKLY.value:
    return dow, hour, minute
  return dow, hour, minute


def _format_validation_error(exc: Exception) -> str:
  """Formats user-actionable validation failures without leaking raw payloads."""
  if isinstance(exc, pydantic.ValidationError):
    messages = []
    for err in exc.errors():
      loc = ".".join(str(part) for part in err.get("loc", ()))
      msg = err.get("msg", "Invalid value")
      if msg.startswith("Value error, "):
        msg = msg[len("Value error, ") :]
      messages.append(f"{loc}: {msg}" if loc else msg)
    if messages:
      return "; ".join(messages)
    return "Invalid schedule configuration."
  if isinstance(exc, ValueError):
    return str(exc)
  return "Could not save schedule. Check the server log for details."


def _load_agent_and_suite_options(
    include_agent_id: int | None = None,
    include_suite_id: int | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
  """Returns Select option lists for active agents and test suites."""
  client = get_client()
  agents = list(client.agents.list_agents(include_archived=False))
  if include_agent_id and all(a.id != include_agent_id for a in agents):
    extra_agent = client.agents.get_agent(include_agent_id)
    if extra_agent:
      agents.append(extra_agent)

  suites = list(client.suites.list_suites(include_archived=False))
  if include_suite_id and all(s.id != include_suite_id for s in suites):
    extra_suite = client.suites.get_suite(include_suite_id)
    if extra_suite:
      suites.append(extra_suite)

  agent_opts = [{"label": a.name, "value": str(a.id)} for a in agents]
  suite_opts = [{"label": s.name, "value": str(s.id)} for s in suites]
  return agent_opts, suite_opts


def _build_schedules_view(pathname: str, search: str):
  """Builds the summary strip and schedule table for `/schedules`."""
  if pathname != "/schedules":
    return dash.no_update, dash.no_update

  parsed_qs = urllib.parse.parse_qs((search or "").lstrip("?"))
  agent_id = _parse_int(parsed_qs.get("agent_id", [None])[0])
  suite_id = _parse_int(parsed_qs.get("suite_id", [None])[0])
  status_val = parsed_qs.get("status", [None])[0]
  include_archived = parsed_qs.get("archived", ["false"])[0] == "true"

  is_enabled: bool | None = None
  if status_val == "active":
    is_enabled = True
  elif status_val == "paused":
    is_enabled = False

  client = get_client()
  filtered_schedules = client.schedules.list_schedules(
      agent_id=agent_id,
      test_suite_id=suite_id,
      is_enabled=is_enabled,
      include_archived=include_archived,
  )
  all_unarchived = client.schedules.list_schedules(include_archived=False)
  recent_runs = client.runs.list_runs(include_archived=True, limit=500)
  scheduled_run_count = sum(1 for r in recent_runs if r.schedule_id is not None)

  kpi_strip = schedule_components.render_schedule_summary_strip(
      all_unarchived, scheduled_run_count
  )
  table_or_empty = schedule_components.render_schedule_table(filtered_schedules)
  return kpi_strip, table_or_empty


@typed_callback(
    output=[
        (Ids.KPI_CONTAINER, CP.CHILDREN),
        (Ids.LIST_CONTAINER, CP.CHILDREN),
    ],
    inputs=[
        ("url", CP.PATHNAME),
        ("url", CP.SEARCH),
    ],
)
def render_schedules_on_load(pathname: str, search: str):
  """Renders the Schedules page on navigation and URL filter updates."""
  return _build_schedules_view(pathname, search)


@typed_callback(
    output=[
        dash.Output(Ids.KPI_CONTAINER, CP.CHILDREN, allow_duplicate=True),
        dash.Output(Ids.LIST_CONTAINER, CP.CHILDREN, allow_duplicate=True),
    ],
    inputs=[
        (Ids.POLL_INTERVAL, "n_intervals"),
        (Ids.UPDATE_SIGNAL, CP.DATA),
    ],
    state=[
        ("url", CP.PATHNAME),
        ("url", CP.SEARCH),
    ],
    prevent_initial_call=True,
)
def refresh_schedules_view(
    unused_intervals: int,
    unused_signal: Any,
    pathname: str,
    search: str,
):
  """Refreshes the Schedules view on interval ticks or mutation signals."""
  del unused_intervals, unused_signal
  return _build_schedules_view(pathname, search)


@typed_callback(
    output=[
        (Ids.FILTER_AGENT, CP.DATA),
        (Ids.FILTER_SUITE, CP.DATA),
    ],
    inputs=[("url", CP.PATHNAME)],
)
def populate_schedule_filter_options(pathname: str):
  """Populates Agent and Test Suite filter dropdowns when on `/schedules`."""
  if pathname != "/schedules":
    return dash.no_update, dash.no_update
  return _load_agent_and_suite_options()


@typed_callback(
    output=[
        (Ids.FILTER_AGENT, CP.VALUE),
        (Ids.FILTER_SUITE, CP.VALUE),
        (Ids.FILTER_STATUS, CP.VALUE),
        (Ids.SWITCH_ARCHIVED, CP.CHECKED),
    ],
    inputs=[("url", CP.SEARCH)],
)
def sync_schedule_filters_to_url(search: str):
  """Synchronizes UI filter controls with URL query parameters."""
  if not search:
    return None, None, None, False

  params = urllib.parse.parse_qs(search.lstrip("?"))
  agent_id = params.get("agent_id", [None])[0]
  suite_id = params.get("suite_id", [None])[0]
  status = params.get("status", [None])[0]
  include_archived = params.get("archived", ["false"])[0] == "true"
  return agent_id, suite_id, status, include_archived


@typed_callback(
    output=dash.Output("url", CP.SEARCH, allow_duplicate=True),
    inputs=[
        (Ids.FILTER_AGENT, CP.VALUE),
        (Ids.FILTER_SUITE, CP.VALUE),
        (Ids.FILTER_STATUS, CP.VALUE),
        (Ids.SWITCH_ARCHIVED, CP.CHECKED),
    ],
    state=[("url", CP.SEARCH)],
    prevent_initial_call=True,
)
def update_schedule_url_from_filters(
    agent_id: str | None,
    suite_id: str | None,
    status: str | None,
    include_archived: bool,
    current_search: str,
):
  """Writes filter changes to `url.search`."""
  params = (
      urllib.parse.parse_qs(current_search.lstrip("?"))
      if current_search
      else {}
  )

  if agent_id:
    params["agent_id"] = [agent_id]
  else:
    params.pop("agent_id", None)

  if suite_id:
    params["suite_id"] = [suite_id]
  else:
    params.pop("suite_id", None)

  if status:
    params["status"] = [status]
  else:
    params.pop("status", None)

  if include_archived:
    params["archived"] = ["true"]
  else:
    params.pop("archived", None)

  params.pop("create", None)
  params.pop("prefill_agent_id", None)
  params.pop("prefill_suite_id", None)

  updated = f"?{urllib.parse.urlencode(params, doseq=True)}" if params else ""
  if updated == (current_search or ""):
    return dash.no_update
  return updated


_MODAL_FIELD_OUTPUTS = [
    (Ids.MODAL, CP.OPENED),
    (Ids.MODAL_TITLE, CP.CHILDREN),
    (Ids.STORE_EDIT_ID, CP.DATA),
    (Ids.SELECT_AGENT, CP.DATA),
    (Ids.SELECT_SUITE, CP.DATA),
    (Ids.INPUT_NAME, CP.VALUE),
    (Ids.SELECT_AGENT, CP.VALUE),
    (Ids.SELECT_SUITE, CP.VALUE),
    (Ids.SEGMENT_CADENCE, CP.VALUE),
    (Ids.SELECT_DOW, CP.VALUE),
    (Ids.INPUT_HOUR, CP.VALUE),
    (Ids.INPUT_MINUTE, CP.VALUE),
    (Ids.INPUT_CRON, CP.VALUE),
    (Ids.SELECT_TIMEZONE, CP.VALUE),
    (Ids.INPUT_CONCURRENCY, CP.VALUE),
    (Ids.SWITCH_SUGGESTIONS, CP.CHECKED),
    (Ids.SWITCH_ENABLED, CP.CHECKED),
    (Ids.MODAL_ERROR, CP.HIDE),
]
_MODAL_FIELD_COUNT = len(_MODAL_FIELD_OUTPUTS)


def _new_schedule_modal_values(
    agent_opts: list[dict[str, str]],
    suite_opts: list[dict[str, str]],
    name: str = "",
    agent_id: str | None = None,
    suite_id: str | None = None,
) -> tuple[Any, ...]:
  """Returns modal field values for a new daily 09:00 UTC schedule."""
  return (
      True,
      "New Evaluation Schedule",
      None,
      agent_opts,
      suite_opts,
      name,
      agent_id,
      suite_id,
      ScheduleCadence.DAILY.value,
      "1",
      9,
      0,
      "0 9 * * *",
      "UTC",
      2,
      False,
      True,
      True,
  )


@typed_callback(
    output=_MODAL_FIELD_OUTPUTS,
    inputs=[
        ({"type": Ids.BTN_OPEN_CREATE, "index": dash.ALL}, CP.N_CLICKS),
        ({"type": Ids.BTN_EMPTY_CREATE, "index": dash.ALL}, CP.N_CLICKS),
        ("url", CP.PATHNAME),
        ("url", CP.SEARCH),
    ],
)
def open_create_schedule_modal(
    open_clicks: list[int | None],
    empty_clicks: list[int | None],
    pathname: str,
    search: str,
):
  """Opens the Schedule modal for creation or a `?create=1` deep link."""
  del open_clicks, empty_clicks
  if pathname != "/schedules":
    return (dash.no_update,) * _MODAL_FIELD_COUNT

  click_triggers = [
      t
      for t in dash.ctx.triggered
      if not t.get("prop_id", "").startswith("url.") and t.get("value")
  ]
  if click_triggers:
    agent_opts, suite_opts = _load_agent_and_suite_options()
    return _new_schedule_modal_values(agent_opts, suite_opts)

  params = urllib.parse.parse_qs((search or "").lstrip("?"))
  if params.get("create", [None])[0] != "1":
    return (dash.no_update,) * _MODAL_FIELD_COUNT

  prefill_agent = (
      params.get("prefill_agent_id", [None])[0]
      or params.get("agent_id", [None])[0]
  )
  prefill_suite = (
      params.get("prefill_suite_id", [None])[0]
      or params.get("suite_id", [None])[0]
  )
  agent_opts, suite_opts = _load_agent_and_suite_options(
      include_agent_id=_parse_int(prefill_agent),
      include_suite_id=_parse_int(prefill_suite),
  )

  suggested_name = ""
  if prefill_suite:
    matching_suites = [
        o["label"] for o in suite_opts if o["value"] == str(prefill_suite)
    ]
    if matching_suites:
      suggested_name = f"Daily {matching_suites[0]}"
  elif prefill_agent:
    matching_agents = [
        o["label"] for o in agent_opts if o["value"] == str(prefill_agent)
    ]
    if matching_agents:
      suggested_name = f"Daily {matching_agents[0]} Check"

  return _new_schedule_modal_values(
      agent_opts,
      suite_opts,
      name=suggested_name,
      agent_id=str(prefill_agent) if prefill_agent else None,
      suite_id=str(prefill_suite) if prefill_suite else None,
  )


@typed_callback(
    output=[
        dash.Output(component_id, prop, allow_duplicate=True)
        for component_id, prop in _MODAL_FIELD_OUTPUTS
    ],
    inputs=[({"type": Ids.BTN_EDIT, "index": dash.ALL}, CP.N_CLICKS)],
    prevent_initial_call=True,
)
def open_edit_schedule_modal(edit_clicks: list[int | None]):
  """Opens the Schedule modal prefilled from the Schedule Detail Edit button.

  Kept apart from the create callback, which only acts on /schedules, because
  the Edit button lives on the detail page.

  Args:
    edit_clicks: Click counts for the Edit buttons on the page.

  Returns:
    Values for every modal field, or no_update for each.
  """
  del edit_clicks
  triggered_id = dash.ctx.triggered_id
  if not isinstance(triggered_id, dict) or not any(
      t.get("value") for t in dash.ctx.triggered
  ):
    return (dash.no_update,) * _MODAL_FIELD_COUNT

  sched = get_client().schedules.get_schedule(int(triggered_id["index"]))
  if not sched:
    return (dash.no_update,) * _MODAL_FIELD_COUNT

  agent_opts, suite_opts = _load_agent_and_suite_options(
      include_agent_id=sched.agent_id,
      include_suite_id=sched.test_suite_id,
  )
  dow, hour, minute = _extract_preset_fields(
      sched.cadence.value, sched.cron_expression
  )
  return (
      True,
      f"Edit Schedule: {sched.name}",
      sched.id,
      agent_opts,
      suite_opts,
      sched.name,
      str(sched.agent_id),
      str(sched.test_suite_id),
      sched.cadence.value,
      dow,
      hour,
      minute,
      sched.cron_expression,
      sched.timezone,
      sched.concurrency,
      sched.generate_suggestions,
      sched.is_enabled,
      True,
  )


@typed_callback(
    output=[
        dash.Output(Ids.MODAL, CP.OPENED, allow_duplicate=True),
        dash.Output(Ids.MODAL_ERROR, CP.HIDE, allow_duplicate=True),
    ],
    inputs=[(Ids.BTN_CANCEL, CP.N_CLICKS)],
    prevent_initial_call=True,
)
def close_schedule_modal(cancel_clicks: int | None):
  """Closes the Schedule modal on Cancel from either schedules page."""
  if not cancel_clicks:
    return dash.no_update, dash.no_update
  return False, True


@typed_callback(
    output=[
        (Ids.PRESET_CONTROLS, CP.STYLE),
        (Ids.PRESET_DOW_WRAPPER, CP.STYLE),
        (Ids.PRESET_HOUR_WRAPPER, CP.STYLE),
        dash.Output(Ids.INPUT_CRON, CP.VALUE, allow_duplicate=True),
    ],
    inputs=[
        (Ids.SEGMENT_CADENCE, CP.VALUE),
        (Ids.SELECT_DOW, CP.VALUE),
        (Ids.INPUT_HOUR, CP.VALUE),
        (Ids.INPUT_MINUTE, CP.VALUE),
    ],
    prevent_initial_call=True,
)
def sync_cadence_and_preset_controls(
    cadence: str | None,
    dow: str | None,
    hour: int | float | None,
    minute: int | float | None,
):
  """Synchronizes preset time selectors with the 5-field cron expression."""
  if not cadence or cadence == ScheduleCadence.CUSTOM.value:
    return (
        {"display": "none"},
        {"display": "none"},
        {"display": "none"},
        dash.no_update,
    )

  minute_int = max(0, min(59, int(minute if minute is not None else 0)))
  hour_int = max(0, min(23, int(hour if hour is not None else 9)))
  dow_int = int(dow) if dow and str(dow).isdigit() else 1

  show_dow = (
      {"display": "block"}
      if cadence == ScheduleCadence.WEEKLY.value
      else {"display": "none"}
  )
  show_hour = (
      {"display": "none"}
      if cadence == ScheduleCadence.HOURLY.value
      else {"display": "block"}
  )
  cron_expr = cron.build_preset_cron(
      cadence,
      minute=minute_int,
      hour=hour_int,
      day_of_week=dow_int,
  )
  return {"display": "block"}, show_dow, show_hour, cron_expr


@typed_callback(
    output=(Ids.PREVIEW_CONTAINER, CP.CHILDREN),
    inputs=[
        (Ids.INPUT_CRON, CP.VALUE),
        (Ids.SELECT_TIMEZONE, CP.VALUE),
        (Ids.SWITCH_ENABLED, CP.CHECKED),
        (Ids.SWITCH_SUGGESTIONS, CP.CHECKED),
    ],
)
def update_schedule_preview(
    cron_expression: str | None,
    tz_name: str | None,
    is_enabled: bool,
    generate_suggestions: bool,
):
  """Computes and renders the next 3 scheduled fire times in real time."""
  expr = (cron_expression or "").strip()
  tz = (tz_name or "UTC").strip() or "UTC"
  if not expr:
    return schedule_components.dmc.Alert(
        "Enter a 5-field cron expression to preview upcoming execution times.",
        color="gray",
        variant="light",
        radius="md",
    )

  try:
    upcoming = get_client().schedules.preview_next_runs(
        expr, timezone=tz, count=3
    )
    return schedule_components.render_preview_box(
        cron_expression=expr,
        tz_name=tz,
        upcoming_runs=upcoming,
        is_enabled=bool(is_enabled),
        generate_suggestions=bool(generate_suggestions),
    )
  except ValueError as exc:
    return schedule_components.dmc.Alert(
        str(exc),
        color="yellow",
        variant="light",
        radius="md",
    )


@typed_callback(
    output=[
        dash.Output(Ids.MODAL, CP.OPENED, allow_duplicate=True),
        dash.Output(Ids.MODAL_ERROR, CP.CHILDREN),
        dash.Output(Ids.MODAL_ERROR, CP.HIDE, allow_duplicate=True),
        dash.Output(Ids.UPDATE_SIGNAL, CP.DATA, allow_duplicate=True),
        dash.Output(
            NOTIFICATION_CONTAINER, "sendNotifications", allow_duplicate=True
        ),
        dash.Output("url", CP.SEARCH, allow_duplicate=True),
    ],
    inputs=[(Ids.BTN_SAVE, CP.N_CLICKS)],
    state=[
        (Ids.STORE_EDIT_ID, CP.DATA),
        (Ids.INPUT_NAME, CP.VALUE),
        (Ids.SELECT_AGENT, CP.VALUE),
        (Ids.SELECT_SUITE, CP.VALUE),
        (Ids.SEGMENT_CADENCE, CP.VALUE),
        (Ids.INPUT_CRON, CP.VALUE),
        (Ids.SELECT_TIMEZONE, CP.VALUE),
        (Ids.INPUT_CONCURRENCY, CP.VALUE),
        (Ids.SWITCH_SUGGESTIONS, CP.CHECKED),
        (Ids.SWITCH_ENABLED, CP.CHECKED),
        ("url", CP.SEARCH),
    ],
    prevent_initial_call=True,
    running=[(dash.Output(Ids.BTN_SAVE, "disabled"), True, False)],
)
def save_schedule(
    n_clicks: int | None,
    edit_id: int | None,
    name: str | None,
    agent_id_raw: str | None,
    suite_id_raw: str | None,
    cadence_raw: str | None,
    cron_expression: str | None,
    tz_name: str | None,
    concurrency_raw: int | float | None,
    generate_suggestions: bool,
    is_enabled: bool,
    current_search: str | None,
):
  """Creates or updates an evaluation schedule and refreshes the table."""
  if not n_clicks:
    return (dash.no_update,) * 6

  cleaned_name = (name or "").strip()
  if not cleaned_name:
    return (
        dash.no_update,
        "Schedule name is required.",
        False,
        dash.no_update,
        dash.no_update,
        dash.no_update,
    )
  agent_id = _parse_int(agent_id_raw)
  if agent_id is None:
    return (
        dash.no_update,
        "Select an agent to evaluate.",
        False,
        dash.no_update,
        dash.no_update,
        dash.no_update,
    )
  suite_id = _parse_int(suite_id_raw)
  if suite_id is None:
    return (
        dash.no_update,
        "Select a test suite to run.",
        False,
        dash.no_update,
        dash.no_update,
        dash.no_update,
    )

  concurrency = int(concurrency_raw) if concurrency_raw is not None else 2
  cadence = ScheduleCadence(cadence_raw or ScheduleCadence.DAILY.value)
  tz = (tz_name or "UTC").strip() or "UTC"
  expr = (cron_expression or "").strip()

  client = get_client()
  try:
    if edit_id is not None:
      saved = client.schedules.update_schedule(
          int(edit_id),
          ScheduleUpdate(
              name=cleaned_name,
              agent_id=agent_id,
              test_suite_id=suite_id,
              cadence=cadence,
              cron_expression=expr,
              timezone=tz,
              concurrency=concurrency,
              generate_suggestions=bool(generate_suggestions),
              is_enabled=bool(is_enabled),
          ),
      )
      toast_title = "Schedule Updated"
      toast_msg = f"Updated schedule '{saved.name}'."
    else:
      saved = client.schedules.create_schedule(
          ScheduleCreate(
              name=cleaned_name,
              agent_id=agent_id,
              test_suite_id=suite_id,
              cadence=cadence,
              cron_expression=expr,
              timezone=tz,
              concurrency=concurrency,
              generate_suggestions=bool(generate_suggestions),
              is_enabled=bool(is_enabled),
          )
      )
      toast_title = "Schedule Created"
      toast_msg = f"Created schedule '{saved.name}'."
  except (ValueError, pydantic.ValidationError) as exc:
    return (
        dash.no_update,
        _format_validation_error(exc),
        False,
        dash.no_update,
        dash.no_update,
        dash.no_update,
    )

  cleaned_search = dash.no_update
  if current_search and "create=" in current_search:
    params = urllib.parse.parse_qs(current_search.lstrip("?"))
    params.pop("create", None)
    params.pop("prefill_agent_id", None)
    params.pop("prefill_suite_id", None)
    cleaned_search = (
        f"?{urllib.parse.urlencode(params, doseq=True)}" if params else ""
    )

  notification = {
      "action": "show",
      "title": toast_title,
      "message": toast_msg,
      "color": "green",
  }
  return (
      False,
      "",
      True,
      {"ts": time.time(), "schedule_id": saved.id},
      [notification],
      cleaned_search,
  )


@typed_callback(
    output=[
        dash.Output(Ids.UPDATE_SIGNAL, CP.DATA, allow_duplicate=True),
        dash.Output(
            NOTIFICATION_CONTAINER, "sendNotifications", allow_duplicate=True
        ),
        dash.Output(REDIRECT_HANDLER, CP.HREF, allow_duplicate=True),
    ],
    inputs=[
        ({"type": Ids.BTN_RUN_NOW, "index": dash.ALL}, CP.N_CLICKS),
        ({"type": Ids.BTN_TOGGLE_PAUSE, "index": dash.ALL}, CP.N_CLICKS),
        ({"type": Ids.BTN_ARCHIVE_ROW, "index": dash.ALL}, CP.N_CLICKS),
        ({"type": Ids.BTN_RESTORE_ROW, "index": dash.ALL}, CP.N_CLICKS),
    ],
    prevent_initial_call=True,
)
def handle_schedule_row_actions(
    run_clicks: list[int | None],
    pause_clicks: list[int | None],
    archive_clicks: list[int | None],
    restore_clicks: list[int | None],
):
  """Handles Run Now, Pause/Resume, Archive, and Restore row actions."""
  del run_clicks, pause_clicks, archive_clicks, restore_clicks
  if not any(t.get("value") for t in dash.ctx.triggered):
    return dash.no_update, dash.no_update, dash.no_update

  triggered = dash.ctx.triggered_id
  if not isinstance(triggered, dict) or "index" not in triggered:
    return dash.no_update, dash.no_update, dash.no_update

  action_type = triggered.get("type")
  schedule_id = int(triggered["index"])
  client = get_client()

  try:
    if action_type == Ids.BTN_RUN_NOW:
      run = client.schedules.trigger_schedule_now(schedule_id)
      toast = {
          "action": "show",
          "title": "Scheduled Run Queued",
          "message": f"Queued Run #{run.id} from schedule.",
          "color": "green",
      }
      return (
          {"ts": time.time(), "action": "run_now", "run_id": run.id},
          [toast],
          dash.no_update,
      )

    if action_type == Ids.BTN_TOGGLE_PAUSE:
      current = client.schedules.get_schedule(schedule_id)
      if not current:
        # Redraw the header anyway, to bring back the button the click
        # disabled.
        return (
            {
                "ts": time.time(),
                "action": "missing",
                "schedule_id": schedule_id,
            },
            dash.no_update,
            dash.no_update,
        )
      if current.is_enabled:
        updated = client.schedules.pause_schedule(schedule_id)
        title = "Schedule Paused"
        msg = f"Paused schedule '{updated.name}'."
        color = "yellow"
      else:
        updated = client.schedules.resume_schedule(schedule_id)
        title = "Schedule Resumed"
        msg = f"Resumed schedule '{updated.name}'."
        color = "green"
      return (
          {"ts": time.time(), "action": "toggle", "schedule_id": schedule_id},
          [{"action": "show", "title": title, "message": msg, "color": color}],
          dash.no_update,
      )

    if action_type == Ids.BTN_ARCHIVE_ROW:
      archived = client.schedules.archive_schedule(schedule_id)
      return (
          {"ts": time.time(), "action": "archive", "schedule_id": schedule_id},
          [{
              "action": "show",
              "title": "Schedule Archived",
              "message": f"Archived schedule '{archived.name}'.",
              "color": "blue",
          }],
          dash.no_update,
      )

    if action_type == Ids.BTN_RESTORE_ROW:
      restored = client.schedules.unarchive_schedule(schedule_id)
      return (
          {"ts": time.time(), "action": "restore", "schedule_id": schedule_id},
          [{
              "action": "show",
              "title": "Schedule Restored",
              "message": (
                  f"Restored schedule '{restored.name}' in a paused state."
              ),
              "color": "green",
          }],
          dash.no_update,
      )
  except ValueError as exc:
    # The signal redraws the header, which brings back the button the click
    # disabled.
    return (
        {"ts": time.time(), "action": "refused", "schedule_id": schedule_id},
        [{
            "action": "show",
            "title": "Action Refused",
            "message": str(exc),
            "color": "red",
        }],
        dash.no_update,
    )
  except Exception:  # pylint: disable=broad-except
    # handle_errors would toast this too, but it writes no outputs, so the
    # button the click disabled would stay disabled until a reload.
    logger.exception(
        "Schedule action %s failed for %s", action_type, schedule_id
    )
    return (
        {"ts": time.time(), "action": "failed", "schedule_id": schedule_id},
        [{
            "action": "show",
            "title": "Action Failed",
            "message": "The action failed. Check the server log for details.",
            "color": "red",
        }],
        dash.no_update,
    )

  return dash.no_update, dash.no_update, dash.no_update


# Disable a schedule action button in the browser as soon as it is clicked, so
# a double click on it sends one request. A double click on Run Now used to
# send two: the second was refused because the first had started a run, and
# Dash keeps only the newest response, so the only toast was a red "Action
# Refused". The header redraw that follows every action brings back fresh,
# enabled buttons. Done client side because running= with ALL ids breaks the
# Dash 4 renderer.
for _button in (
    Ids.BTN_RUN_NOW,
    Ids.BTN_TOGGLE_PAUSE,
    Ids.BTN_ARCHIVE_ROW,
    Ids.BTN_RESTORE_ROW,
):
  dash.clientside_callback(
      """
      function(nClicks) {
          if (!nClicks) {
              return window.dash_clientside.no_update;
          }
          // A request that dies without a response never redraws the header,
          // so bring the button back after longer than an action takes.
          const id = window.dash_clientside.callback_context.triggered_id;
          setTimeout(
              () => window.dash_clientside.set_props(id, {disabled: false}),
              15000);
          return true;
      }
      """,
      dash.Output({"type": _button, "index": dash.MATCH}, CP.DISABLED),
      dash.Input({"type": _button, "index": dash.MATCH}, CP.N_CLICKS),
      prevent_initial_call=True,
  )
del _button
