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

"""Callbacks for Agent Detail Page."""

import logging
import time
from typing import Any
import dash
from dash import html
from dash import Input
from dash import Output
from dash import State
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.client import get_client
from prism.common.schemas import agent as agent_schemas
from prism.ui.components import eval_run_modal
from prism.ui.components.cards import render_detail_card
from prism.ui.components.dashboard_components import get_suite_color
from prism.ui.components.dashboard_components import render_duration_chart
from prism.ui.components.dashboard_components import render_empty_evaluations_placeholder
from prism.ui.components.dashboard_components import render_evaluation_chart
from prism.ui.components.dashboard_components import render_recent_evals_table
from prism.ui.constants import CP
from prism.ui.constants import REDIRECT_HANDLER
from prism.ui.pages.agent_ids import AgentIds
from prism.ui.utils import is_valid_bq_table
from prism.ui.utils import is_valid_looker_explore
from prism.ui.utils import parse_textarea_list
from prism.ui.utils import typed_callback


@typed_callback(
    [
        Output(AgentIds.Detail.CONTENT, CP.CHILDREN),
        Output("agent-detail-loading", "visible"),
        Output(AgentIds.Detail.TITLE, CP.CHILDREN),
        Output(AgentIds.Detail.DESCRIPTION, CP.CHILDREN),
        Output(AgentIds.Detail.ACTIONS, CP.CHILDREN),
        Output(AgentIds.Detail.STORE_REMOTE_TRIGGER, CP.DATA),
    ],
    [
        Input("url", CP.PATHNAME),
        Input(AgentIds.Detail.STORE_REFRESH_TRIGGER, CP.DATA),
    ],
)
def update_agent_details(pathname: str, refresh_trigger: Any):
  """Updates agent details (Local Data Only) & Triggers Remote Fetch."""
  del refresh_trigger  # Used only as a trigger
  if not pathname or not pathname.startswith("/agents/view/"):
    return (dash.no_update,) * 5 + (dash.no_update,)

  try:
    agent_id = int(pathname.split("/")[-1])
  except (ValueError, IndexError):
    return (dash.no_update,) * 5 + (dash.no_update,)

  client = get_client()
  agent = client.agents.get_agent(agent_id)

  if not agent:
    return (
        dmc.Alert(f"Agent {agent_id} not found.", color="red"),
        False,
        dash.no_update,
        dash.no_update,
        dash.no_update,
        dash.no_update,
    )

  # 1. Fetch Data
  # Dashboard Stats
  try:
    stats = client.runs.get_agent_dashboard_stats(agent_id, days=30)
  except Exception as e:  # pylint: disable=broad-except
    logging.error("Failed to fetch dashboard stats: %s", e)
    stats = {}

  # GCP Details OMITTED in first pass (Loaded async)
  # We only render the skeleton UI for these sections initially.

  # 2. Render Components

  # --- Unified Header Card ---
  def _meta_item(label, value, icon=None, color="blue", mono=False):
    del icon, color  # Icons and color badges removed per user request

    return dmc.Stack(
        gap=4,
        children=[
            dmc.Text(
                label,
                size="xs",
                c="dimmed",
                tt="uppercase",
                fw=700,
                lts=0.5,  # tracking-wider
            ),
            dmc.Group(
                gap=6,
                children=[
                    dmc.Text(
                        value,
                        size="sm",
                        fw=500,
                        className="font-mono" if mono else "",
                    ),
                ],
            ),
        ],
    )

  last_updated_str = (
      agent.modified_at.strftime("%Y-%m-%d %H:%M")
      if agent.modified_at
      else "N/A"
  )

  unified_header_card = dmc.Paper(
      withBorder=True,
      radius="md",  # rounded-xl
      p="lg",
      shadow="sm",
      children=[
          # Metadata Grid
          dmc.SimpleGrid(
              cols={"base": 1, "md": 3},
              spacing="md",
              children=[
                  _meta_item(
                      "GCP Parent Project",
                      agent.config.project_id if agent.config else "N/A",
                      mono=True,
                  ),
                  _meta_item(
                      "GCP Location",
                      agent.config.location if agent.config else "N/A",
                  ),
                  _meta_item(
                      "GDA Resource ID",
                      (
                          agent.config.agent_resource_id
                          if agent.config
                          else "N/A"
                      ),
                      mono=True,
                  ),
              ],
          ),
      ],
  )

  # --- Header Actions ---
  header_actions = [
      dmc.Button(
          "Duplicate Agent",
          id=AgentIds.Detail.BTN_DUPLICATE,
          variant="default",
          radius="md",
          leftSection=DashIconify(
              icon="material-symbols:content-copy", width=20
          ),
          disabled=True,
      ),
      dmc.Button(
          "Edit Agent",
          id=AgentIds.Detail.BTN_EDIT,
          variant="default",
          radius="md",
          leftSection=DashIconify(icon="material-symbols:edit", width=20),
          disabled=True,
      ),
      dmc.Button(
          "Run Evaluation",
          id=AgentIds.Detail.BTN_RUN_EVAL,
          variant="filled",
          color="blue",
          radius="md",
          fw=600,
          leftSection=DashIconify(icon="bi:play-fill", width=20),
          disabled=True,
      ),
  ]

  description = [
      "Last updated ",
      html.Span(
          last_updated_str,
          style={"fontWeight": 500},
          className="text-dark",
      ),
  ]

  # --- Main Content Grid (Instruction + Datasource) ---
  # Prepare Datasource Card (Skeleton Initially)
  datasource_skeleton = render_detail_card(
      title="Datasource",
      description="Configuration for data retrieval",
      action=html.Div(
          id=AgentIds.Detail.BADGE_DATASOURCE,
          children=dmc.Skeleton(width=80, height=20, radius="md"),
      ),
      children=dmc.Stack(
          id=AgentIds.Detail.CONTAINER_DATASOURCE,
          children=[
              dmc.Skeleton(height=20, width="40%", mb=10),
              dmc.Skeleton(height=30, width="100%", mb=10),
              dmc.Skeleton(height=20, width="40%", mb=10),
              dmc.Skeleton(height=30, width="100%", mb=10),
          ],
      ),
  )

  main_grid = dmc.SimpleGrid(
      cols={"base": 1, "md": 2},
      spacing="md",
      children=[
          render_detail_card(
              title="System Instruction",
              description="The set of instructions sent to the LLM",
              children=dmc.ScrollArea(
                  mah=300,
                  children=html.Div(
                      id=AgentIds.Detail.INSTRUCTION,
                      children=dmc.Skeleton(
                          visible=True,
                          height=150,
                          radius="md",
                      ),
                  ),
              ),
          ),
          datasource_skeleton,
      ],
  )

  # --- Credential Warning (if Looker and missing) ---
  credential_warning = None
  if agent.config and isinstance(
      agent.config.datasource, agent_schemas.LookerConfig
  ):
    if (
        not agent.config.looker_client_id
        or not agent.config.looker_client_secret
    ):
      credential_warning = dmc.Alert(
          "Looker credentials (Client ID and Secret) are missing. Evaluations"
          " will be disabled until they are provided in the Edit Agent modal.",
          title="Missing Credentials",
          color="red",
          radius="md",
          icon=DashIconify(icon="material-symbols:warning-rounded"),
          mb="lg",
      )

  # Decide what analytics/table to show
  recent_evals = stats.get("recent_evals", [])
  if not recent_evals:
    evaluation_section = [render_empty_evaluations_placeholder()]
  else:
    evaluation_section = [
        # Row 1: Analytics Charts
        dmc.SimpleGrid(
            cols={"base": 1, "lg": 2},
            spacing="lg",
            children=[
                render_evaluation_chart(
                    stats.get("daily_accuracy", []),
                    suites=stats.get("suites"),
                    dropdown_id=AgentIds.Detail.SELECT_EVAL_ACCURACY_DAYS,
                    container_id=AgentIds.Detail.CHART_EVAL_ACCURACY_ROOT,
                    selected_days="Last 30 Days",
                ),
                render_duration_chart(
                    stats.get("daily_duration", []),
                    suites=stats.get("suites"),
                    dropdown_id=AgentIds.Detail.SELECT_DURATION_DAYS,
                    container_id=AgentIds.Detail.CHART_DURATION_ROOT,
                ),
            ],
        ),
        # Row 2: Full-width Table
        html.Div(
            render_recent_evals_table(recent_evals, agent_id=agent_id),
            style={"width": "100%"},
        ),
    ]

  # Assemble Layout
  content = dmc.Stack(
      gap="xl",
      children=[
          credential_warning,
          unified_header_card,
          main_grid,
          *evaluation_section,
          eval_run_modal.render_modal(),
      ],
  )

  return (
      content,
      False,
      agent.name,
      description,
      header_actions,
      {"agent_id": agent_id, "ts": time.time()},  # Trigger remote fetch
  )


