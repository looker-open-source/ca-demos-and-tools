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

"""Callbacks for the Add Agent page."""

import dash
from dash import Input
from dash import Output
from dash import State
import dash_mantine_components as dmc
from prism.client import get_client
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import BigQueryConfig
from prism.common.schemas.agent import LookerConfig
from prism.ui.constants import CP
from prism.ui.constants import GLOBAL_PROJECT_ID_STORE
from prism.ui.constants import REDIRECT_HANDLER
from prism.ui.pages.agent_ids import AgentIds
from prism.ui.utils import is_valid_bq_table
from prism.ui.utils import is_valid_looker_explore
from prism.ui.utils import parse_textarea_list
from prism.ui.utils import typed_callback


@typed_callback(
    Output(AgentIds.Form.INPUT_PROJECT, "data"),
    [Input("url", CP.PATHNAME)],
)
def load_project_id_options_add(pathname: str):
  """Loads configured GDA projects as options for the Select component."""
  if pathname != "/agents/onboard/new":
    return dash.no_update
  projects = get_client().agents.get_configured_gda_projects()
  return [{"label": p, "value": p} for p in projects]


@typed_callback(
    Output(AgentIds.Form.INPUT_PROJECT, CP.VALUE),
    [Input(AgentIds.Form.INPUT_PROJECT, "data")],
    [State(GLOBAL_PROJECT_ID_STORE, "data")],
)
def populate_project_id_add(
    options: list[dict[str, str]], project_id: str | None
):
  """Pre-populates the GCP project ID field."""
  if not options:
    return dash.no_update

  # If we have a project_id from store and it's in options, use it.
  # Otherwise use the first option.
  if project_id and any(o["value"] == project_id for o in options):
    return project_id

  return options[0]["value"]


@typed_callback(
    [
        Output("bq-datasource-container", "style"),
        Output("looker-datasource-container", "style"),
    ],
    [Input(AgentIds.Form.SELECT_DATASOURCE_TYPE, CP.VALUE)],
)
def toggle_datasource_type(datasource_type: str):
  """Toggles the visibility of datasource configuration sections."""
  if datasource_type == "looker":
    return {"display": "none"}, {"display": "block"}
  return {"display": "block"}, {"display": "none"}


