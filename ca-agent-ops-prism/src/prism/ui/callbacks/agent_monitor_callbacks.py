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

"""Callbacks for the Monitor Existing Agent page."""

import json
import logging
import dash
from dash import html
from dash import Input
from dash import Output
from dash import State
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.client import get_client
from prism.common.schemas.agent import AgentBase
from prism.ui.constants import CP
from prism.ui.constants import GLOBAL_PROJECT_ID_STORE
from prism.ui.pages.agent_ids import agent_monitor_btn_add_id
from prism.ui.pages.agent_ids import AgentIds
from prism.ui.utils import typed_callback


@typed_callback(
    Output(AgentIds.Monitor.INPUT_PROJECT, "data"),
    [Input("url", CP.PATHNAME)],
)
def load_project_id_options_monitor(pathname: str):
  """Loads configured GDA projects as options for the Select component."""
  if pathname != "/agents/onboard/existing":
    return dash.no_update
  projects = get_client().agents.get_configured_gda_projects()
  return [{"label": p, "value": p} for p in projects]


@typed_callback(
    Output(AgentIds.Monitor.INPUT_PROJECT, CP.VALUE),
    [Input(AgentIds.Monitor.INPUT_PROJECT, "data")],
    [State(GLOBAL_PROJECT_ID_STORE, "data")],
)
def populate_project_id_monitor(
    options: list[dict[str, str]], project_id: str | None
):
  """Pre-populates the GCP project ID field."""
  if not options:
    return dash.no_update

  if project_id and any(o["value"] == project_id for o in options):
    return project_id

  return options[0]["value"]


logger = logging.getLogger(__name__)


def _render_table_skeleton():
  """Returns a skeleton placeholder for the table."""
  return dmc.Stack(
      gap="md",
      p="xl",
      children=[dmc.Skeleton(height=50, radius="md") for _ in range(5)],
  )


@typed_callback(
    [
        Output(AgentIds.Monitor.TABLE_ROOT, CP.CHILDREN, allow_duplicate=True),
        Output(AgentIds.Monitor.STORE_FETCH_TRIGGER, CP.DATA),
    ],
    [Input(AgentIds.Monitor.BTN_FETCH, CP.N_CLICKS)],
    prevent_initial_call=True,
)
def start_discovery(n_clicks):
  """Starts discovery by showing skeletons and triggering the fetch."""
  if not n_clicks:
    return dash.no_update, dash.no_update
  return _render_table_skeleton(), True


@typed_callback(
    [
        Output(AgentIds.Monitor.TABLE_ROOT, CP.CHILDREN, allow_duplicate=True),
        Output("discovered-agents-store", "data"),
    ],
    [Input(AgentIds.Monitor.STORE_FETCH_TRIGGER, CP.DATA)],
    state=[
        State(AgentIds.Monitor.INPUT_PROJECT, CP.VALUE),
        State(AgentIds.Monitor.INPUT_LOCATION, CP.VALUE),
    ],
    prevent_initial_call=True,
)
def perform_discovery(
    trigger,
    project_id,
    location,
):
  """Fetches agents from GCP and renders a selection table."""
  if not trigger or not project_id or not location:
    return dash.no_update, dash.no_update

  # Format parent log just for info (client handles logic now)
  parent = f"projects/{project_id}/locations/{location}"
  logger.info("Fetching GCP agents for %s", parent)

  client = get_client().agents

  try:
    discovered = client.discover_gcp_agents(
        project_id=project_id, location=location
    )
  except Exception as e:
    logger.error("Failed to list GDA agents: %s", e)
    return (
        dmc.Alert(f"Failed to fetch agents: {e}", color="red"),
        [],
    )

  logger.info("Found %d agents on GCP", len(discovered) if discovered else 0)

  if not discovered:
    return (
        dmc.Alert("No agents found in this project/location.", color="yellow"),
        [],
    )

  # Filter out already monitored agents
  # We fetch local agents via client to filter
  monitored = client.list_agents()
  monitored_ids = {
      (a.config.project_id, a.config.location, a.config.agent_resource_id)
      for a in monitored
      if a.config
  }

  # Discovered agents are AgentBase objects (or compatible)
  # convert discovered to list to filter
  new_agents = []
  for a in discovered:
    # Ensure config exists and check duplication
    if not a.config:
      continue
    if (
        a.config.project_id,
        a.config.location,
        a.config.agent_resource_id,
    ) not in monitored_ids:
      new_agents.append(a)

  if not new_agents:
    return (
        dmc.Alert(
            "No new agents found. All agents in this location are already"
            " monitored.",
            color="yellow",
        ),
        [],
    )

  # Serialize to store
  store_data = [a.model_dump() for a in new_agents]

  # Render Table
  rows = []
  for idx, a in enumerate(new_agents):
    instruction = a.config.system_instruction or "N/A"

    # Determine Datasource Icon and Label using Pydantic model dump or object
    ds_icon = "bi:question-circle"
    ds_label = "Unknown"

    # Check datasource safely
    if a.config.datasource:
      ds_dump = (
          a.config.datasource.model_dump()
          if hasattr(a.config.datasource, "model_dump")
          else a.config.datasource
      )
      if isinstance(ds_dump, dict):
        if "tables" in ds_dump:
          ds_icon = "bi:database"
          ds_label = "BigQuery"
        elif "instance_uri" in ds_dump:
          ds_icon = "bi:bar-chart-line"
          ds_label = "Looker"

    rows.append(
        html.Tr([
            html.Td(
                dmc.Text(a.name, fw=500, size="sm"),
                style={"padding": "16px 24px"},
            ),
            html.Td(
                dmc.Group(
                    gap="xs",
                    children=[
                        DashIconify(icon=ds_icon, width=18, color="gray"),
                        dmc.Text(ds_label, size="sm"),
                    ],
                ),
                style={"padding": "16px 24px"},
            ),
            html.Td(
                dmc.Text(
                    instruction,
                    size="sm",
                    c="dimmed",
                    style={
                        "display": "-webkit-box",
                        "-webkit-line-clamp": "3",
                        "-webkit-box-orient": "vertical",
                        "overflow": "hidden",
                    },
                ),
                style={"padding": "16px 24px"},
            ),
            html.Td(
                dmc.Button(
                    "Monitor",
                    id=agent_monitor_btn_add_id(str(idx)),
                    leftSection=DashIconify(icon="bi:plus", width=16),
                    size="xs",
                    variant="outline",
                    radius="md",
                ),
                style={"textAlign": "right", "padding": "16px 24px"},
            ),
        ])
    )

  table_head = html.Thead(
      html.Tr(
          [
              html.Th(
                  dmc.Text("DISPLAY NAME", size="xs", fw=700, c="dimmed"),
                  style={"padding": "16px 24px", "textAlign": "left"},
              ),
              html.Th(
                  dmc.Text("DATASOURCE", size="xs", fw=700, c="dimmed"),
                  style={"padding": "16px 24px", "textAlign": "left"},
              ),
              html.Th(
                  dmc.Text("SYSTEM INSTRUCTION", size="xs", fw=700, c="dimmed"),
                  style={"padding": "16px 24px", "textAlign": "left"},
              ),
              html.Th(
                  dmc.Text("ACTION", size="xs", fw=700, c="dimmed"),
                  style={"padding": "16px 24px", "textAlign": "right"},
              ),
          ],
          style={
              "backgroundColor": "var(--mantine-color-gray-0)",
              "borderBottom": "1px solid var(--mantine-color-gray-2)",
          },
      )
  )

  table = dmc.Table(
      children=[table_head, html.Tbody(rows)],
      verticalSpacing=0,
      horizontalSpacing=0,
      highlightOnHover=True,
      withTableBorder=False,
  )

  return table, store_data


