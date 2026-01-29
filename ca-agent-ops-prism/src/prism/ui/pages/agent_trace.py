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

"""Agent Trace page."""

import dash
from dash import html
import dash_mantine_components as dmc
from prism.ui.components.page_layout import render_page
from prism.ui.ids import EvaluationIds as Ids


def layout(**_kwargs):
  """Renders the Agent Trace layout."""
  return render_page(
      title="Agent Trace",
      title_id=Ids.AGENT_TRACE_TITLE,
      status_id=Ids.AGENT_TRACE_STATUS,
      actions_id=Ids.AGENT_TRACE_ACTIONS,
      breadcrumbs_id=Ids.AGENT_TRACE_BREADCRUMBS_CONTAINER,
      children=[
          dash.dcc.Store(id=Ids.AGENT_TRACE_RAW_STORE),
          dash.dcc.Download(id=Ids.AGENT_TRACE_DOWNLOAD_COMPONENT),
          dmc.Modal(
              id=Ids.AGENT_TRACE_RAW_MODAL,
              title="Raw Execution Trace",
              size="70%",
              children=[
                  dmc.ScrollArea(
                      h=600,
                      children=[
                          dmc.Code(
                              id=Ids.AGENT_TRACE_RAW_MODAL + "-content",
                              block=True,
                              fz="xs",
                          )
                      ],
                  )
              ],
          ),
          html.Div(
              id=Ids.AGENT_TRACE_CONTAINER,
              children=[dmc.Center(children=[dmc.Loader(variant="dots")])],
          ),
      ],
  )


def register_page():
  dash.register_page(
      __name__,
      path_template="/evaluations/trials/<trial_id>/trace",
      title="Prism | Agent Trace",
      layout=layout,
  )
