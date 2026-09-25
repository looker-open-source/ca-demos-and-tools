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

import json
import logging
import time
from typing import Any
import dash
from dash import dcc
from dash import html
from dash import Input
from dash import Output
from dash import State
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.client import get_client
from prism.common.schemas import agent as agent_schemas
from prism.ui.components import eval_run_modal
from prism.ui.components.agent_components import render_bq_check_results
from prism.ui.components.cards import render_detail_card
from prism.ui.components.dashboard_components import get_suite_color
from prism.ui.components.dashboard_components import render_duration_chart
from prism.ui.components.dashboard_components import render_empty_evaluations_placeholder
from prism.ui.components.dashboard_components import render_evaluation_chart
from prism.ui.components.dashboard_components import render_recent_evals_table
from prism.ui.constants import CP
from prism.ui.constants import NOTIFICATION_CONTAINER
from prism.ui.constants import REDIRECT_HANDLER
from prism.ui.pages.agent_ids import AgentIds
from prism.ui.utils import format_timestamp
from prism.ui.utils import id_from_pathname
from prism.ui.utils import is_valid_bq_table
from prism.ui.utils import is_valid_looker_explore
from prism.ui.utils import parse_textarea_list
from prism.ui.utils import typed_callback
import pydantic

logger = logging.getLogger(__name__)


def _golden_query_error(e: Exception) -> str:
  """What a rejected golden query list is allowed to say in a toast.

  str() on a pydantic error prints input_value=, which is the whole rejected
  query: the Looker model, the explore, and the question somebody wrote
  against the customer's data. The field paths say as much about what to fix
  without putting the value back on the page.
  """
  if isinstance(e, pydantic.ValidationError):
    fields = ", ".join(
        ".".join(str(part) for part in error["loc"]) for error in e.errors()
    )
    if fields:
      return f"Invalid Golden Query structure. Check these fields: {fields}"
  return "Invalid Golden Query structure."