@typed_callback(
    [
        Output(REDIRECT_HANDLER, CP.HREF, allow_duplicate=True),
        Output("agent-add-loading-overlay", "visible"),
        Output("notification-container", "sendNotifications"),
    ],
    [Input(AgentIds.Add.BTN_SUBMIT, CP.N_CLICKS)],
    state=[
        State(AgentIds.Form.INPUT_NAME, CP.VALUE),
        State(AgentIds.Form.INPUT_PROJECT, CP.VALUE),
        State(AgentIds.Form.INPUT_LOCATION, CP.VALUE),
        State(AgentIds.Form.TEXTAREA_INSTRUCTION, CP.VALUE),
        # New Datasource Fields
        State(AgentIds.Form.SELECT_DATASOURCE_TYPE, CP.VALUE),
        State(AgentIds.Form.INPUT_BQ_TABLES, CP.VALUE),
        State(AgentIds.Form.INPUT_LOOKER_URI, CP.VALUE),
        State(AgentIds.Form.INPUT_LOOKER_EXPLORES, CP.VALUE),
        State(AgentIds.Form.INPUT_LOOKER_CLIENT_ID, CP.VALUE),
        State(AgentIds.Form.INPUT_LOOKER_CLIENT_SECRET, CP.VALUE),
    ],
    prevent_initial_call=True,
)
def add_agent(
    n_clicks: int,
    name: str,
    project: str,
    location: str,
    instruction: str,
    ds_type: str,
    bq_tables_raw: str | None,
    looker_uri: str | None,
    looker_explores_raw: str | None,
    looker_client_id: str | None,
    looker_client_secret: str | None,
):
  """Handles agent creation and redirection."""
  if not n_clicks:
    return dash.no_update, dash.no_update, dash.no_update

  bq_tables = parse_textarea_list(bq_tables_raw)
  looker_explores = parse_textarea_list(looker_explores_raw)

  # 1. Comprehensive Validation
  missing_fields = []
  invalid_fields = []

  if not name:
    missing_fields.append("Agent Name")
  if not project:
    missing_fields.append("GCP Project ID")
  if not location:
    missing_fields.append("GCP Location")

  # Datasource specific validation
  if ds_type == "looker":
    if not looker_uri:
      missing_fields.append("Looker Instance URI")
    if not looker_explores:
      missing_fields.append("Looker Explores")
    else:
      for e in looker_explores:
        if not is_valid_looker_explore(e):
          invalid_fields.append(f"Invalid Looker Explore: {e}")
    if not looker_client_id:
      missing_fields.append("Looker Client ID")
    if not looker_client_secret:
      missing_fields.append("Looker Client Secret")
  else:
    if not bq_tables:
      missing_fields.append("BigQuery Tables")
    else:
      for t in bq_tables:
        if not is_valid_bq_table(t):
          invalid_fields.append(f"Invalid BQ Table: {t}")

  if missing_fields or invalid_fields:
    msg_parts = []
    if missing_fields:
      msg_parts.append(f"Missing: {', '.join(missing_fields)}")
    if invalid_fields:
      msg_parts.append(f"Invalid format: {', '.join(invalid_fields)}")

    msg = ". ".join(msg_parts)
    return (
        dash.no_update,
        False,
        [{
            "action": "show",
            "title": "Validation Error",
            "message": msg,
            "color": "red",
            "autoClose": 5000,
        }],
    )

  try:
    if ds_type == "looker":
      datasource = LookerConfig(
          instance_uri=looker_uri or "",
          explores=looker_explores or [],
      )
    else:
      datasource = BigQueryConfig(
          tables=bq_tables or [],
      )

    config = AgentConfig(
        project_id=project,
        location=location,
        agent_resource_id="",  # Generated by GCP
        datasource=datasource,
        system_instruction=instruction or "",
        looker_client_id=looker_client_id,
        looker_client_secret=looker_client_secret,
    )

    # Delegate to client
    client = get_client().agents
    agent = client.register_gcp_agent(name=name, config=config)

    return (
        f"/agents/view/{agent.id}",
        False,
        None,
    )  # Redirect on success, hide loading, clear alert
  except Exception as e:  # pylint: disable=broad-exception-caught
    return (
        dash.no_update,
        False,
        [{
            "action": "show",
            "title": "Submission Error",
            "message": f"Failed to create agent: {str(e)}",
            "color": "red",
            "autoClose": False,
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
    Output("agent-add-loading-overlay", "visible", allow_duplicate=True),
    Input(AgentIds.Add.BTN_SUBMIT, CP.N_CLICKS),
    prevent_initial_call=True,
)


@typed_callback(
    [
        Output(AgentIds.Form.ALERT_LOOKER_TEST, CP.CHILDREN),
        Output(AgentIds.Form.ALERT_LOOKER_TEST, CP.HIDE),
        Output(AgentIds.Form.ALERT_LOOKER_TEST, "color"),
        Output(AgentIds.Form.BTN_TEST_LOOKER, "loading"),
    ],
    [Input(AgentIds.Form.BTN_TEST_LOOKER, CP.N_CLICKS)],
    [
        State(AgentIds.Form.INPUT_LOOKER_URI, CP.VALUE),
        State(AgentIds.Form.INPUT_LOOKER_CLIENT_ID, CP.VALUE),
        State(AgentIds.Form.INPUT_LOOKER_CLIENT_SECRET, CP.VALUE),
    ],
    prevent_initial_call=True,
)
def test_looker_connectivity_add(n_clicks, uri, client_id, client_secret):
  """Tests Looker connectivity during agent creation."""
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
  except Exception as e:
    return f"Test failed: {str(e)}", False, "red", False


@typed_callback(
    [
        Output(AgentIds.Form.INPUT_BQ_TABLES_PREVIEW, CP.CHILDREN),
        Output(AgentIds.Form.INPUT_BQ_TABLES, "error"),
    ],
    [Input(AgentIds.Form.INPUT_BQ_TABLES, CP.VALUE)],
)
def validate_bq_tables_add(value: str | None):
  """Validates and previews BQ table paths."""
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
        Output(AgentIds.Form.INPUT_LOOKER_EXPLORES_PREVIEW, CP.CHILDREN),
        Output(AgentIds.Form.INPUT_LOOKER_EXPLORES, "error"),
    ],
    [Input(AgentIds.Form.INPUT_LOOKER_EXPLORES, CP.VALUE)],
)
def validate_looker_explores_add(value: str | None):
  """Validates and previews Looker explore paths."""
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
