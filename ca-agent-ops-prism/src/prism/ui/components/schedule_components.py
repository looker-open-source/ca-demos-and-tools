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

"""Presentational components for Scheduled Evaluations."""

import datetime
from typing import Any
import zoneinfo

from dash import dcc
from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.common import cron
from prism.common.schemas.execution import RunSchema
from prism.common.schemas.schedule import MAX_SCHEDULE_CONCURRENCY
from prism.common.schemas.schedule import ScheduleCadence
from prism.common.schemas.schedule import ScheduleSchema
from prism.common.schemas.schedule import SKIPPED_ACTIVE_RUN_MESSAGE
from prism.ui import utils
from prism.ui.components import badges
from prism.ui.components import cards
from prism.ui.components import tables
from prism.ui.ids import ScheduleIds

_DOW_OPTIONS = [
    {"label": "Sunday", "value": "0"},
    {"label": "Monday", "value": "1"},
    {"label": "Tuesday", "value": "2"},
    {"label": "Wednesday", "value": "3"},
    {"label": "Thursday", "value": "4"},
    {"label": "Friday", "value": "5"},
    {"label": "Saturday", "value": "6"},
]

_HEADER_CELL_STYLE = {
    "fontSize": "11px",
    "fontWeight": 600,
    "color": "var(--mantine-color-gray-6)",
    "letterSpacing": "0.05em",
    "padding": "12px 10px",
    "textAlign": "left",
    "whiteSpace": "nowrap",
}


def _summary_item(label: str, value: str, mono: bool = False) -> dmc.Stack:
  """Renders one metric column inside the unified schedule status strip."""
  return dmc.Stack(
      gap=4,
      children=[
          dmc.Text(
              label,
              size="xs",
              c="dimmed",
              tt="uppercase",
              fw=700,
              lts=0.5,
          ),
          dmc.Text(
              value,
              size="lg",
              fw=700,
              ff="monospace" if mono else None,
          ),
      ],
  )


def render_schedule_summary_strip(
    schedules: list[ScheduleSchema],
    total_scheduled_runs: int,
) -> dmc.Paper:
  """Renders the unified operational summary strip for active schedules."""
  active_schedules = [
      s for s in schedules if s.is_enabled and not s.is_archived
  ]
  paused_schedules = [
      s for s in schedules if (not s.is_enabled) and not s.is_archived
  ]
  upcoming_times = [
      s.next_run_at for s in active_schedules if s.next_run_at is not None
  ]
  next_due_str = (
      utils.format_timestamp(min(upcoming_times))
      if upcoming_times
      else "No active schedules"
  )

  return dmc.Paper(
      withBorder=True,
      radius="md",
      p="lg",
      shadow="sm",
      children=[
          dmc.SimpleGrid(
              cols={"base": 2, "md": 4},
              spacing="lg",
              children=[
                  _summary_item(
                      "Active Schedules",
                      str(len(active_schedules)),
                      mono=True,
                  ),
                  _summary_item(
                      "Paused Schedules",
                      str(len(paused_schedules)),
                      mono=True,
                  ),
                  _summary_item(
                      "Next Due Run",
                      next_due_str,
                  ),
                  _summary_item(
                      "Scheduled Runs",
                      str(total_scheduled_runs),
                      mono=True,
                  ),
              ],
          )
      ],
  )