@typed_callback(
    Output(AgentIds.Detail.CHART_EVAL_ACCURACY_ROOT, CP.CHILDREN),
    [
        Input(AgentIds.Detail.SELECT_EVAL_ACCURACY_DAYS, CP.VALUE),
        Input("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
)
def update_accuracy_chart(days_str: str, pathname: str):
  """Updates the accuracy chart based on selected time range."""
  if not pathname or not pathname.startswith("/agents/view/"):
    return dash.no_update

  try:
    agent_id = int(pathname.split("/")[-1])
  except (ValueError, IndexError):
    return dash.no_update

  days = 30 if "30" in days_str else 7
  client = get_client()

  try:
    stats = client.runs.get_agent_dashboard_stats(agent_id, days=days)
  except Exception as e:  # pylint: disable=broad-except
    logging.error("Failed to fetch accuracy stats: %s", e)
    return dmc.Text("Error loading data", c="red")

  # We only need the chart part, but render_evaluation_chart returns the whole
  # Paper.
  # Or just return the AreaChart directly here.
  # Let's look at dashboard_components.py again.
  # Actually, it's easier to just return the AreaChart content.
  processed_data = []
  daily_accuracy = stats.get("daily_accuracy", [])
  if daily_accuracy:
    for item in daily_accuracy:
      new_item = item.copy()
      for k, v in new_item.items():
        if k != "date" and isinstance(v, (int, float)):
          new_item[k] = round(v * 100, 1)
      processed_data.append(new_item)

  suites = stats.get("suites")
  series = []
  if suites:
    sorted_suites = sorted(suites)
    for i, ds in enumerate(sorted_suites):
      series.append({
          "name": ds,
          "color": get_suite_color(ds, i),
          "label": ds,
      })
  else:
    series = [{"name": "accuracy", "color": "violet.6", "label": "Accuracy"}]

  return dmc.AreaChart(
      h=300,
      data=processed_data,
      dataKey="date",
      series=series,
      curveType="monotone",
      tickLine="xy",
      gridAxis="xy",
      withGradient=True,
      withDots=True,
      withLegend=bool(suites),
      unit="%",
      areaProps={
          "isAnimationActive": True,
          "animationDuration": 1000,
          "animationEasing": "ease-in-out",
      },
  )


@typed_callback(
    Output(AgentIds.Detail.CHART_DURATION_ROOT, CP.CHILDREN),
    [
        Input(AgentIds.Detail.SELECT_DURATION_DAYS, CP.VALUE),
        Input("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
)
def update_duration_chart(days_str: str, pathname: str):
  """Updates the duration chart based on selected time range."""
  if not pathname or not pathname.startswith("/agents/view/"):
    return dash.no_update

  try:
    agent_id = int(pathname.split("/")[-1])
  except (ValueError, IndexError):
    return dash.no_update

  days = 30 if "30" in days_str else 7
  client = get_client()

  try:
    stats = client.runs.get_agent_dashboard_stats(agent_id, days=days)
  except Exception as e:  # pylint: disable=broad-except
    logging.error("Failed to fetch duration stats: %s", e)
    return dmc.Text("Error loading data", c="red")

  daily_duration = stats.get("daily_duration", [])
  suites = stats.get("suites")

  series = []
  if suites:
    sorted_suites = sorted(suites)
    for i, ds in enumerate(sorted_suites):
      series.append({
          "name": ds,
          "color": get_suite_color(ds, i),
          "label": ds,
      })
  else:
    series = [{"name": "duration", "color": "teal.6", "label": "Duration (ms)"}]

  return dmc.AreaChart(
      h=300,
      data=daily_duration,
      dataKey="date",
      series=series,
      curveType="monotone",
      tickLine="xy",
      gridAxis="xy",
      withGradient=True,
      withDots=True,
      withLegend=bool(suites),
      unit="ms",
      areaProps={
          "isAnimationActive": True,
          "animationDuration": 1000,
          "animationEasing": "ease-in-out",
      },
  )


@typed_callback(
    [
        Output(AgentIds.Detail.INSTRUCTION, CP.CHILDREN),
        Output(AgentIds.Detail.CONTAINER_DATASOURCE, CP.CHILDREN),
        Output(AgentIds.Detail.BADGE_DATASOURCE, CP.CHILDREN),
        Output(AgentIds.Detail.STORE_GCP_CONFIG, CP.DATA),
        Output(AgentIds.Detail.BTN_EDIT, CP.DISABLED),
        Output(AgentIds.Detail.BTN_DUPLICATE, CP.DISABLED),
        Output(AgentIds.Detail.BTN_RUN_EVAL, CP.DISABLED),
    ],
    [Input(AgentIds.Detail.STORE_REMOTE_TRIGGER, CP.DATA)],
    prevent_initial_call=True,
)
def fetch_remote_config(trigger_data):
  """Fetches remote GDA config and updates UI."""
  if not trigger_data:
    return (
        dash.no_update,
        dash.no_update,
        dash.no_update,
        dash.no_update,
        dash.no_update,
        dash.no_update,
        dash.no_update,
    )

  if isinstance(trigger_data, dict):
    agent_id = trigger_data.get("agent_id")
  else:
    agent_id = trigger_data

  client = get_client().agents
  try:
    gcp_agent = client.get_gcp_agent_details(agent_id)
  except Exception as e:  # pylint: disable=broad-except
    logging.error("Failed to fetch GCP details: %s", e)
    return (
        dmc.Alert(f"Failed to load remote config: {e}", color="red"),
        dmc.Alert("Failed to load.", color="red"),
        dash.no_update,
        dash.no_update,
        False,  # Re-enable edit button
        False,  # Re-enable duplicate button
        dash.no_update,
    )

  if not gcp_agent:
    return (
        "Error: Agent not found on GCP.",
        "Error: Configuration unavailable.",
        dash.no_update,
        dash.no_update,
        False,  # Re-enable edit button
        False,  # Re-enable duplicate button
        dash.no_update,
    )

  # 1. System Instruction
  instruction = gcp_agent.config.system_instruction or "No instruction."
  instruction_ui = dmc.Text(
      instruction,
      size="sm",
      c="dark",
      style={"whiteSpace": "pre-wrap"},
  )

  # 2. Datasource
  datasource = gcp_agent.config.datasource
  ds_type = None
  ds_children = []

  if datasource is None:
    ds_type = "None"
    ds_children = [
        dmc.Text("No datasource configured on GCP.", size="sm", c="dimmed")
    ]
  elif isinstance(datasource, agent_schemas.LookerConfig):
    ds_type = "Looker"
    instance_uri = datasource.instance_uri
    explores = datasource.explores or []

    # Instance URI
    if instance_uri:
      instance_uri_ui = dmc.Code(
          instance_uri,
          block=False,
          style={"display": "inline-block"},
      )
    else:
      instance_uri_ui = dmc.Text("-", size="sm", c="dimmed")

    ds_children.append(
        dmc.Stack(
            gap=4,
            align="flex-start",
            children=[
                dmc.Text("Looker Instance URI", size="xs", c="dimmed"),
                instance_uri_ui,
            ],
            mb="sm",
        )
    )

    # Explores
    explore_children = [dmc.Text("Looker Explores", size="xs", c="dimmed")]
    for explore in explores:
      explore_children.append(
          dmc.Code(
              explore,
              block=False,
              style={"display": "inline-block"},
          )
      )
    ds_children.append(
        dmc.Stack(gap=4, align="flex-start", children=explore_children)
    )

  elif isinstance(datasource, agent_schemas.BigQueryConfig):
    ds_type = "BQ"
    tables = datasource.tables or []

    # Tables
    table_children = [dmc.Text("Tables", size="xs", c="dimmed")]
    for table in tables:
      table_children.append(
          dmc.Code(
              table,
              block=False,
              style={"display": "inline-block"},
          )
      )
    ds_children.append(
        dmc.Stack(gap=4, align="flex-start", children=table_children)
    )

  # Badge Logic
  ds_colors = {"Looker": "blue", "BQ": "orange"}
  badge = dmc.Badge(
      ds_type,
      color=ds_colors.get(ds_type, "gray"),
      variant="light",
  )

  # Decide if we can enable Run Eval button
  can_run_eval = ds_type != "Looker" or (
      bool(gcp_agent.config.looker_client_id)
      and bool(gcp_agent.config.looker_client_secret)
  )

  return (
      instruction_ui,
      dmc.Stack(children=ds_children),
      badge,
      gcp_agent.config.model_dump(),
      False,  # Re-enable edit button
      False,  # Re-enable duplicate button
      not can_run_eval,  # BTN_RUN_EVAL disabled if missing creds
  )


@typed_callback(
    [
        Output(AgentIds.Detail.MODAL_EDIT, "opened"),
        Output(AgentIds.Detail.INPUT_EDIT_NAME, CP.VALUE),
        Output(AgentIds.Detail.TEXTAREA_EDIT_INSTRUCTION, CP.VALUE),
        # Looker Visibility
        Output(AgentIds.Detail.CONTAINER_EDIT_LOOKER_CONFIG, "style"),
        # Looker Values
        Output(AgentIds.Detail.INPUT_EDIT_LOOKER_URI, CP.VALUE),
        Output(AgentIds.Detail.INPUT_EDIT_LOOKER_EXPLORES, CP.VALUE),
        Output(AgentIds.Detail.INPUT_EDIT_LOOKER_CLIENT_ID, CP.VALUE),
        Output(AgentIds.Detail.INPUT_EDIT_LOOKER_CLIENT_SECRET, CP.VALUE),
        # BQ Visibility
        Output(AgentIds.Detail.CONTAINER_EDIT_BQ_CONFIG, "style"),
        # BQ Values
        Output(AgentIds.Detail.INPUT_EDIT_BQ_TABLES, CP.VALUE),
    ],
    [
        Input(AgentIds.Detail.BTN_EDIT, CP.N_CLICKS),
    ],
    [
        State(AgentIds.Detail.STORE_GCP_CONFIG, CP.DATA),
        State("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
)
def open_edit_modal(n_clicks, gcp_config, pathname):
  """Opens the edit modal and pre-fills values."""
  if not n_clicks:
    return (dash.no_update,) * 10

  current_name = ""
  instruction = ""

  is_looker = False
  looker_uri = ""
  looker_explores = []
  looker_client_id = ""
  looker_client_secret = ""

  is_bq = False
  bq_tables = []

  # Fetch Agent Name from DB (Reliable Source)
  try:
    agent_id = int(pathname.split("/")[-1])
    client = get_client().agents
    agent = client.get_agent(agent_id)
    if agent:
      current_name = agent.name

      if agent.config:
        # Check DB credentials from config if Looker
        if agent.config.datasource and isinstance(
            agent.config.datasource, agent_schemas.LookerConfig
        ):
          is_looker = True
          looker_uri = agent.config.datasource.instance_uri
          looker_explores = agent.config.datasource.explores or []
          looker_client_id = agent.config.looker_client_id or ""
          looker_client_secret = agent.config.looker_client_secret or ""

        # Check for BQ
        if agent.config.datasource and isinstance(
            agent.config.datasource, agent_schemas.BigQueryConfig
        ):
          is_bq = True
          bq_tables = agent.config.datasource.tables or []

        # The Pydantic Agent schema used in the UI uses agent.config.datasource.
        if agent.config.datasource and isinstance(
            agent.config.datasource, agent_schemas.LookerConfig
        ):
          is_looker = True
          looker_uri = agent.config.datasource.instance_uri
          looker_explores = agent.config.datasource.explores or []
          looker_client_id = agent.config.looker_client_id or ""
          looker_client_secret = agent.config.looker_client_secret or ""

        # Check for BQ
        if agent.config.datasource and isinstance(
            agent.config.datasource, agent_schemas.BigQueryConfig
        ):
          is_bq = True
          bq_tables = agent.config.datasource.tables or []

        # Check if Looker type
        if isinstance(agent.config.datasource, agent_schemas.LookerConfig):
          is_looker = True

  except Exception:  # pylint: disable=broad-except
    pass

  if gcp_config:
    instruction = gcp_config.get("system_instruction") or ""
    # Check if Looker via GCP config
    datasource = gcp_config.get("datasource")
    if datasource:
      # Check if type Looker
      if "instance_uri" in datasource or "looker_instance_uri" in datasource:
        is_looker = True

  looker_style = {"display": "none"}
  if is_looker:
    looker_style = {"display": "block"}

  bq_style = {"display": "none"}
  if is_bq:
    bq_style = {"display": "block"}

  return (
      True,
      current_name,
      instruction,
      looker_style,
      looker_uri,
      "\n".join(looker_explores),
      looker_client_id,
      looker_client_secret,
      bq_style,
      "\n".join(bq_tables),
  )


@typed_callback(
    [
        Output(AgentIds.Detail.MODAL_EDIT, "opened", allow_duplicate=True),
        Output(AgentIds.Detail.EDIT_LOADING_OVERLAY, "visible"),
        Output(REDIRECT_HANDLER, CP.HREF, allow_duplicate=True),
        Output(
            "notification-container", "sendNotifications", allow_duplicate=True
        ),
        Output(AgentIds.Detail.STORE_REFRESH_TRIGGER, CP.DATA),
    ],
    [
        Input(AgentIds.Detail.BTN_EDIT_SUBMIT, CP.N_CLICKS),
    ],
    [
        State("url", CP.PATHNAME),
        State(AgentIds.Detail.INPUT_EDIT_NAME, CP.VALUE),
        State(AgentIds.Detail.TEXTAREA_EDIT_INSTRUCTION, CP.VALUE),
        State(AgentIds.Detail.INPUT_EDIT_LOOKER_URI, CP.VALUE),
        State(AgentIds.Detail.INPUT_EDIT_LOOKER_EXPLORES, CP.VALUE),
        State(AgentIds.Detail.INPUT_EDIT_LOOKER_CLIENT_ID, CP.VALUE),
        State(AgentIds.Detail.INPUT_EDIT_LOOKER_CLIENT_SECRET, CP.VALUE),
        State(AgentIds.Detail.INPUT_EDIT_BQ_TABLES, CP.VALUE),
    ],
    prevent_initial_call=True,
)
def submit_edit(
    n_clicks,
    pathname,
    new_name,
    new_instruction,
    looker_uri,
    looker_explores_raw,
    looker_client_id,
    looker_client_secret,
    bq_tables_raw,
):
  """Submits the edit form."""
  if not n_clicks:
    return (
        dash.no_update,
        dash.no_update,
        dash.no_update,
        dash.no_update,
        dash.no_update,
    )

  looker_explores = parse_textarea_list(looker_explores_raw)
  bq_tables = parse_textarea_list(bq_tables_raw)

  # Validation
  invalid_fields = []
  try:
    agent_id = int(pathname.split("/")[-1])
    client_agents = get_client().agents
    agent = client_agents.get_agent(agent_id)
    if agent and agent.config:
      if isinstance(agent.config.datasource, agent_schemas.LookerConfig):
        for e in looker_explores:
          if not is_valid_looker_explore(e):
            invalid_fields.append(f"Invalid Looker Explore: {e}")
      elif isinstance(agent.config.datasource, agent_schemas.BigQueryConfig):
        for t in bq_tables:
          if not is_valid_bq_table(t):
            invalid_fields.append(f"Invalid BQ Table: {t}")
  except (ValueError, IndexError):
    return False, False, dash.no_update, dash.no_update

  if invalid_fields:
    return (
        dash.no_update,
        False,
        dash.no_update,
        [{
            "action": "show",
            "title": "Validation Error",
            "message": f"Invalid format: {', '.join(invalid_fields)}",
            "color": "red",
            "autoClose": 5000,
        }],
        dash.no_update,
    )

  client = get_client().agents
  try:
    # Fetch current agent to preserve unrelated config fields
    agent = client.get_agent(agent_id)
    if agent and agent.config:
      new_config = agent.config.model_copy()
      new_config.system_instruction = new_instruction

      # Update Datasource based on what was there
      if isinstance(agent.config.datasource, agent_schemas.BigQueryConfig):
        new_config.datasource = agent_schemas.BigQueryConfig(tables=bq_tables)
      elif isinstance(agent.config.datasource, agent_schemas.LookerConfig):
        new_config.datasource = agent_schemas.LookerConfig(
            instance_uri=looker_uri, explores=looker_explores
        )
        new_config.looker_client_id = looker_client_id
        new_config.looker_client_secret = looker_client_secret
    else:
      # Fallback (should not happen for valid agent)
      # If fallback, we don't know the type, so we can't easily set datasource.
      # But update_agent usually happens for existing agents.
      new_config = agent_schemas.AgentConfig(
          system_instruction=new_instruction,
      )

    # Validation for Looker
    if isinstance(new_config.datasource, agent_schemas.LookerConfig):
      if not looker_client_id or not looker_client_secret:
        return (
            True,
            False,
            dash.no_update,
            [{
                "action": "show",
                "title": "Missing Looker Credentials",
                "message": (
                    "Client ID and Secret are required for Looker agents."
                ),
                "color": "red",
            }],
            dash.no_update,
        )

    client.update_agent(
        agent_id=agent_id,
        name=new_name,
        config=new_config,
    )
    return (
        False,
        False,
        dash.no_update,
        [{
            "action": "show",
            "title": "Success",
            "message": "Agent updated successfully!",
            "color": "green",
        }],
        time.time(),
    )
  except Exception as e:  # pylint: disable=broad-except
    logging.error("Failed to update agent: %s", e)
    return (
        True,
        False,
        dash.no_update,
        [{
            "action": "show",
            "title": "Update Error",
            "message": f"Failed to update agent: {str(e)}",
            "color": "red",
        }],
        dash.no_update,
    )


@typed_callback(
    [
        Output(AgentIds.Detail.INPUT_EDIT_BQ_TABLES_PREVIEW, CP.CHILDREN),
        Output(AgentIds.Detail.INPUT_EDIT_BQ_TABLES, "error"),
    ],
    [Input(AgentIds.Detail.INPUT_EDIT_BQ_TABLES, CP.VALUE)],
)
def validate_bq_tables_edit(value: str | None):
  """Validates and previews BQ table paths in edit modal."""
  tables = parse_textarea_list(value)
  if not tables:
    return [], False

  badges = []
  errors = []
  for t in tables:
    if is_valid_bq_table(t):
      badges.append(
          dmc.Badge(t, color="blue", variant="light", size="sm", tt="none")
      )
    else:
      badges.append(
          dmc.Badge(t, color="red", variant="light", size="sm", tt="none")
      )
      errors.append(f"Invalid format: {t}")

  error_msg = f"Invalid BQ paths: {', '.join(errors)}" if errors else False
  return badges, error_msg


@typed_callback(
    [
        Output(AgentIds.Detail.INPUT_EDIT_LOOKER_EXPLORES_PREVIEW, CP.CHILDREN),
        Output(AgentIds.Detail.INPUT_EDIT_LOOKER_EXPLORES, "error"),
    ],
    [Input(AgentIds.Detail.INPUT_EDIT_LOOKER_EXPLORES, CP.VALUE)],
)
def validate_looker_explores_edit(value: str | None):
  """Validates and previews Looker explore paths in edit modal."""
  explores = parse_textarea_list(value)
  if not explores:
    return [], False

  badges = []
  errors = []
  for e in explores:
    if is_valid_looker_explore(e):
      badges.append(
          dmc.Badge(e, color="blue", variant="light", size="sm", tt="none")
      )
    else:
      badges.append(
          dmc.Badge(e, color="red", variant="light", size="sm", tt="none")
      )
      errors.append(f"Invalid format: {e}")

  error_msg = f"Invalid Looker paths: {', '.join(errors)}" if errors else False
  return badges, error_msg


dash.clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks > 0) {
            return true;
        }
        return dash_clientside.no_update;
    }
    """,
    Output(
        AgentIds.Detail.EDIT_LOADING_OVERLAY, "visible", allow_duplicate=True
    ),
    Input(AgentIds.Detail.BTN_EDIT_SUBMIT, CP.N_CLICKS),
    prevent_initial_call=True,
)


@typed_callback(
    [
        Output(AgentIds.Detail.EvalModal.ROOT, "opened"),
        Output(AgentIds.Detail.EvalModal.SELECT_SUITE, "data"),
        Output(AgentIds.Detail.EvalModal.ALERT_VALIDATION, CP.CHILDREN),
        Output(AgentIds.Detail.EvalModal.SELECT_SUITE, CP.VALUE),
    ],
    [
        Input(AgentIds.Detail.BTN_RUN_EVAL, CP.N_CLICKS),
        Input(
            {"type": "agent-detail-btn-run-eval", "index": dash.ALL},
            CP.N_CLICKS,
        ),
    ],
    [State("url", CP.PATHNAME)],
    prevent_initial_call=True,
)
def open_eval_modal(n_clicks, n_clicks_list, pathname):
  """Opens the evaluation modal and populates compatible test suites."""

  if not n_clicks and not any(n_clicks_list or []):
    return dash.no_update, dash.no_update, dash.no_update, dash.no_update

  try:
    agent_id = int(pathname.split("/")[-1])
  except (ValueError, IndexError):
    return dash.no_update, dash.no_update, dash.no_update, dash.no_update

  client = get_client()
  agent = client.agents.get_agent(agent_id)
  if not agent:
    return dash.no_update, dash.no_update, dash.no_update, dash.no_update

  # Check credentials if Looker
  # Note: Client schema does not expose secrets, so we cannot strictly verify
  # presence of client_id/secret here. We rely on backend validation or
  # trust the user has configured it.

  alert = None
  # We cannot check for missing credentials on the client side
  # securely/easily yet without exposing them in the schema.

  # List all suites
  suites = client.suites.list_suites()

  options = [{"label": s.name, "value": str(s.id)} for s in suites]

  return True, options, alert, None


@typed_callback(
    [
        Output(AgentIds.Detail.EvalModal.SUITE_DETAILS, CP.CHILDREN),
        Output(AgentIds.Detail.EvalModal.BTN_START, CP.DISABLED),
    ],
    [Input(AgentIds.Detail.EvalModal.SELECT_SUITE, CP.VALUE)],
    [State("url", CP.PATHNAME)],
    prevent_initial_call=True,
)
def handle_suite_selection(suite_id, pathname):
  """Shows details for the selected test suite and validates start button."""
  if not suite_id:
    return (
        dmc.Alert(
            "Select a test suite to view details.",
            color="blue",
            variant="light",
        ),
        True,
    )

  try:
    s_id = int(suite_id)
    agent_id = int(pathname.split("/")[-1])
  except (ValueError, IndexError):
    return dash.no_update, True

  client = get_client()
  suite = client.suites.get_suite(s_id)
  if not suite:
    return (
        dmc.Alert("Test Suite not found.", color="red", variant="light"),
        True,
    )

  # Validate Agent Credentials again to decide if we can enable the button
  agent = client.agents.get_agent(agent_id)
  if not agent:
    return dash.no_update, True

  # We enable the button if agent exists and has creds if Looker.
  can_start = True
  if agent.config and isinstance(
      agent.config.datasource, agent_schemas.LookerConfig
  ):
    if (
        not agent.config.looker_client_id
        or not agent.config.looker_client_secret
    ):
      can_start = False

  return eval_run_modal.render_suite_card(suite), not can_start


@typed_callback(
    [
        Output(REDIRECT_HANDLER, CP.HREF, allow_duplicate=True),
        Output(
            "notification-container", "sendNotifications", allow_duplicate=True
        ),
    ],
    [Input(AgentIds.Detail.EvalModal.BTN_START, CP.N_CLICKS)],
    [
        State("url", CP.PATHNAME),
        State(AgentIds.Detail.EvalModal.SELECT_SUITE, CP.VALUE),
    ],
    prevent_initial_call=True,
)
def start_evaluation(n_clicks, pathname, suite_id):
  """Starts a new evaluation run."""
  if not n_clicks or not suite_id:
    return dash.no_update

  try:
    agent_id = int(pathname.split("/")[-1])
    s_id = int(suite_id)
  except (ValueError, IndexError):
    return dash.no_update

  client = get_client()
  agent = client.agents.get_agent(agent_id)

  # Final safety check for credentials
  if (
      agent
      and agent.config
      and isinstance(agent.config.datasource, agent_schemas.LookerConfig)
  ):
    if (
        not agent.config.looker_client_id
        or not agent.config.looker_client_secret
    ):
      return dash.no_update, [{
          "action": "show",
          "title": "Cannot Start Evaluation",
          "message": (
              f"Agent '{agent.name}' is a Looker agent, but it is missing"
              " credentials. Please provide them in the Edit Agent modal"
              " before starting evaluations."
          ),
          "color": "red",
          "icon": DashIconify(icon="material-symbols:error-outline"),
      }]

  try:
    run = client.runs.create_run(agent_id=agent_id, test_suite_id=s_id)
    # Redirect to the new run page
    return f"/evaluations/runs/{run.id}", dash.no_update
  except Exception as e:  # pylint: disable=broad-except
    logging.error("Failed to create run: %s", e)
    return dash.no_update, [{
        "action": "show",
        "title": "Failed to Start Evaluation",
        "message": str(e),
        "color": "red",
    }]


@typed_callback(
    Output(AgentIds.Detail.EvalModal.ROOT, "opened", allow_duplicate=True),
    [
        Input(AgentIds.Detail.EvalModal.BTN_CANCEL, CP.N_CLICKS),
        Input(AgentIds.Detail.EvalModal.BTN_CANCEL + "-x", CP.N_CLICKS),
    ],
    prevent_initial_call=True,
)
def close_eval_modal(cancel1, cancel2):
  """Closes the evaluation modal."""
  del cancel1, cancel2
  return False


@typed_callback(
    [
        Output(AgentIds.Detail.MODAL_DUPLICATE, "opened"),
        Output(AgentIds.Detail.INPUT_DUPLICATE_NAME, CP.VALUE),
    ],
    [Input(AgentIds.Detail.BTN_DUPLICATE, CP.N_CLICKS)],
    [State("url", CP.PATHNAME)],
    prevent_initial_call=True,
)
def open_duplicate_modal(n_clicks, pathname):
  """Opens the duplication modal and pre-fills the name."""
  if not n_clicks:
    return dash.no_update, dash.no_update

  current_name = ""
  try:
    agent_id = int(pathname.split("/")[-1])
    client = get_client()
    agent = client.agents.get_agent(agent_id)
    if agent:
      current_name = agent.name
  except Exception:  # pylint: disable=broad-except
    pass

  return True, f"Copy of {current_name}" if current_name else "Copy of Agent"


@typed_callback(
    [
        Output(AgentIds.Detail.MODAL_DUPLICATE, "opened", allow_duplicate=True),
        Output(AgentIds.Detail.DUPLICATE_LOADING_OVERLAY, "visible"),
        Output(REDIRECT_HANDLER, CP.HREF, allow_duplicate=True),
    ],
    [Input(AgentIds.Detail.BTN_DUPLICATE_SUBMIT, CP.N_CLICKS)],
    [
        State("url", CP.PATHNAME),
        State(AgentIds.Detail.INPUT_DUPLICATE_NAME, CP.VALUE),
    ],
    prevent_initial_call=True,
)
def submit_duplicate(n_clicks, pathname, new_name):
  """Submits the duplication request."""
  if not n_clicks:
    return dash.no_update, dash.no_update, dash.no_update

  try:
    agent_id = int(pathname.split("/")[-1])
  except (ValueError, IndexError):
    return False, False, dash.no_update

  client = get_client()
  try:
    new_agent = client.agents.duplicate_agent(agent_id, new_name)
    return False, False, f"/agents/view/{new_agent.id}"
  except Exception as e:  # pylint: disable=broad-except
    logging.error("Failed to duplicate agent: %s", e)
    return True, False, dash.no_update


dash.clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks > 0) {
            return true;
        }
        return dash_clientside.no_update;
    }
    """,
    Output(
        AgentIds.Detail.DUPLICATE_LOADING_OVERLAY,
        "visible",
        allow_duplicate=True,
    ),
    Input(AgentIds.Detail.BTN_DUPLICATE_SUBMIT, CP.N_CLICKS),
    prevent_initial_call=True,
)


@typed_callback(
    [
        Output(AgentIds.Detail.ALERT_LOOKER_TEST, CP.CHILDREN),
        Output(AgentIds.Detail.ALERT_LOOKER_TEST, CP.HIDE),
        Output(AgentIds.Detail.ALERT_LOOKER_TEST, "color"),
        Output(AgentIds.Detail.BTN_TEST_LOOKER, "loading"),
    ],
    [Input(AgentIds.Detail.BTN_TEST_LOOKER, CP.N_CLICKS)],
    [
        State(AgentIds.Detail.INPUT_EDIT_LOOKER_URI, CP.VALUE),
        State(AgentIds.Detail.INPUT_EDIT_LOOKER_CLIENT_ID, CP.VALUE),
        State(AgentIds.Detail.INPUT_EDIT_LOOKER_CLIENT_SECRET, CP.VALUE),
    ],
    prevent_initial_call=True,
)
def test_looker_connectivity(n_clicks, uri, client_id, client_secret):
  """Tests Looker connectivity."""
  if not n_clicks:
    return dash.no_update, True, "blue", False

  if not all([uri, client_id, client_secret]):
    return (
        "Incomplete credentials. Please provide URI, Client ID, and Secret.",
        False,
        "orange",
        False,
    )

  client = get_client().agents
  try:
    result = client.test_looker_credentials(
        instance_uri=uri, client_id=client_id, client_secret=client_secret
    )
    color = "green" if result["success"] else "red"
    return result.get("message", "Success!"), False, color, False
  except Exception as e:  # pylint: disable=broad-except
    return f"Test failed: {str(e)}", False, "red", False