@typed_callback(
    [
        Output("redirect-handler", CP.PATHNAME),
        Output(
            {"type": "agent-monitor-btn-add", "index": dash.ALL}, CP.LOADING
        ),
    ],
    [Input({"type": "agent-monitor-btn-add", "index": dash.ALL}, CP.N_CLICKS)],
    allow_duplicate=True,
    state=[
        State("discovered-agents-store", "data"),
    ],
    prevent_initial_call=True,
)
def monitor_selected_agent(
    n_clicks_list,
    discovered_data,
):
  """Handles selection of a GCP agent to monitor."""
  if not any(n_clicks_list):
    return dash.no_update, [False] * len(n_clicks_list)

  ctx = dash.callback_context
  if not ctx.triggered:
    return dash.no_update, [False] * len(n_clicks_list)

  # Extract triggered ID index
  triggered_prop = ctx.triggered[0]["prop_id"]
  if "agent-monitor-btn-add" not in triggered_prop:
    return dash.no_update, [False] * len(n_clicks_list)

  try:
    triggered_id = json.loads(triggered_prop.split(".")[0])
    idx = int(triggered_id["index"])
    logger.info("Selected agent at index %d for monitoring", idx)
  except (ValueError, KeyError, json.JSONDecodeError) as e:
    logger.error("Failed to parse triggered ID: %s", e)
    return dash.no_update, [False] * len(n_clicks_list)

  if not discovered_data or idx >= len(discovered_data):
    return dash.no_update, [False] * len(n_clicks_list)

  selected_raw = discovered_data[idx]
  # We need to reconstruct the schema to pass to client
  # AgentsClient expects AgentConfig, but selected_raw is AgentBase dict
  # We should extract name and config from it

  try:
    selected = AgentBase.model_validate(selected_raw)

    client = get_client().agents
    agent = client.onboard_gcp_agent(name=selected.name, config=selected.config)

    logger.info(
        "Successfully monitored agent: %s (ID: %d)", selected.name, agent.id
    )

    return f"/agents/view/{agent.id}", [False] * len(n_clicks_list)
  except Exception as e:  # pylint: disable=broad-exception-caught
    logger.exception("Failed to monitor agent: %s", e)
    return dash.no_update, [False] * len(n_clicks_list)


dash.clientside_callback(
    """
    function(n_clicks_list) {
        const triggered = dash_clientside.callback_context.triggered;
        if (!triggered || triggered.length === 0) return dash_clientside.no_update;
        
        const prop_id = triggered[0].prop_id;
        if (!prop_id.includes('n_clicks')) return dash_clientside.no_update;
        
        const triggered_id = JSON.parse(prop_id.split('.')[0]);
        const triggered_idx = triggered_id.index;
        
        return n_clicks_list.map((clicks, idx) => {
            return idx == triggered_idx && (clicks || 0) > 0;
        });
    }
    """,
    dash.Output(
        {"type": "agent-monitor-btn-add", "index": dash.ALL},
        CP.LOADING,
        allow_duplicate=True,
    ),
    Input({"type": "agent-monitor-btn-add", "index": dash.ALL}, CP.N_CLICKS),
    prevent_initial_call=True,
)