def render_empty_schedules_state() -> dmc.Paper:
  """Renders the empty state when no schedules match the current filters."""
  return dmc.Paper(
      withBorder=True,
      radius="md",
      p="xl",
      shadow="sm",
      children=[
          dmc.Center(
              py="xl",
              children=dmc.Stack(
                  align="center",
                  gap="sm",
                  maw=460,
                  children=[
                      dmc.ThemeIcon(
                          DashIconify(
                              icon="material-symbols:calendar-clock", width=24
                          ),
                          variant="light",
                          color="blue",
                          size="xl",
                          radius="md",
                      ),
                      dmc.Text(
                          "No evaluation schedules configured",
                          fw=700,
                          size="lg",
                          ta="center",
                      ),
                      dmc.Text(
                          "Automate recurring evaluations against your agents"
                          " on an hourly, daily, weekly, or custom cron"
                          " cadence.",
                          size="sm",
                          c="dimmed",
                          ta="center",
                      ),
                      dmc.Button(
                          "Create Schedule",
                          id={
                              "type": ScheduleIds.BTN_EMPTY_CREATE,
                              "index": "empty",
                          },
                          variant="light",
                          color="blue",
                          radius="md",
                          mt="xs",
                          leftSection=DashIconify(icon="bi:plus-lg", width=16),
                      ),
                  ],
              ),
          )
      ],
  )


def _render_last_run_cell(schedule: ScheduleSchema):
  """Renders the Last Run cell linking to the most recent scheduled run."""
  if not schedule.last_run_id:
    return dmc.Text("Never", size="sm", c="dimmed")

  children = [
      dmc.Anchor(
          f"#{schedule.last_run_id}",
          href=f"/evaluations/runs/{schedule.last_run_id}",
          size="sm",
          fw=600,
          ff="monospace",
      )
  ]
  if schedule.last_run_status is not None:
    status_color, status_label = utils.run_status_display(
        schedule.last_run_status
    )
    children.append(badges.render_status_badge(status_label, status_color))
  return dmc.Group(gap="xs", wrap="nowrap", children=children)


def schedule_detail_href(schedule_id: int) -> str:
  """Returns the Schedule Detail page path for `schedule_id`."""
  return f"/schedules/view/{schedule_id}"


def render_schedule_status_badge(schedule: ScheduleSchema) -> dmc.Badge:
  """Renders the Active, Paused, or Archived badge for a schedule."""
  if schedule.is_archived:
    return badges.render_status_badge("Archived", "gray")
  if schedule.is_enabled:
    return badges.render_status_badge("Active", "green")
  return badges.render_status_badge("Paused", "yellow")


def _next_run_text(schedule: ScheduleSchema) -> str:
  """Returns the Next Run label, which only an active schedule has a time for."""
  if schedule.is_archived:
    return "Archived"
  if not schedule.is_enabled:
    return "Paused"
  if schedule.next_run_at:
    return utils.format_timestamp(schedule.next_run_at)
  return "Pending calculation"


def _render_dispatch_failed_badge(message: str) -> dmc.Tooltip:
  """Renders the badge flagging that the last due tick failed or was skipped."""
  skipped = message == SKIPPED_ACTIVE_RUN_MESSAGE
  return dmc.Tooltip(
      label=cards.error_summary_line(message),
      withArrow=True,
      maw=380,
      multiline=True,
      children=dmc.Badge(
          "Last Run Skipped" if skipped else "Last Dispatch Failed",
          variant="light",
          color="yellow" if skipped else "red",
          size="xs",
          radius="md",
          style={"flexShrink": 0},
          styles={"label": {"overflow": "visible"}},
      ),
  )


