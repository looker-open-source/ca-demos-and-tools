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

"""Callbacks for the Home Dashboard."""

from dash import Input
from dash import Output
from prism.client import get_client
from prism.ui.components.dashboard_components import render_evaluation_chart
from prism.ui.components.dashboard_components import render_run_volume_chart
from prism.ui.components.tables import render_run_table
from prism.ui.pages.home_ids import HomeIds
from prism.ui.utils import typed_callback


@typed_callback(
    [
        Output(HomeIds.CHART_CONTAINER, "children"),
        Output(HomeIds.VOLUME_CHART_CONTAINER, "children"),
        Output(HomeIds.RECENT_RUNS_CONTAINER, "children"),
    ],
    [Input(HomeIds.INTERVAL, "n_intervals")],
)
def update_dashboard(n_intervals: int):
  """Updates dashboard statistics and components."""
  del n_intervals  # The interval is just a timer; its count is unused.

  # Through the singleton, like every other callback. Building a
  # DashboardClient here made a second one every 30s tick.
  stats = get_client().dashboard.get_dashboard_stats()

  chart_data = [item.model_dump() for item in stats.accuracy_history]
  chart = render_evaluation_chart(chart_data)

  volume_data = [item.model_dump() for item in stats.run_volume_history]
  volume_chart = render_run_volume_chart(volume_data)

  # Run names come from the RunSchema, so the table needs no extra lookup.
  #
  # No table_id. This callback writes the children of the div that already
  # carries RECENT_RUNS_CONTAINER, so stamping the same id on the table inside
  # it put two nodes with one id on the page, once per 30s tick.
  recent_runs = render_run_table(stats.recent_runs, table_id=None)

  return (
      chart,
      volume_chart,
      recent_runs,
  )
