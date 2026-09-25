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

"""Trial Detail page."""

import dash
from dash import html
import dash_mantine_components as dmc
from prism.ui.components.page_layout import render_page
from prism.ui.ids import EvaluationIds as Ids


def layout(**_kwargs):
  return render_page(
      title="Trial Detail",
      title_id=Ids.TRIAL_TITLE,
      description="Loading trial details...",
      description_id=Ids.TRIAL_DESCRIPTION,
      actions_id=Ids.TRIAL_ACTIONS,
      breadcrumbs_id=Ids.TRIAL_BREADCRUMBS_CONTAINER,
      children=[
          html.Div(
              id=Ids.TRIAL_DETAIL_CONTAINER,
              children=[dmc.Center(children=[dmc.Loader(variant="dots")])],
          ),
          dash.dcc.Store(id=Ids.TRIAL_SUG_UPDATE_SIGNAL, data=0),
          dash.dcc.Store(id=Ids.TRIAL_SUG_LOADING_STORE, data=False),
          # Enabled by the regenerate callback, which hands the work to a
          # thread and has nothing to return until the thread is done.
          dash.dcc.Interval(
              id=Ids.TRIAL_SUG_POLLING_INTERVAL,
              interval=3000,
              disabled=True,
          ),
      ],
  )


def register_page():
  dash.register_page(
      __name__,
      path_template="/evaluations/trials/<trial_id>",
      title="Prism | Trial Detail",
      layout=layout,
  )