def render_schedule_table(schedules: list[ScheduleSchema]) -> dmc.Paper:
  """Renders the read-only table of evaluation schedules.

  Each row is a summary that links to the Schedule Detail page, which holds the
  full configuration, run history, and the Run Now, Pause, Edit, and Archive
  actions. With all of that inline the table outgrew the page and scrolled
  sideways, hiding the actions column.

  Args:
    schedules: The schedules matching the current filters.

  Returns:
    The table, or the empty state when there are no schedules.
  """
  if not schedules:
    return render_empty_schedules_state()

  rows = []
  for schedule in schedules:
    detail_href = schedule_detail_href(schedule.id)
    name_row_items = [
        dmc.Anchor(
            schedule.name,
            href=detail_href,
            size="sm",
            fw=600,
            c="dark",
            style={"overflowWrap": "break-word"},
        ),
    ]
    if schedule.last_error_message:
      name_row_items.append(
          _render_dispatch_failed_badge(schedule.last_error_message)
      )

    agent_label = schedule.agent_name or f"Agent {schedule.agent_id}"
    suite_label = schedule.suite_name or f"Suite {schedule.test_suite_id}"

    rows.append(
        html.Tr(
            children=[
                html.Td(
                    dmc.Group(gap="xs", children=name_row_items),
                    style={"padding": "14px", "maxWidth": "260px"},
                ),
                html.Td(
                    dmc.Stack(
                        gap=2,
                        children=[
                            dmc.Text(agent_label, size="sm", fw=500),
                            dmc.Text(suite_label, size="xs", c="dimmed"),
                        ],
                    ),
                    style={"padding": "14px 10px", "maxWidth": "240px"},
                ),
                html.Td(
                    dmc.Text(
                        cron.describe_cron(
                            schedule.cron_expression, schedule.timezone
                        ),
                        size="sm",
                    ),
                    style={"padding": "14px 10px", "maxWidth": "220px"},
                ),
                html.Td(
                    render_schedule_status_badge(schedule),
                    style={"padding": "14px 10px", "whiteSpace": "nowrap"},
                ),
                html.Td(
                    dmc.Text(_next_run_text(schedule), size="xs", c="dimmed"),
                    style={"padding": "14px 10px", "whiteSpace": "nowrap"},
                ),
                html.Td(
                    _render_last_run_cell(schedule),
                    style={"padding": "14px 10px", "whiteSpace": "nowrap"},
                ),
                html.Td(
                    dmc.Anchor(
                        DashIconify(icon="bi:chevron-right", width=16),
                        href=detail_href,
                        c="gray",
                        **{"aria-label": f"Open schedule {schedule.name}"},
                    ),
                    style={"padding": "14px", "textAlign": "right"},
                ),
            ]
        )
    )

  table_head = html.Thead(
      html.Tr(
          [
              html.Th("SCHEDULE", style=_HEADER_CELL_STYLE),
              html.Th("AGENT / TEST SUITE", style=_HEADER_CELL_STYLE),
              html.Th("CADENCE", style=_HEADER_CELL_STYLE),
              html.Th("STATUS", style=_HEADER_CELL_STYLE),
              html.Th("NEXT RUN", style=_HEADER_CELL_STYLE),
              html.Th("LAST RUN", style=_HEADER_CELL_STYLE),
              html.Th("", style=_HEADER_CELL_STYLE),
          ],
          style={
              "backgroundColor": "var(--mantine-color-gray-0)",
              "borderBottom": "1px solid var(--mantine-color-gray-2)",
          },
      )
  )

  return dmc.Paper(
      withBorder=True,
      radius="md",
      p=0,
      shadow="sm",
      style={"overflow": "hidden"},
      children=[
          html.Div(
              dmc.Table(
                  children=[table_head, html.Tbody(rows)],
                  verticalSpacing=0,
                  horizontalSpacing=0,
                  highlightOnHover=True,
                  withTableBorder=False,
              ),
              style={"overflowX": "auto"},
          )
      ],
  )


def render_schedule_detail_breadcrumbs(name: str) -> dmc.Breadcrumbs:
  """Renders the Schedules / <name> breadcrumbs on the detail page."""
  return dmc.Breadcrumbs(
      separator="/",
      mb="lg",
      children=[
          dmc.Anchor("Schedules", href="/schedules", size="sm", fw=500),
          dmc.Text(name, size="sm", fw=500, c="dimmed"),
      ],
  )


def render_schedule_detail_status(schedule: ScheduleSchema) -> dmc.Group:
  """Renders the status badge and dispatch failure flag beside the title."""
  children = [render_schedule_status_badge(schedule)]
  if schedule.last_error_message:
    children.append(_render_dispatch_failed_badge(schedule.last_error_message))
  return dmc.Group(gap="xs", wrap="nowrap", children=children)


