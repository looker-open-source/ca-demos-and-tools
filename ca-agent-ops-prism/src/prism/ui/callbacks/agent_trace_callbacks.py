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

"""Callbacks for Agent Trace page."""

import json
import dash
from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.client import get_client
from prism.ui.components import timeline
from prism.ui.pages.evaluation_ids import EvaluationIds as Ids
from prism.ui.utils import typed_callback


@typed_callback(
    [
        (Ids.AGENT_TRACE_BREADCRUMBS_CONTAINER, "children"),
        (Ids.AGENT_TRACE_TITLE, "children"),
        (Ids.AGENT_TRACE_STATUS, "children"),
        (Ids.AGENT_TRACE_STATUS, "color"),
        (Ids.AGENT_TRACE_ACTIONS, "children"),
        (Ids.AGENT_TRACE_CONTAINER, "children"),
        (Ids.AGENT_TRACE_RAW_STORE, "data"),
    ],
    inputs=[("url", "pathname")],
)
def render_agent_trace(
    pathname: str,
):
  """Renders the Agent Trace page content."""
  if (
      not pathname
      or not pathname.endswith("/trace")
      or "/evaluations/trials/" not in pathname
  ):
    return (
        dash.no_update,
        dash.no_update,
        dash.no_update,
        dash.no_update,
        dash.no_update,
        dash.no_update,
        dash.no_update,
    )

  try:
    trial_id_str = pathname.split("/")[-2]
    trial_id = int(trial_id_str)
  except (ValueError, IndexError):
    return (
        dash.no_update,
        "Error",
        None,
        "gray",
        None,
        dmc.Alert("Invalid Trial ID", color="red"),
        dash.no_update,
    )

  runs_client = get_client().runs
  trial = runs_client.get_trial(trial_id)
  if not trial:
    return (
        dash.no_update,
        "Error",
        None,
        "gray",
        None,
        dmc.Alert("Trial not found", color="red"),
        dash.no_update,
    )

  timeline_obj = runs_client.get_trial_timeline(trial_id)
  if not timeline_obj:
    return (
        dash.no_update,
        f"Agent Trace for Trial #{trial.id}",
        None,
        "gray",
        None,
        dmc.Alert("Timeline generation failed", color="red"),
        dash.no_update,
    )

  timeline_data = timeline_obj.model_dump()

  # Extract duration and raw trace for other components
  duration_ms = getattr(trial, "duration_ms", 0) or 0

  trace_results = getattr(trial, "trace_results", []) or []
  if isinstance(trace_results, dict):
    trace_results = trace_results.get("response", [])
  raw_trace_json = json.dumps(trace_results, indent=2)

  # Status Label
  status_color = "green" if trial.status.value == "COMPLETED" else "red"
  status_label = "Success" if trial.status.value == "COMPLETED" else "Failed"

  # Actions
  actions = [
      dmc.Button(
          "Download full trace",
          id=Ids.AGENT_TRACE_DOWNLOAD_BTN,
          leftSection=DashIconify(icon="bi:download", width=16),
          color="gray",
          variant="default",
          size="sm",
          fw=600,
      ),
      dmc.Button(
          "View raw trace",
          id=Ids.AGENT_TRACE_VIEW_RAW_BTN,
          leftSection=DashIconify(icon="bi:eye", width=16),
          variant="default",
          color="gray",
          size="sm",
          fw=600,
      ),
  ]

  # Unified Breadcrumbs: Evaluations / Run #<run_id> / Trial #<trial_id> / Trace
  breadcrumbs = dmc.Breadcrumbs(
      separator="/",
      mb="lg",
      children=[
          dmc.Anchor("Evaluations", href="/evaluations", size="sm", fw=500),
          dmc.Anchor(
              f"Run #{trial.run_id}",
              href=f"/evaluations/runs/{trial.run_id}",
              size="sm",
              fw=500,
          ),
          dmc.Anchor(
              f"Trial #{trial.id}",
              href=f"/evaluations/trials/{trial.id}",
              size="sm",
              fw=500,
          ),
          dmc.Text("Trace", size="sm", fw=500, c="dimmed"),
      ],
  )

  timeline_card = dmc.Paper(
      withBorder=True,
      radius="md",
      children=[
          dmc.Group(
              [
                  dmc.Group(
                      [
                          dmc.Text("Execution Timeline", fw=700, size="lg"),
                          dmc.Badge(
                              f"{duration_ms/1000:.1f}s",
                              color="blue",
                              variant="light",
                              size="sm",
                              radius="sm",
                          ),
                      ],
                      gap="sm",
                  ),
                  dmc.Text(
                      "TRACE",
                      size="xs",
                      fw=700,
                      c="dimmed",
                      style={"letterSpacing": "1px"},
                  ),
              ],
              justify="space-between",
              p="lg",
              style={"borderBottom": "1px solid var(--mantine-color-gray-2)"},
          ),
          html.Div(
              timeline.render_trace_timeline(timeline_data),
              style={"padding": "24px"},
          ),
      ],
  )

  return (
      breadcrumbs,
      f"Agent Trace for Trial #{trial.id}",
      status_label,
      status_color,
      actions,
      timeline_card,
      raw_trace_json,
  )


@typed_callback(
    [
        (Ids.AGENT_TRACE_RAW_MODAL, "opened"),
        (Ids.AGENT_TRACE_RAW_MODAL + "-content", "children"),
    ],
    inputs=[(Ids.AGENT_TRACE_VIEW_RAW_BTN, "n_clicks")],
    state=[(Ids.AGENT_TRACE_RAW_STORE, "data")],
    prevent_initial_call=True,
)
def toggle_raw_modal(n_clicks: int, raw_data: str):
  """Opens the raw trace modal."""
  if not n_clicks:
    return dash.no_update, dash.no_update
  return True, raw_data


@typed_callback(
    (Ids.AGENT_TRACE_DOWNLOAD_COMPONENT, "data"),
    inputs=[(Ids.AGENT_TRACE_DOWNLOAD_BTN, "n_clicks")],
    state=[
        (Ids.AGENT_TRACE_RAW_STORE, "data"),
        ("url", "pathname"),
    ],
    prevent_initial_call=True,
)
def download_trace(n_clicks: int, raw_data: str, pathname: str):
  """Downloads the raw trace as a JSON file."""
  if not n_clicks:
    return dash.no_update

  trial_id = "unknown"
  try:
    trial_id = pathname.split("/")[-2]
  except (ValueError, IndexError):
    pass

  return dict(content=raw_data, filename=f"trace_{trial_id}.json")
