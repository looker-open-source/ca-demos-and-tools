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
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.ui.components.assertion_components import render_assertion_form_content
from prism.ui.components.page_layout import render_page
from prism.ui.ids import EvaluationIds as Ids


def layout(**_kwargs):
  """Renders the Trial Detail layout."""
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
          # Suggestion Edit Modal
          dmc.Modal(
              id=Ids.TRIAL_SUG_EDIT_MODAL,
              size="80%",
              title="Edit Suggestion",
              children=[
                  render_assertion_form_content(
                      ids_class=type(
                          "TrialSuggestionEditIds",
                          (),
                          {
                              "ASSERT_TYPE": Ids.TRIAL_SUG_EDIT_TYPE,
                              "ASSERT_WEIGHT": Ids.TRIAL_SUG_EDIT_WEIGHT,
                              "ASSERT_VALUE": Ids.TRIAL_SUG_EDIT_VALUE,
                              "ASSERT_YAML": Ids.TRIAL_SUG_EDIT_YAML,
                              "ASSERT_CHART_TYPE": (
                                  Ids.TRIAL_SUG_EDIT_CHART_TYPE
                              ),
                              "ASSERT_GUIDE_CONTAINER": (
                                  Ids.TRIAL_SUG_EDIT_GUIDE_CONTAINER
                              ),
                              "ASSERT_GUIDE_TITLE": (
                                  Ids.TRIAL_SUG_EDIT_GUIDE_TITLE
                              ),
                              "ASSERT_GUIDE_DESC": (
                                  Ids.TRIAL_SUG_EDIT_GUIDE_DESC
                              ),
                              "ASSERT_EXAMPLE_CONTAINER": (
                                  Ids.TRIAL_SUG_EDIT_EXAMPLE_CONTAINER
                              ),
                              "ASSERT_EXAMPLE_VALUE": (
                                  Ids.TRIAL_SUG_EDIT_EXAMPLE_VALUE
                              ),
                              "ASSERT_EXAMPLE_YAML": (
                                  Ids.TRIAL_SUG_EDIT_EXAMPLE_YAML
                              ),
                              "VAL_MSG": Ids.TRIAL_SUG_VAL_MSG,
                          },
                      ),
                      is_edit=True,
                      is_suggestion=True,
                  ),
              ],
          ),
          # Context Store for Edit (Trial ID, Index)
          dash.dcc.Store(id=Ids.TRIAL_SUG_EDIT_CONTEXT),
          # Signal Store for Refresh
          dash.dcc.Store(id=Ids.TRIAL_SUG_UPDATE_SIGNAL, data=0),
          # Loading Store for Skeletons
          dash.dcc.Store(id=Ids.TRIAL_SUG_LOADING_STORE, data=False),
          # Polling for background tasks
          dash.dcc.Interval(
              id=Ids.TRIAL_SUG_POLLING_INTERVAL,
              interval=3000,  # 3 seconds
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