def render_schedule_detail_actions(schedule: ScheduleSchema) -> list[Any]:
  """Renders the header actions for the Schedule Detail page.

  An archived schedule does not run, so it only offers Restore.

  Args:
    schedule: The schedule the page shows.

  Returns:
    The header buttons.
  """
  if schedule.is_archived:
    return [
        dmc.Button(
            "Restore",
            id={"type": ScheduleIds.BTN_RESTORE_ROW, "index": schedule.id},
            variant="filled",
            color="green",
            radius="md",
            leftSection=DashIconify(
                icon="material-symbols:settings-backup-restore", width=18
            ),
        )
    ]

  toggle_label = "Pause" if schedule.is_enabled else "Resume"
  toggle_icon = "bi:pause-fill" if schedule.is_enabled else "bi:play-circle"
  return [
      dmc.Button(
          "Run Now",
          id={"type": ScheduleIds.BTN_RUN_NOW, "index": schedule.id},
          radius="md",
          leftSection=DashIconify(icon="bi:play-fill", width=18),
      ),
      dmc.Button(
          toggle_label,
          id={"type": ScheduleIds.BTN_TOGGLE_PAUSE, "index": schedule.id},
          variant="default",
          radius="md",
          leftSection=DashIconify(icon=toggle_icon, width=18),
      ),
      dmc.Button(
          "Edit",
          id={"type": ScheduleIds.BTN_EDIT, "index": schedule.id},
          variant="default",
          radius="md",
          leftSection=DashIconify(icon="material-symbols:edit", width=18),
      ),
      dmc.Button(
          "Archive",
          id={"type": ScheduleIds.BTN_ARCHIVE_ROW, "index": schedule.id},
          variant="outline",
          color="gray",
          radius="md",
          leftSection=DashIconify(icon="material-symbols:archive", width=18),
      ),
  ]


def render_schedule_detail_stats(schedule: ScheduleSchema) -> list[dmc.Paper]:
  """Renders the Agent, Test Suite, Cadence, and Next Run stat cards."""
  return [
      cards.render_stat_card(
          "Agent",
          schedule.agent_name or f"Agent {schedule.agent_id}",
          icon="bi:robot",
          color="blue",
          value_href=f"/agents/view/{schedule.agent_id}",
      ),
      cards.render_stat_card(
          "Test Suite",
          schedule.suite_name or f"Suite {schedule.test_suite_id}",
          icon="material-symbols:folder-open",
          color="blue",
          value_href=f"/test_suites/view/{schedule.test_suite_id}",
      ),
      # The timezone is in the Configuration card. Left in, it pushed the
      # cadence past the card width and truncated it.
      cards.render_stat_card(
          "Cadence",
          cron.describe_cron(
              schedule.cron_expression, schedule.timezone
          ).removesuffix(f" ({schedule.timezone})"),
          icon="material-symbols:calendar-clock",
          color="indigo",
      ),
      cards.render_stat_card(
          "Next Run",
          _next_run_text(schedule),
          icon="material-symbols:schedule",
          color="teal",
      ),
  ]


def _config_row(label: str, value: Any) -> dmc.Group:
  """Renders one label and value row in the configuration card."""
  return dmc.Group(
      justify="space-between",
      wrap="nowrap",
      children=[
          dmc.Text(label, size="sm", c="dimmed"),
          value
          if not isinstance(value, str)
          else dmc.Text(value, size="sm", fw=500),
      ],
  )


