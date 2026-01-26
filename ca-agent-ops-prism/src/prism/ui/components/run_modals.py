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

"""Run related modals."""

from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.ui.pages.evaluation_ids import EvaluationIds as Ids


def render_compare_run_modal():
  """Renders the Compare Runs modal."""
  return dmc.Modal(
      id=Ids.MODAL_COMPARE_RUNS,
      title="Compare Evaluation Runs",
      size="lg",
      children=[
          dmc.Stack(
              children=[
                  dmc.Text(
                      "Select two runs to compare side-by-side. Only runs"
                      " evaluated on the same dataset are shown.",
                      size="sm",
                      mb="md",
                  ),
                  dmc.Stack(
                      gap=4,
                      children=[
                          dmc.Text("Base Run", size="sm", fw=500),
                          dmc.Select(
                              id=Ids.COMPARE_BASE_SELECT,
                              placeholder="Select Baseline",
                              searchable=True,
                              data=[],
                          ),
                      ],
                  ),
                  dmc.Group(
                      justify="center",
                      my=10,  # Explicit equal vertical margin
                      children=dmc.ActionIcon(
                          DashIconify(icon="material-symbols:swap-vert"),
                          id=Ids.BTN_SWAP_COMPARE_MODAL,
                          variant="default",
                          radius="md",
                          size="lg",
                      ),
                  ),
                  dmc.Stack(
                      gap=4,
                      children=[
                          dmc.Text("Challenger Run", size="sm", fw=500),
                          dmc.Select(
                              id=Ids.COMPARE_CHALLENGE_SELECT,
                              placeholder="Select Challenger",
                              searchable=True,
                              data=[],
                          ),
                      ],
                  ),
                  dmc.Group(
                      justify="flex-end",
                      mt="xl",
                      children=[
                          dmc.Button(
                              "Cancel",
                              id=Ids.BTN_CANCEL_COMPARE,
                              variant="subtle",
                              color="gray",
                          ),
                          dmc.Button(
                              "Compare Runs",
                              id=Ids.BTN_GO_COMPARE,
                              color="indigo",
                          ),
                      ],
                  ),
              ]
          )
      ],
  )
