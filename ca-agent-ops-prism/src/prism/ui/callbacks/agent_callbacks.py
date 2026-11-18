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

"""Callbacks for Monitoring Dashboard Home."""

import urllib.parse

import dash
from dash import Input
from dash import Output
from dash import State
from prism.client import get_client
from prism.ui.components import tables
from prism.ui.constants import CP
from prism.ui.pages.agent_ids import AgentIds
from prism.ui.utils import typed_callback


@typed_callback(
    Output(AgentIds.Home.ChoiceModal.ROOT, CP.OPENED),
    [
        Input(AgentIds.Home.BTN_MONITOR, CP.N_CLICKS),
        Input(AgentIds.Home.ChoiceModal.BTN_CREATE, CP.N_CLICKS),
        Input(AgentIds.Home.ChoiceModal.BTN_EXISTING, CP.N_CLICKS),
        Input(AgentIds.Home.ChoiceModal.BTN_CANCEL, CP.N_CLICKS),
    ],
    state=[State(AgentIds.Home.ChoiceModal.ROOT, CP.OPENED)],
    prevent_initial_call=True,
)
def toggle_choice_modal(*_args):
  """Toggles the choice modal.

  Create and existing are anchors that navigate away, so for those two all
  this does is close the modal behind them.
  """
  is_open = _args[-1]
  return not is_open


@typed_callback(
    Output(AgentIds.Home.SWITCH_ARCHIVED, CP.CHECKED),
    inputs=[
        ("url", CP.PATHNAME),
        ("url", CP.SEARCH),
    ],
)
def sync_agent_filters_to_url(pathname: str, search: str):
  """Syncs the Show Archived switch with URL search params."""
  if pathname != "/agents":
    return dash.no_update
  if not search:
    return False
  params = urllib.parse.parse_qs(search.lstrip("?"))
  return params.get("archived", ["false"])[0] == "true"


@typed_callback(
    Output("url", CP.SEARCH, allow_duplicate=True),
    inputs=[(AgentIds.Home.SWITCH_ARCHIVED, CP.CHECKED)],
    state=[
        ("url", CP.PATHNAME),
        ("url", CP.SEARCH),
    ],
    prevent_initial_call=True,
)
def update_agent_url_from_archived_switch(
    include_archived: bool,
    pathname: str,
    current_search: str,
):
  """Updates URL search params when the Show Archived switch changes."""
  if pathname != "/agents":
    return dash.no_update

  params = (
      urllib.parse.parse_qs(current_search.lstrip("?"))
      if current_search
      else {}
  )
  cur_archived = params.get("archived", ["false"])[0] == "true"
  if cur_archived == bool(include_archived):
    return dash.no_update

  if include_archived:
    params["archived"] = ["true"]
  else:
    params.pop("archived", None)

  return f"?{urllib.parse.urlencode(params, doseq=True)}" if params else ""


@typed_callback(
    Output(AgentIds.Home.CARD_GRID, CP.CHILDREN),
    [
        Input("url", CP.PATHNAME),
        Input(AgentIds.Home.SWITCH_ARCHIVED, CP.CHECKED),
    ],
)
def update_agent_list(pathname: str, include_archived: bool):
  """Updates the agent list UI with cards."""
  if pathname != "/agents":
    return dash.no_update
  client = get_client()
  agents_client = client.agents
  runs_client = client.runs

  agents = agents_client.list_agents(include_archived=include_archived)

  agent_ids = [a.id for a in agents]
  latest_runs_map = runs_client.get_latest_runs_with_stats(agent_ids)

  run_history = runs_client.get_run_history_for_agents(agent_ids, limit=20)

  cards = tables.render_agent_table(agents, latest_runs_map, run_history)

  return cards