def render_schedule_config_card(schedule: ScheduleSchema) -> dmc.Card:
  """Renders the full schedule configuration, including the raw cron."""
  rows = [
      _config_row("Cron expression", dmc.Code(schedule.cron_expression)),
      _config_row("Timezone", schedule.timezone),
      _config_row("Cadence type", schedule.cadence.value.title()),
      _config_row("Concurrency", str(schedule.concurrency)),
      _config_row(
          "Assertion suggestions",
          "On" if schedule.generate_suggestions else "Off",
      ),
      # No modified_at row: every dispatch writes last_run_* and bumps it, so
      # it read as a config edit on each run.
      _config_row("Created", utils.format_timestamp(schedule.created_at)),
  ]
  if schedule.last_error_message:
    skipped = schedule.last_error_message == SKIPPED_ACTIVE_RUN_MESSAGE
    rows.append(
        dmc.Alert(
            cards.error_summary_line(schedule.last_error_message),
            title="Last run skipped" if skipped else "Last dispatch failed",
            color="yellow" if skipped else "red",
            variant="light",
            radius="md",
        )
    )
  return cards.render_detail_card(
      title="Configuration",
      icon="material-symbols:tune",
      children=dmc.Stack(gap="sm", children=rows),
  )


def render_upcoming_runs_card(
    schedule: ScheduleSchema, upcoming_runs: list[datetime.datetime]
) -> dmc.Card:
  """Renders the next fire times, or why there are none."""
  if schedule.is_archived:
    body = dmc.Text(
        "Archived schedules do not run. Restore it to schedule upcoming runs.",
        size="sm",
        c="dimmed",
    )
  elif not schedule.is_enabled:
    body = dmc.Text(
        "Paused. Resume the schedule to queue upcoming runs.",
        size="sm",
        c="dimmed",
    )
  else:
    tz = zoneinfo.ZoneInfo(schedule.timezone)
    time_rows = []
    for idx, run_utc in enumerate(upcoming_runs, start=1):
      local_str = run_utc.astimezone(tz).strftime("%Y-%m-%d %H:%M %Z")
      display_line = (
          local_str
          if schedule.timezone == "UTC"
          else f"{local_str} ({utils.format_timestamp(run_utc)})"
      )
      time_rows.append(
          dmc.Group(
              justify="space-between",
              children=[
                  dmc.Text(f"Run {idx}", size="sm", c="dimmed", fw=600),
                  dmc.Text(display_line, size="sm", fw=500, ff="monospace"),
              ],
          )
      )
    body = dmc.Stack(gap="sm", children=time_rows)
  return cards.render_detail_card(
      title="Upcoming Runs",
      icon="material-symbols:event-upcoming",
      children=body,
  )


def render_schedule_runs_card(
    schedule: ScheduleSchema, runs: list[RunSchema]
) -> dmc.Card:
  """Renders the recent runs this schedule triggered."""
  view_all = dmc.Anchor(
      "View all in Evaluations",
      href=f"/evaluations?schedule_id={schedule.id}",
      size="sm",
      fw=600,
  )
  if runs:
    body = tables.render_run_table(
        runs,
        agent_names={schedule.agent_id: schedule.agent_name or ""},
        suite_names={schedule.test_suite_id: schedule.suite_name or ""},
    )
  else:
    body = dmc.Text(
        "No runs yet. Use Run Now to trigger one.",
        size="sm",
        c="dimmed",
        ta="center",
        py="lg",
    )
  return cards.render_detail_card(
      title="Run History",
      icon="material-symbols:history",
      action=view_all,
      children=body,
  )


def render_schedule_not_found(schedule_id: str) -> dmc.Alert:
  """Renders the body shown when the path names no schedule."""
  return dmc.Alert(
      f"Schedule {schedule_id} was not found.",
      title="Schedule not found",
      color="red",
      variant="light",
      radius="md",
  )


