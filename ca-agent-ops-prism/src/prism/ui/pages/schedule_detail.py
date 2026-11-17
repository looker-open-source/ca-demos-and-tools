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

"""Schedule Detail page."""

import dash
from dash import dcc
from dash import html
import dash_mantine_components as dmc
from prism.ui.components import schedule_components
from prism.ui.components.page_layout import render_page
from prism.ui.ids import ScheduleDetailIds as Ids
from prism.ui.ids import ScheduleIds


def layout(schedule_id: str = "", **_kwargs):  # pylint: disable=unused-argument
  """Renders the Schedule Detail skeleton.

  The callbacks fill every container from the path, so a schedule edited,
  paused, or archived here redraws in place without a page load.

  Args:
    schedule_id: The id from the path. Unused here; the callbacks read it.

  Returns:
    The page skeleton.
  """
  return render_page(
      title="Schedule",
      title_id=Ids.TITLE,
      breadcrumbs_id=Ids.BREADCRUMBS,
      extra_badges=[
          html.Div(
              id=Ids.STATUS_CONTAINER,
              style={"display": "flex", "alignItems": "center"},
          )
      ],
      actions_id=Ids.ACTIONS,
      children=[
          dcc.Interval(id=Ids.POLL_INTERVAL, interval=5000, n_intervals=0),
          # Bumped by the poll only while the header is still unrendered.
          dcc.Store(id=Ids.HEADER_REPAINT),
          # Shared with the list page so the modal's save callback and the row
          # action callback signal this page the same way.
          dcc.Store(id=ScheduleIds.UPDATE_SIGNAL),
          dmc.Stack(
              gap="xl",
              children=[
                  dmc.SimpleGrid(
                      id=Ids.STATS,
                      cols={"base": 1, "sm": 2, "lg": 4},
                      children=[dmc.Skeleton(height=100) for _ in range(4)],
                  ),
                  dmc.SimpleGrid(
                      cols={"base": 1, "md": 2},
                      spacing="lg",
                      # A short Upcoming Runs card keeps its own height instead
                      # of stretching to the Configuration card's.
                      style={"alignItems": "start"},
                      children=[
                          html.Div(id=Ids.CONFIG_CONTAINER),
                          html.Div(id=Ids.UPCOMING_CONTAINER),
                      ],
                  ),
                  html.Div(id=Ids.RUNS_CONTAINER),
              ],
          ),
          schedule_components.render_schedule_modal(),
      ],
  )


def register_page():
  dash.register_page(
      __name__,
      path_template="/schedules/view/<schedule_id>",
      title="Prism | Schedule",
      layout=layout,
  )
