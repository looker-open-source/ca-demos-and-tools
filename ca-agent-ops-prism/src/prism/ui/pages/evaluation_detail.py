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

"""Evaluation Detail page."""

import dash
from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.ui.components import run_components
from prism.ui.components.page_layout import render_page
from prism.ui.components.run_modals import render_compare_run_modal
from prism.ui.pages.evaluation_ids import EvaluationIds as Ids


def layout(run_id: str = None):
  """Renders the Evaluation Detail layout."""
  return render_page(
      title=f"Evaluation Run #{run_id}",
      breadcrumbs_id=Ids.RUN_BREADCRUMBS_CONTAINER,
      status_id=Ids.RUN_STATUS_BADGE,
      actions=[
          dmc.Group(
              gap="xs",
              children=[
                  dmc.Button(
                      "Pause",
                      id=Ids.BTN_PAUSE_RUN,
                      variant="default",
                      radius="md",
                      fw=600,
                      size="xs",
                      leftSection=DashIconify(icon="bi:pause-fill"),
                      style={"display": "none"},
                  ),
                  dmc.Button(
                      "Resume",
                      id=Ids.BTN_RESUME_RUN,
                      variant="default",
                      radius="md",
                      fw=600,
                      size="xs",
                      leftSection=DashIconify(icon="bi:play-fill"),
                      style={"display": "none"},
                  ),
                  dmc.Button(
                      "Cancel",
                      id=Ids.BTN_CANCEL_RUN_EXEC,
                      variant="default",
                      radius="md",
                      fw=600,
                      size="xs",
                      leftSection=DashIconify(icon="bi:x-circle"),
                      style={"display": "none"},
                  ),
                  dmc.Button(
                      "Compare to",
                      id={
                          "type": Ids.BTN_OPEN_COMPARE_MODAL,
                          "index": run_id,
                      },
                      leftSection=DashIconify(
                          icon="material-symbols:compare-arrows"
                      ),
                      variant="outline",
                      color="gray",
                      radius="md",
                  ),
              ],
          ),
      ],
      children=[
          dash.dcc.Store(id=Ids.RUN_CONTEXT_TRIGGER),
          dash.dcc.Store(id=Ids.RUN_UPDATE_SIGNAL),
          dash.dcc.Interval(
              id=Ids.RUN_POLLING_INTERVAL,
              interval=3000,
              n_intervals=0,
              disabled=True,
          ),
          dmc.Stack(
              gap="xl",
              children=[
                  # Summary Stats
                  dmc.SimpleGrid(
                      cols={"base": 1, "sm": 2, "lg": 4},
                      id=Ids.RUN_DETAIL_STATS,
                      children=[
                          # Placeholders
                          dmc.Skeleton(height=100),
                          dmc.Skeleton(height=100),
                          dmc.Skeleton(height=100),
                      ],
                  ),
                  # Dynamic Content (Charts and Table - Polling)
                  html.Div(id=Ids.RUN_CHARTS_CONTAINER),
                  html.Div(id=Ids.RUN_TRIALS_CONTAINER),
                  render_compare_run_modal(),
                  run_components.render_diff_modal([]),
                  dash.dcc.Download(id=Ids.DOWNLOAD_DIFF_COMPONENT),
                  dash.dcc.Store(id=Ids.RUN_CONTEXT_DIFF_STORE),
                  dash.dcc.Store(id=Ids.RUN_DATA_STORE),
              ],
          ),
      ],
  )


def register_page():
  dash.register_page(
      __name__,
      path_template="/evaluations/runs/<run_id>",
      title="Prism | Run Detail",
      layout=layout,
  )