def render_preview_box(
    cron_expression: str,
    tz_name: str,
    upcoming_runs: list[datetime.datetime],
    is_enabled: bool,
    generate_suggestions: bool,
) -> dmc.Paper:
  """Renders the live preview of upcoming fire times in local timezone and UTC."""
  tz = zoneinfo.ZoneInfo(tz_name)
  state_text = "Starts active" if is_enabled else "Saved in paused state"
  if generate_suggestions:
    state_text = f"{state_text}, assertion suggestions enabled"

  time_rows = []
  for idx, run_utc in enumerate(upcoming_runs, start=1):
    local_dt = run_utc.astimezone(tz)
    local_str = local_dt.strftime("%Y-%m-%d %H:%M %Z")
    utc_str = utils.format_timestamp(run_utc)
    display_line = local_str if tz_name == "UTC" else f"{local_str} ({utc_str})"
    time_rows.append(
        dmc.Group(
            justify="space-between",
            children=[
                dmc.Text(f"Run {idx}", size="xs", c="dimmed", fw=600),
                dmc.Text(display_line, size="xs", fw=500, ff="monospace"),
            ],
        )
    )

  return dmc.Paper(
      withBorder=True,
      radius="md",
      p="sm",
      bg="gray.0",
      children=dmc.Stack(
          gap=6,
          children=[
              dmc.Group(
                  justify="space-between",
                  children=[
                      dmc.Text(
                          cron.describe_cron(cron_expression, tz_name),
                          size="xs",
                          fw=700,
                      ),
                      dmc.Text(state_text, size="xs", c="dimmed"),
                  ],
              ),
              *time_rows,
          ],
      ),
  )