@typed_callback(
    [
        Output(AgentIds.Detail.CONTENT, CP.CHILDREN),
        Output(AgentIds.Detail.LOADING, CP.VISIBLE),
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
  """Renders the page from the stored agent and triggers the GCP fetch."""
  del refresh_trigger  # Its value is unused. A write to it re-runs this.
  if not pathname or not pathname.startswith("/agents/view/"):
    return (dash.no_update,) * 5 + (dash.no_update,)

  try:
    agent_id = id_from_pathname(pathname)
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

  stats_failed = False
  try:
    stats = client.runs.get_agent_dashboard_stats(agent_id, days=30)
  except Exception as e:  # pylint: disable=broad-except
    logger.error("Failed to fetch dashboard stats: %s", e)
    stats = {}
    stats_failed = True

  def _meta_item(label, value, mono=False):
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

  # Through the shared formatter, like the agents list table. This formatted
  # the stored clock itself, so the same agent's Last Updated read one way here
  # and another on the list, differing by the UTC offset.
  last_updated_str = (
      format_timestamp(agent.modified_at) if agent.modified_at else "N/A"
  )

  unified_header_card = dmc.Paper(
      withBorder=True,
      radius="md",
      p="lg",
      shadow="sm",
      children=[
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
          "Archive",
          id=AgentIds.Detail.BTN_ARCHIVE,
          variant="outline",
          radius="md",
          leftSection=DashIconify(icon="material-symbols:archive", width=20),
          color="gray",
          style={"display": "none"}
          if agent.is_archived
          else {"display": "block"},
      ),
      dmc.Button(
          "Restore",
          id=AgentIds.Detail.BTN_RESTORE,
          variant="filled",
          radius="md",
          leftSection=DashIconify(
              icon="material-symbols:settings-backup-restore", width=20
          ),
          color="green",
          style={"display": "block"}
          if agent.is_archived
          else {"display": "none"},
      ),
      dmc.Button(
          "Run Evaluation",
          id=AgentIds.Detail.BTN_RUN_EVAL,
          variant="filled",
          color="blue",
          radius="md",
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

  # The GCP details are skeletons here. A later callback fetches them, so that
  # a slow API call does not hold up the rest of the page.
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

  system_instruction_card = render_detail_card(
      title="System Instruction",
      description="The set of instructions sent to the LLM",
      action=dmc.Switch(
          id=AgentIds.Detail.SWITCH_INSTRUCTION_VIEW,
          label="Markdown",
          checked=True,
          size="sm",
      ),
      children=dmc.ScrollArea(
          mah=500,
          children=html.Div(
              id=AgentIds.Detail.INSTRUCTION,
              children=dmc.Skeleton(
                  visible=True,
                  height=150,
                  radius="md",
              ),
          ),
      ),
  )

  golden_queries_card = render_detail_card(
      title="Golden Queries",
      description="Examples to guide the agent",
      children=dmc.ScrollArea(
          mah=500,
          children=html.Div(
              id=AgentIds.Detail.CARD_GOLDEN_QUERIES,
              children=dmc.Skeleton(
                  visible=True,
                  height=100,
                  radius="md",
              ),
          ),
      ),
  )

  main_grid = dmc.Stack(
      gap="lg",
      children=[
          datasource_skeleton,
          system_instruction_card,
          golden_queries_card,
      ],
  )

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

  recent_evals = stats.get("recent_evals", [])
  if stats_failed:
    # A failed query is not a new agent, and the placeholder below says it is.
    evaluation_section = [
        dmc.Alert(
            "Could not load the evaluation history for this agent. The cause"
            " is in the server log.",
            title="Evaluation History Unavailable",
            color="red",
            radius="md",
            icon=DashIconify(icon="material-symbols:warning-rounded"),
        )
    ]
  elif not recent_evals:
    evaluation_section = [render_empty_evaluations_placeholder()]
  else:
    evaluation_section = [
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
        html.Div(
            render_recent_evals_table(recent_evals, agent_id=agent_id),
            style={"width": "100%"},
        ),
    ]

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
      {"agent_id": agent_id, "ts": time.time()},
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
    agent_id = id_from_pathname(pathname)
  except (ValueError, IndexError):
    return dash.no_update

  days = 30 if "30" in days_str else 7
  client = get_client()

  try:
    stats = client.runs.get_agent_dashboard_stats(agent_id, days=days)
  except Exception as e:  # pylint: disable=broad-except
    logger.error("Failed to fetch accuracy stats: %s", e)
    return dmc.Text("Error loading data", c="red")

  # render_evaluation_chart returns the whole Paper, so build the AreaChart
  # here instead.
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
    agent_id = id_from_pathname(pathname)
  except (ValueError, IndexError):
    return dash.no_update

  days = 30 if "30" in days_str else 7
  client = get_client()

  try:
    stats = client.runs.get_agent_dashboard_stats(agent_id, days=days)
  except Exception as e:  # pylint: disable=broad-except
    logger.error("Failed to fetch duration stats: %s", e)
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
        Output(AgentIds.Detail.CARD_GOLDEN_QUERIES, CP.CHILDREN),
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
    logger.error("Failed to fetch GCP details: %s", e)
    return (
        # Not the exception text. It is whatever the GDA client raised, which
        # carries the resource name and the request it was building, and this
        # renders into the page.
        dmc.Alert(
            "Could not load the agent's configuration from GDA. The details"
            " are in the server log.",
            color="red",
        ),
        dmc.Alert("Failed to load.", color="red"),
        dash.no_update,
        dash.no_update,
        # Edit stays disabled. The instruction reaches the form only through
        # the Store above, which this branch leaves alone, so the textarea
        # would open blank. submit_edit copies it onto the config it sends and
        # update_agent pushes any instruction that is not None, so saving a
        # rename once GDA came back replaced the published instruction with
        # the empty string, and the user got a green success toast.
        True,
        False,  # Re-enable duplicate button
        dash.no_update,
        dash.no_update,
    )

  if not gcp_agent:
    return (
        "Error: Agent not found on GCP.",
        "Error: Configuration unavailable.",
        dash.no_update,
        dash.no_update,
        True,  # Edit stays disabled. Same reason as the branch above.
        False,  # Re-enable duplicate button
        dash.no_update,
        dash.no_update,
    )

  instruction = gcp_agent.config.system_instruction or "No instruction."

  markdown_view = html.Div(
      id=AgentIds.Detail.INSTRUCTION_MARKDOWN,
      style={"display": "block"},
      children=dcc.Markdown(instruction),
  )

  raw_view = html.Div(
      id=AgentIds.Detail.INSTRUCTION_RAW,
      style={"display": "none"},
      children=dmc.Code(
          instruction,
          block=True,
          style={"whiteSpace": "pre-wrap"},
      ),
  )

  instruction_ui = html.Div(
      style={"maxHeight": "500px", "overflowY": "auto"},
      children=html.Div([markdown_view, raw_view]),
  )

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

  ds_colors = {"Looker": "blue", "BQ": "orange"}
  badge = dmc.Badge(
      ds_type,
      color=ds_colors.get(ds_type, "gray"),
      variant="light",
  )

  can_run_eval = ds_type != "Looker" or (
      bool(gcp_agent.config.looker_client_id)
      and bool(gcp_agent.config.looker_client_secret)
  )

  golden_queries_ui = []
  if gcp_agent.config.golden_queries:
    gqs = [gq.model_dump(mode="json") for gq in gcp_agent.config.golden_queries]
    json_str = json.dumps(gqs, indent=2)

    golden_queries_ui = html.Div(
        style={"maxHeight": "500px", "overflowY": "auto"},
        children=dmc.Stack(
            gap=0,
            children=[
                dcc.Markdown(
                    f"```json\n{json_str}\n```",
                    style={"fontSize": "12px", "lineHeight": "1.1"},
                )
            ],
        ),
    )
  else:
    golden_queries_ui = dmc.Text(
        "No golden queries configured.", size="sm", c="dimmed"
    )

  return (
      instruction_ui,
      dmc.Stack(children=ds_children),
      badge,
      # get_gcp_agent_details back-fills the stored secret so can_run_eval
      # above can see whether credentials exist. That value must not carry on
      # into the Store, which is serialized into the page. open_edit_modal is
      # the only reader and it wants system_instruction, which is held on GCP
      # and nowhere else.
      gcp_agent.config.model_dump(exclude={"looker_client_secret"}),
      False,  # Re-enable edit button
      False,  # Re-enable duplicate button
      not can_run_eval,  # BTN_RUN_EVAL disabled if missing creds
      dmc.Stack(children=[golden_queries_ui]),
  )


dash.clientside_callback(
    """
    function(checked) {
        if (checked) {
            return [{'display': 'block'}, {'display': 'none'}];
        } else {
            return [{'display': 'none'}, {'display': 'block'}];
        }
    }
    """,
    [
        Output(AgentIds.Detail.INSTRUCTION_MARKDOWN, "style"),
        Output(AgentIds.Detail.INSTRUCTION_RAW, "style"),
    ],
    Input(AgentIds.Detail.SWITCH_INSTRUCTION_VIEW, "checked"),
)


@typed_callback(
    [
        Output(AgentIds.Detail.MODAL_EDIT, "opened"),
        Output(AgentIds.Detail.INPUT_EDIT_NAME, CP.VALUE),
        Output(AgentIds.Detail.TEXTAREA_EDIT_INSTRUCTION, CP.VALUE),
        Output(AgentIds.Detail.CONTAINER_EDIT_LOOKER_CONFIG, "style"),
        Output(AgentIds.Detail.INPUT_EDIT_LOOKER_URI, CP.VALUE),
        Output(AgentIds.Detail.INPUT_EDIT_LOOKER_EXPLORES, CP.VALUE),
        Output(AgentIds.Detail.INPUT_EDIT_LOOKER_CLIENT_ID, CP.VALUE),
        Output(AgentIds.Detail.INPUT_EDIT_LOOKER_CLIENT_SECRET, CP.VALUE),
        Output(AgentIds.Detail.CONTAINER_EDIT_BQ_CONFIG, "style"),
        Output(AgentIds.Detail.INPUT_EDIT_BQ_TABLES, CP.VALUE),
        Output(AgentIds.Detail.INPUT_EDIT_GOLDEN_QUERIES, CP.VALUE),
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
    return (dash.no_update,) * 11

  current_name = ""
  instruction = ""

  is_looker = False
  looker_uri = ""
  looker_explores = []
  looker_client_id = ""
  golden_queries_str = ""

  is_bq = False
  bq_tables = []

  # Pull the name and datasource config from the DB, not the GCP copy.
  try:
    agent_id = id_from_pathname(pathname)
    client = get_client().agents
    agent = client.get_agent(agent_id)
    if agent:
      current_name = agent.name

      if agent.config:
        # The Pydantic Agent schema used in the UI uses agent.config.datasource.
        if isinstance(agent.config.datasource, agent_schemas.LookerConfig):
          is_looker = True
          looker_uri = agent.config.datasource.instance_uri
          looker_explores = agent.config.datasource.explores or []
          looker_client_id = agent.config.looker_client_id or ""

          if agent.config.golden_queries:
            gqs = [
                gq.model_dump(mode="json") for gq in agent.config.golden_queries
            ]
            golden_queries_str = json.dumps(gqs, indent=2)

        if isinstance(agent.config.datasource, agent_schemas.BigQueryConfig):
          is_bq = True
          bq_tables = agent.config.datasource.tables or []

  except Exception as e:  # pylint: disable=broad-except
    # The modal still opens, on the GCP copy below plus blanks. submit_edit
    # rejects the blank name, so a half-loaded form can't overwrite the real
    # one.
    logger.error("Failed to load agent for the edit modal: %s", e)

  # The instruction, and only the instruction. It is not stored locally, so the
  # GCP copy is the only source for it. The datasource is read above instead.
  # This used to set is_looker off the GCP copy without clearing is_bq, so an
  # agent the two disagreed about opened with both panels showing, the Looker
  # fields blank because they are filled from the DB read. submit_edit picks
  # the datasource type off the DB too, so whatever was typed into the extra
  # panel was dropped on save.
  if gcp_config:
    instruction = gcp_config.get("system_instruction") or ""

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
      # Never send the stored secret back. PasswordInput only masks it on
      # screen, so the plaintext would still sit in the callback response and
      # the DOM. Blank means "keep the stored secret"; see submit_edit.
      "",
      bq_style,
      "\n".join(bq_tables),
      golden_queries_str,
  )


@typed_callback(
    [
        Output(AgentIds.Detail.MODAL_EDIT, "opened", allow_duplicate=True),
        Output(AgentIds.Detail.EDIT_LOADING_OVERLAY, "visible"),
        Output(REDIRECT_HANDLER, CP.HREF, allow_duplicate=True),
        Output(
            NOTIFICATION_CONTAINER, "sendNotifications", allow_duplicate=True
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
        State(AgentIds.Detail.INPUT_EDIT_GOLDEN_QUERIES, CP.VALUE),
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
    golden_queries_raw,
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

  invalid_fields = []
  # open_edit_modal leaves this blank when it could not read the agent, and
  # update_agent would then write the blank over the stored name.
  if not (new_name or "").strip():
    invalid_fields.append("Name is required")
  try:
    agent_id = id_from_pathname(pathname)
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

    if golden_queries_raw:
      try:
        parsed_gqs = json.loads(golden_queries_raw)
        if not isinstance(parsed_gqs, list):
          invalid_fields.append("Golden Queries must be a list")
      except json.JSONDecodeError:
        invalid_fields.append("Golden Queries must be valid JSON")

  except (ValueError, IndexError):
    # The URL carries no agent id, so there is nothing to save. Keep the modal
    # open and say so; closing it looked like the edit had gone through.
    return (
        dash.no_update,
        False,
        dash.no_update,
        [{
            "action": "show",
            "title": "Could not save",
            "message": "This page is not a valid agent URL.",
            "color": "red",
            "autoClose": 5000,
        }],
        dash.no_update,
    )

  if invalid_fields:
    return (
        dash.no_update,
        False,
        dash.no_update,
        [{
            "action": "show",
            "title": "Validation Error",
            "message": ", ".join(invalid_fields),
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

      if isinstance(agent.config.datasource, agent_schemas.BigQueryConfig):
        new_config.datasource = agent_schemas.BigQueryConfig(tables=bq_tables)
      elif isinstance(agent.config.datasource, agent_schemas.LookerConfig):
        new_config.datasource = agent_schemas.LookerConfig(
            instance_uri=looker_uri, explores=looker_explores
        )
        new_config.looker_client_id = looker_client_id
        # None, not "": AgentRepository.update skips the secret when it's
        # None, which keeps the stored one. "" would wipe it.
        new_config.looker_client_secret = looker_client_secret or None

        if golden_queries_raw:
          try:
            # json.loads already succeeded in the validation pass above.
            gqs_list = json.loads(golden_queries_raw)
            new_config.golden_queries = [
                agent_schemas.LookerGoldenQuery.model_validate(item)
                for item in gqs_list
            ]
          except Exception as e:  # pylint: disable=broad-exception-caught
            return (
                dash.no_update,
                False,
                dash.no_update,
                [{
                    "action": "show",
                    "title": "Golden Query Error",
                    "message": _golden_query_error(e),
                    "color": "red",
                }],
                dash.no_update,
            )
        else:
          new_config.golden_queries = []

    else:
      # Reached only when the agent is missing or has no stored config. We
      # don't know the datasource type, so leave it unset.
      new_config = agent_schemas.AgentConfig(
          system_instruction=new_instruction,
      )

    if isinstance(new_config.datasource, agent_schemas.LookerConfig):
      # The field always opens blank, so blank only counts as missing when
      # there is nothing stored to fall back on.
      has_stored_secret = bool(
          agent and agent.config and agent.config.looker_client_secret
      )
      if not looker_client_id or not (
          looker_client_secret or has_stored_secret
      ):
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
    logger.error("Failed to update agent: %s", e)
    return (
        True,
        False,
        dash.no_update,
        [{
            "action": "show",
            "title": "Update Error",
            # Not the exception text. See the note in fetch_remote_config.
            "message": (
                "Could not save the agent. The details are in the server log."
            ),
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
    agent_id = id_from_pathname(pathname)
  except (ValueError, IndexError):
    return dash.no_update, dash.no_update, dash.no_update, dash.no_update

  client = get_client()
  agent = client.agents.get_agent(agent_id)
  if not agent:
    return dash.no_update, dash.no_update, dash.no_update, dash.no_update

  # No validation alert here. handle_suite_selection re-checks the Looker
  # credentials once a suite is picked and disables the start button.
  alert = None

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
    agent_id = id_from_pathname(pathname)
  except (ValueError, IndexError):
    return dash.no_update, True

  client = get_client()
  suite = client.suites.get_suite(s_id)
  if not suite:
    return (
        dmc.Alert("Test Suite not found.", color="red", variant="light"),
        True,
    )

  # Credentials can be cleared between the page load and this callback, so the
  # button state is decided on a fresh read.
  agent = client.agents.get_agent(agent_id)
  if not agent:
    return dash.no_update, True

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
            NOTIFICATION_CONTAINER, "sendNotifications", allow_duplicate=True
        ),
    ],
    [Input(AgentIds.Detail.EvalModal.BTN_START, CP.N_CLICKS)],
    [
        State("url", CP.PATHNAME),
        State(AgentIds.Detail.EvalModal.SELECT_SUITE, CP.VALUE),
        State(AgentIds.Detail.EvalModal.TOGGLE_SUGGESTIONS, "checked"),
        State(AgentIds.Detail.EvalModal.INPUT_CONCURRENCY, CP.VALUE),
    ],
    prevent_initial_call=True,
    # Starting a run spawns trials that call a paid API. Without this the
    # button stays live for the whole round trip and a second click starts a
    # second run.
    running=[
        (
            Output(AgentIds.Detail.EvalModal.BTN_START, CP.DISABLED),
            True,
            False,
        ),
        (Output(AgentIds.Detail.EvalModal.BTN_START, CP.LOADING), True, False),
    ],
)
def start_evaluation(
    n_clicks, pathname, suite_id, generate_suggestions, concurrency
):
  """Starts a new evaluation run."""
  if not n_clicks or not suite_id:
    return dash.no_update

  try:
    agent_id = id_from_pathname(pathname)
    s_id = int(suite_id)
  except (ValueError, IndexError):
    return dash.no_update

  # Clearing the NumberInput sends "", not the default it was rendered with.
  # That went all the way to the insert and failed there, so the user got the
  # generic "could not start" toast for a field they could see was empty.
  try:
    max_concurrency = int(concurrency)
  except (TypeError, ValueError):
    return dash.no_update, [{
        "action": "show",
        "title": "Cannot Start Evaluation",
        "message": "Max Concurrency must be a number between 1 and 100.",
        "color": "red",
        "icon": DashIconify(icon="material-symbols:error-outline"),
    }]

  client = get_client()
  agent = client.agents.get_agent(agent_id)

  # The button is disabled without credentials, but the modal can be open
  # from before they were cleared.
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
    run = client.runs.create_run(
        agent_id=agent_id,
        test_suite_id=s_id,
        generate_suggestions=generate_suggestions,
        concurrency=max_concurrency,
    )
    return f"/evaluations/runs/{run.id}", dash.no_update
  except Exception as e:  # pylint: disable=broad-except
    logger.exception("Failed to create run: %s", e)
    return dash.no_update, [{
        "action": "show",
        "title": "Failed to Start Evaluation",
        # Not the exception text. See the note in fetch_remote_config. This
        # one reaches the agent and datasource layer, so what it raises
        # carries resource names and instance URIs.
        "message": (
            "Could not start the evaluation. The details are in the server log."
        ),
        "color": "red",
    }]


@typed_callback(
    Output(AgentIds.Detail.EvalModal.ROOT, "opened", allow_duplicate=True),
    [
        Input(AgentIds.Detail.EvalModal.BTN_CANCEL, CP.N_CLICKS),
        Input(AgentIds.Detail.EvalModal.BTN_CLOSE, CP.N_CLICKS),
    ],
    prevent_initial_call=True,
)
def close_eval_modal(cancel_clicks, close_clicks):
  """Closes the evaluation modal."""
  del cancel_clicks, close_clicks
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
    agent_id = id_from_pathname(pathname)
    client = get_client()
    agent = client.agents.get_agent(agent_id)
    if agent:
      current_name = agent.name
  except Exception as e:  # pylint: disable=broad-except
    # Losing the prefill is not worth blocking the duplicate, so the modal
    # still opens with a generic name. It used to swallow the reason too,
    # which left no trace of why the name went generic.
    logger.error("Failed to read the agent name for the copy: %s", e)

  return True, f"Copy of {current_name}" if current_name else "Copy of Agent"


@typed_callback(
    [
        Output(AgentIds.Detail.MODAL_DUPLICATE, "opened", allow_duplicate=True),
        Output(AgentIds.Detail.DUPLICATE_LOADING_OVERLAY, "visible"),
        Output(REDIRECT_HANDLER, CP.HREF, allow_duplicate=True),
        Output(
            NOTIFICATION_CONTAINER, "sendNotifications", allow_duplicate=True
        ),
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
    return dash.no_update, dash.no_update, dash.no_update, dash.no_update

  try:
    agent_id = id_from_pathname(pathname)
  except (ValueError, IndexError):
    return False, False, dash.no_update, dash.no_update

  client = get_client()
  try:
    new_agent = client.agents.duplicate_agent(agent_id, new_name)
    return False, False, f"/agents/view/{new_agent.id}", dash.no_update
  except Exception as e:  # pylint: disable=broad-except
    logger.error("Failed to duplicate agent: %s", e)
    # The modal is left open on purpose, so the name the user typed survives.
    # On its own that reads as a dead button, which is why the toast is here.
    return (
        True,
        False,
        dash.no_update,
        [{
            "action": "show",
            "title": "Duplicate Failed",
            # Not the exception text. See the note in fetch_remote_config.
            "message": (
                "Could not duplicate the agent. The details are in the server"
                " log."
            ),
            "color": "red",
        }],
    )


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
    ],
    [Input(AgentIds.Detail.BTN_TEST_LOOKER, CP.N_CLICKS)],
    [
        State(AgentIds.Detail.INPUT_EDIT_LOOKER_URI, CP.VALUE),
        State(AgentIds.Detail.INPUT_EDIT_LOOKER_CLIENT_ID, CP.VALUE),
        State(AgentIds.Detail.INPUT_EDIT_LOOKER_CLIENT_SECRET, CP.VALUE),
        State("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
    # The spinner has to come from running=. Returning loading=False with the
    # result cannot show one: the round trip is over by the time the value
    # arrives, so the button sat inert for the whole call to Looker.
    running=[
        (Output(AgentIds.Detail.BTN_TEST_LOOKER, CP.LOADING), True, False)
    ],
)
def test_looker_connectivity(n_clicks, uri, client_id, client_secret, pathname):
  """Tests Looker connectivity."""
  if not n_clicks:
    return dash.no_update, True, "blue"

  # The secret is not checked here. open_edit_modal returns "" for it and
  # never sends the stored one back, so requiring it refused every saved
  # agent, which is what the button is for. Blank means keep the stored
  # secret, and the service fills it from the agent row.
  if not all([uri, client_id]):
    return (
        "Incomplete credentials. Please provide URI, Client ID, and Secret.",
        False,
        "orange",
    )

  try:
    agent_id = id_from_pathname(pathname)
  except (ValueError, IndexError):
    agent_id = None

  client = get_client().agents
  try:
    result = client.test_looker_credentials(
        instance_uri=uri,
        client_id=client_id,
        client_secret=client_secret,
        agent_id=agent_id,
    )
    color = "green" if result["success"] else "red"
    return result.get("message", "Success!"), False, color
  except Exception as e:  # pylint: disable=broad-except
    logger.error("Looker connection test failed: %s", e)
    # Not the exception text. See the note in fetch_remote_config. The
    # message the service builds for a rejected login is returned above; this
    # branch is whatever the SDK raised on the way there.
    return (
        (
            "Could not reach the Looker instance. The details are in the server"
            " log."
        ),
        False,
        "red",
    )


@typed_callback(
    [
        Output(
            AgentIds.Detail.STORE_REFRESH_TRIGGER, CP.DATA, allow_duplicate=True
        ),
        Output(
            NOTIFICATION_CONTAINER, "sendNotifications", allow_duplicate=True
        ),
    ],
    [
        Input(AgentIds.Detail.BTN_ARCHIVE, CP.N_CLICKS),
        Input(AgentIds.Detail.BTN_RESTORE, CP.N_CLICKS),
    ],
    [State("url", CP.PATHNAME)],
    prevent_initial_call=True,
)
def toggle_agent_archive(
    archive_clicks: int, restore_clicks: int, pathname: str
):
  """Archives or restores an agent."""
  ctx = dash.callback_context
  if not ctx.triggered:
    return dash.no_update, dash.no_update

  triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
  if not archive_clicks and not restore_clicks:
    return dash.no_update, dash.no_update

  try:
    agent_id = id_from_pathname(pathname)
  except (ValueError, IndexError):
    return dash.no_update, dash.no_update

  client = get_client().agents
  try:
    if triggered_id == AgentIds.Detail.BTN_ARCHIVE:
      client.archive_agent(agent_id)
      msg = "Agent archived successfully."
    else:
      client.unarchive_agent(agent_id)
      msg = "Agent restored successfully."

    # NotificationContainer wants a list of actions. A bare dict is silently
    # ignored, which hid this toast and the error one below.
    return {"ts": time.time()}, [{
        "action": "show",
        "title": "Success",
        "message": msg,
        "color": "green",
    }]
  except Exception as e:  # pylint: disable=broad-exception-caught
    logger.error("Failed to toggle agent archive: %s", e)
    return dash.no_update, [{
        "action": "show",
        "title": "Error",
        # Not the exception text. See the note in fetch_remote_config.
        "message": (
            "Could not archive the agent. The details are in the server log."
        ),
        "color": "red",
    }]


@typed_callback(
    [
        Output(
            AgentIds.Detail.INPUT_EDIT_GOLDEN_QUERIES,
            CP.VALUE,
            allow_duplicate=True,
        ),
        Output(
            AgentIds.Detail.ERROR_GOLDEN_QUERIES,
            CP.CHILDREN,
            allow_duplicate=True,
        ),
    ],
    [Input(AgentIds.Detail.BTN_FIX_GOLDEN_QUERIES_AI, CP.N_CLICKS)],
    [State(AgentIds.Detail.INPUT_EDIT_GOLDEN_QUERIES, CP.VALUE)],
    prevent_initial_call=True,
)
def fix_golden_queries_with_ai(n_clicks, current_value):
  """Uses AI to fix/format the golden queries JSON."""
  if not n_clicks:
    return dash.no_update, dash.no_update

  if not current_value:
    return dash.no_update, dash.no_update

  try:
    client = get_client().agents

    result = client.format_golden_queries_with_ai(current_value)
    return result, ""  # Clear error on success
  except Exception as e:  # pylint: disable=broad-exception-caught
    logger.error("Failed to fix golden queries with AI: %s", e)
    # Not the exception text. See the note in fetch_remote_config.
    return (
        dash.no_update,
        "AI fix failed. The details are in the server log.",
    )


@typed_callback(
    Output(AgentIds.Detail.ERROR_GOLDEN_QUERIES, CP.CHILDREN),
    [Input(AgentIds.Detail.INPUT_EDIT_GOLDEN_QUERIES, CP.VALUE)],
    prevent_initial_call=True,
)
def validate_golden_queries_edit(value: str | None):
  """Validates golden queries JSON in edit modal."""
  if not value:
    return ""

  try:
    parsed = json.loads(value)
    if not isinstance(parsed, list):
      return "Error: Must be a list of objects"
  except json.JSONDecodeError as e:
    return f"Invalid JSON: {e}"

  return ""


@typed_callback(
    [
        Output(AgentIds.Detail.ALERT_BQ_TEST, CP.CHILDREN),
        Output(AgentIds.Detail.ALERT_BQ_TEST, CP.HIDE),
        Output(AgentIds.Detail.ALERT_BQ_TEST, "color"),
    ],
    [Input(AgentIds.Detail.BTN_TEST_BQ, CP.N_CLICKS)],
    [
        State(AgentIds.Detail.INPUT_EDIT_BQ_TABLES, CP.VALUE),
    ],
    prevent_initial_call=True,
    # See the note on test_looker_connectivity. One round trip per table, so
    # this is the slower of the two.
    running=[(Output(AgentIds.Detail.BTN_TEST_BQ, CP.LOADING), True, False)],
)
def test_bq_tables(n_clicks, tables_text):
  """Checks the BQ tables against BigQuery from the edit modal."""
  if not n_clicks:
    return dash.no_update, True, "blue"

  tables = parse_textarea_list(tables_text)
  if not tables:
    return "Enter at least one table to check.", False, "orange"

  client = get_client().agents
  try:
    results = client.check_bigquery_tables(tables=tables)
  except Exception as e:  # pylint: disable=broad-except
    logger.error("BigQuery table check failed: %s", e)
    # Not the exception text. See the note in fetch_remote_config. A per
    # table error is reported by render_bq_check_results below; this branch
    # is the call itself failing.
    return (
        "Could not check these tables. The details are in the server log.",
        False,
        "red",
    )

  children, color = render_bq_check_results(results)
  return children, False, color
