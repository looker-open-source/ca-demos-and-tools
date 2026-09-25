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
from prism.ui.ids import EvaluationIds as Ids


def layout(run_id: str = ""):
  """Renders the Evaluation Detail layout.

  Args:
    run_id: The run to display. Empty string, not None: it is interpolated into
      a pattern-matching component id, and Dash rejects None as a dict id value.
  """
  return render_page(
      # Without a run there is no number, and "Evaluation Run #" reads as a
      # rendering bug. Dash calls layout() with no argument when it builds the
      # page registry, so the empty case is hit on every boot.
      title=f"Evaluation Run #{run_id}" if run_id else "Evaluation Run",
      breadcrumbs_id=Ids.RUN_BREADCRUMBS_CONTAINER,
      status_id=Ids.RUN_STATUS_BADGE,
      extra_badges=[
          html.Div(
              id=Ids.RUN_BIGQUERY_BADGE,
              style={"display": "flex", "alignItems": "center"},
          )
      ],
      actions=[
          dmc.Group(
              gap="xs",
              children=[
                  dmc.Button(
                      "Pause",
                      id=Ids.BTN_PAUSE_RUN,
                      variant="default",
                      radius="md",
                      leftSection=DashIconify(icon="bi:pause-fill", width=20),
                      style={"display": "none"},
                  ),
                  dmc.Button(
                      "Resume",
                      id=Ids.BTN_RESUME_RUN,
                      variant="default",
                      radius="md",
                      leftSection=DashIconify(icon="bi:play-fill", width=20),
                      style={"display": "none"},
                  ),
                  dmc.Button(
                      "Cancel",
                      id=Ids.BTN_CANCEL_RUN_EXEC,
                      variant="default",
                      radius="md",
                      leftSection=DashIconify(icon="bi:x-circle", width=20),
                      style={"display": "none"},
                  ),
                  dmc.Button(
                      "Sync to BigQuery",
                      id=Ids.BTN_SYNC_BIGQUERY,
                      variant="outline",
                      color="blue",
                      radius="md",
                      leftSection=DashIconify(
                          icon="material-symbols:cloud-upload", width=20
                      ),
                      style={"display": "none"},
                  ),
                  dmc.Button(
                      "Archive",
                      id=Ids.BTN_ARCHIVE,
                      variant="outline",
                      color="gray",
                      radius="md",
                      leftSection=DashIconify(
                          icon="material-symbols:archive", width=20
                      ),
                      style={"display": "none"},
                  ),
                  dmc.Button(
                      "Restore",
                      id=Ids.BTN_RESTORE,
                      variant="filled",
                      color="green",
                      radius="md",
                      leftSection=DashIconify(
                          icon="material-symbols:settings-backup-restore",
                          width=20,
                      ),
                      style={"display": "none"},
                  ),
                  dmc.Button(
                      "Compare to",
                      id={
                          "type": Ids.BTN_OPEN_COMPARE_MODAL,
                          "index": run_id,
                      },
                      leftSection=DashIconify(
                          icon="material-symbols:compare-arrows", width=20
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
                  dmc.SimpleGrid(
                      cols={"base": 1, "sm": 2, "lg": 4},
                      id=Ids.RUN_DETAIL_STATS,
                      # One per card render_run_detail_components fills this
                      # with: Agent, Test Suite, Avg Accuracy, Avg Trial
                      # Duration. Three left the row a column short on every
                      # load, then it jumped to four.
                      children=[
                          dmc.Skeleton(height=100),
                          dmc.Skeleton(height=100),
                          dmc.Skeleton(height=100),
                          dmc.Skeleton(height=100),
                      ],
                  ),
                  # Dynamic content (charts and table), filled by polling.
                  html.Div(id=Ids.RUN_CHARTS_CONTAINER),
                  html.Div(id=Ids.RUN_TRIALS_CONTAINER),
                  render_compare_run_modal(),
                  run_components.render_diff_modal(),
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