def render_schedule_modal() -> dmc.Modal:
  """Renders the Create / Edit Schedule modal."""
  return dmc.Modal(
      id=ScheduleIds.MODAL,
      title=dmc.Text(
          "New Evaluation Schedule",
          id=ScheduleIds.MODAL_TITLE,
          fw=700,
          size="lg",
      ),
      size="lg",
      radius="md",
      centered=True,
      children=[
          dcc.Store(id=ScheduleIds.STORE_EDIT_ID, data=None),
          dmc.Stack(
              gap="md",
              children=[
                  dmc.Alert(
                      "",
                      id=ScheduleIds.MODAL_ERROR,
                      color="red",
                      variant="light",
                      radius="md",
                      hide=True,
                      icon=DashIconify(icon="bi:exclamation-triangle-fill"),
                  ),
                  dmc.TextInput(
                      id=ScheduleIds.INPUT_NAME,
                      label="Schedule Name",
                      placeholder="e.g. Nightly Finance Suite Check",
                      required=True,
                      radius="md",
                  ),
                  dmc.SimpleGrid(
                      cols={"base": 1, "sm": 2},
                      spacing="md",
                      children=[
                          dmc.Select(
                              id=ScheduleIds.SELECT_AGENT,
                              label="Agent",
                              placeholder="Select an agent",
                              searchable=True,
                              required=True,
                              data=[],
                          ),
                          dmc.Select(
                              id=ScheduleIds.SELECT_SUITE,
                              label="Test Suite",
                              placeholder="Select a test suite",
                              searchable=True,
                              required=True,
                              data=[],
                          ),
                      ],
                  ),
                  dmc.Stack(
                      gap=6,
                      children=[
                          dmc.Text("Cadence", size="sm", fw=500),
                          dmc.SegmentedControl(
                              id=ScheduleIds.SEGMENT_CADENCE,
                              value=ScheduleCadence.DAILY.value,
                              fullWidth=True,
                              data=[
                                  {"label": "Hourly", "value": "HOURLY"},
                                  {"label": "Daily", "value": "DAILY"},
                                  {"label": "Weekly", "value": "WEEKLY"},
                                  {"label": "Custom Cron", "value": "CUSTOM"},
                              ],
                          ),
                      ],
                  ),
                  html.Div(
                      id=ScheduleIds.PRESET_CONTROLS,
                      children=[
                          dmc.Group(
                              gap="md",
                              align="flex-end",
                              children=[
                                  html.Div(
                                      id=ScheduleIds.PRESET_DOW_WRAPPER,
                                      style={"display": "none"},
                                      children=[
                                          dmc.Select(
                                              id=ScheduleIds.SELECT_DOW,
                                              label="Day of Week",
                                              value="1",
                                              allowDeselect=False,
                                              data=_DOW_OPTIONS,
                                              style={"width": 160},
                                          )
                                      ],
                                  ),
                                  html.Div(
                                      id=ScheduleIds.PRESET_HOUR_WRAPPER,
                                      children=[
                                          dmc.NumberInput(
                                              id=ScheduleIds.INPUT_HOUR,
                                              label="Hour (0-23)",
                                              value=9,
                                              min=0,
                                              max=23,
                                              step=1,
                                              allowDecimal=False,
                                              style={"width": 130},
                                          )
                                      ],
                                  ),
                                  dmc.NumberInput(
                                      id=ScheduleIds.INPUT_MINUTE,
                                      label="Minute (0-59)",
                                      value=0,
                                      min=0,
                                      max=59,
                                      step=1,
                                      allowDecimal=False,
                                      style={"width": 140},
                                  ),
                              ],
                          )
                      ],
                  ),
                  dmc.SimpleGrid(
                      cols={"base": 1, "sm": 2},
                      spacing="md",
                      children=[
                          dmc.TextInput(
                              id=ScheduleIds.INPUT_CRON,
                              label="Cron Expression (5-field)",
                              value="0 9 * * *",
                              description=(
                                  "minute hour day_of_month month day_of_week"
                              ),
                              styles={"input": {"fontFamily": "monospace"}},
                          ),
                          dmc.Select(
                              id=ScheduleIds.SELECT_TIMEZONE,
                              label="Timezone",
                              # Also lines the select up with the cron input,
                              # which has a description under its label.
                              description="Cron fields are read in this zone",
                              value="UTC",
                              searchable=True,
                              allowDeselect=False,
                              data=[
                                  {"label": tz, "value": tz}
                                  for tz in cron.COMMON_TIMEZONES
                              ],
                          ),
                      ],
                  ),
                  html.Div(id=ScheduleIds.PREVIEW_CONTAINER),
                  dmc.SimpleGrid(
                      cols={"base": 1, "sm": 2},
                      spacing="md",
                      children=[
                          dmc.NumberInput(
                              id=ScheduleIds.INPUT_CONCURRENCY,
                              label="Trial Concurrency",
                              description=(
                                  "Parallel trials per run (1 to"
                                  f" {MAX_SCHEDULE_CONCURRENCY})."
                              ),
                              value=2,
                              min=1,
                              max=MAX_SCHEDULE_CONCURRENCY,
                              step=1,
                              allowDecimal=False,
                          ),
                          dmc.Stack(
                              gap="sm",
                              pt=4,
                              children=[
                                  dmc.Switch(
                                      id=ScheduleIds.SWITCH_SUGGESTIONS,
                                      label="Generate Suggested Assertions",
                                      description=(
                                          "Propose new assertions from"
                                          " completed trial traces."
                                      ),
                                      checked=False,
                                  ),
                                  dmc.Switch(
                                      id=ScheduleIds.SWITCH_ENABLED,
                                      label="Active Schedule",
                                      description=(
                                          "Automatically queue runs when due."
                                      ),
                                      checked=True,
                                  ),
                              ],
                          ),
                      ],
                  ),
                  dmc.Group(
                      justify="flex-end",
                      mt="sm",
                      children=[
                          dmc.Button(
                              "Cancel",
                              id=ScheduleIds.BTN_CANCEL,
                              variant="subtle",
                              color="gray",
                              radius="md",
                          ),
                          dmc.Button(
                              "Save Schedule",
                              id=ScheduleIds.BTN_SAVE,
                              color="blue",
                              radius="md",
                              leftSection=DashIconify(
                                  icon="material-symbols:check", width=18
                              ),
                          ),
                      ],
                  ),
              ],
          ),
      ],
  )
