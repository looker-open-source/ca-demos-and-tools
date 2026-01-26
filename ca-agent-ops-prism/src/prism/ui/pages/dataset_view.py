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

"""Page for viewing a dataset in read-only mode."""

import dash
from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.client import get_client
from prism.ui.components import dataset_components
from prism.ui.components.badges import render_coverage_badge
from prism.ui.components.page_layout import render_page
from prism.ui.models import ui_state
from prism.ui.pages.dataset_ids import DatasetIds as Ids
from prism.ui.pages.evaluation_ids import EvaluationIds


def _meta_item(label, value, icon=None, mono=False):
  return dmc.Stack(
      gap=4,
      children=[
          dmc.Text(
              label,
              size="xs",
              c="dimmed",
              tt="uppercase",
              fw=700,
              lts=0.5,
          ),
          dmc.Group(
              gap=6,
              children=[
                  (
                      DashIconify(icon=icon, width=16, color="gray")
                      if icon
                      else None
                  ),
                  dmc.Text(
                      value,
                      size="sm",
                      fw=500,
                      className="font-mono" if mono else "",
                  ),
              ],
          ),
      ],
  )


def layout(dataset_id: str = None):
  """Renders the View Dataset layout (read-only)."""
  if not dataset_id:
    return dmc.Text("Invalid Dataset ID", c="red")

  dataset_id_int = int(dataset_id)

  client = get_client()
  suite = client.suites.get_suite(dataset_id_int)
  examples = client.suites.list_examples(dataset_id_int) or []

  # Convert examples to List[SuiteQuestion] for rendering
  questions = []
  for e in examples:
    questions.append(
        ui_state.SuiteQuestion(
            id=e.id,
            question=e.question,
            asserts=[
                (a.model_dump() if hasattr(a, "model_dump") else a)
                for a in e.asserts or []
            ],
        )
    )

  if not suite:
    return dmc.Container(
        dmc.Alert("Dataset not found", color="red"), size="xl", py="xl"
    )

  # Calculate Assertion Coverage
  total_questions = len(questions)
  questions_with_asserts = sum(1 for q in questions if q.asserts)

  if total_questions == 0:
    coverage_status = "No Test Cases"
    coverage_color = "gray"
  elif questions_with_asserts == total_questions:
    coverage_status = "Full Coverage"
    coverage_color = "green"
  elif questions_with_asserts > 0:
    coverage_status = "Partial Coverage"
    coverage_color = "yellow"
  else:
    coverage_status = "No Coverage"
    coverage_color = "orange"

  last_updated_str = (
      suite.modified_at.strftime("%Y-%m-%d %H:%M")
      if suite.modified_at
      else suite.created_at.strftime("%Y-%m-%d %H:%M")
  )

  unified_header_card = dmc.Paper(
      withBorder=True,
      radius="md",
      p="lg",
      shadow="sm",
      mb="xl",
      children=[
          dmc.SimpleGrid(
              cols={"base": 2, "md": 4},
              spacing="md",
              children=[
                  dmc.Stack(
                      gap=4,
                      children=[
                          dmc.Text(
                              "Assertion Coverage",
                              size="xs",
                              c="dimmed",
                              tt="uppercase",
                              fw=700,
                              lts=0.5,
                          ),
                          render_coverage_badge(
                              coverage_status, coverage_color, size="sm"
                          ),
                      ],
                  ),
                  _meta_item(
                      "Test Cases",
                      str(total_questions),
                  ),
                  _meta_item(
                      "Created At",
                      suite.created_at.strftime("%Y-%m-%d"),
                      icon="bi:calendar-event",
                  ),
                  _meta_item(
                      "Last Updated",
                      last_updated_str,
                      icon="bi:clock",
                  ),
              ],
          ),
      ],
  )

  return render_page(
      title=suite.name,
      description=(
          suite.description
          if suite.description
          else "View details, metadata, and test cases for this test suite."
      ),
      actions=[
          dmc.Button(
              "Edit Test Suite",
              id=Ids.BTN_CONFIG_EDIT,
              leftSection=DashIconify(icon="material-symbols:edit", width=20),
              variant="default",
              radius="md",
          ),
          dmc.Button(
              "Run Evaluation",
              id=EvaluationIds.BTN_OPEN_RUN_MODAL,
              leftSection=DashIconify(icon="bi:play-fill", width=20),
              color="blue",
              radius="md",
          ),
      ],
      breadcrumbs=dmc.Breadcrumbs(
          separator="/",
          children=[
              dmc.Anchor(
                  "Test Suites",
                  href="/test_suites",
                  size="sm",
                  fw=500,
              ),
              dmc.Text("Test Suite Details", size="sm", fw=500, c="dimmed"),
          ],
      ),
      children=[
          unified_header_card,
          # Main Content Grid
          dmc.Grid(
              gutter="xl",
              children=[
                  # Full-width Test Cases Grid
                  dmc.GridCol(
                      span=12,
                      children=[
                          dmc.Group(
                              justify="space-between",
                              mb="md",
                              children=[
                                  dmc.Title("Test Cases", order=3),
                                  dmc.Group(
                                      gap="xs",
                                      children=[
                                          dmc.Anchor(
                                              dmc.Button(
                                                  "Add Test Case",
                                                  leftSection=DashIconify(
                                                      icon="bi:plus-lg",
                                                      width=20,
                                                  ),
                                                  variant="light",
                                                  radius="md",
                                              ),
                                              href=f"/test_suites/edit/{dataset_id}?action=add",
                                              underline=False,
                                          ),
                                          dmc.Anchor(
                                              dmc.Button(
                                                  "Edit Test Cases",
                                                  leftSection=DashIconify(
                                                      icon="bi:collection-play",
                                                      width=20,
                                                  ),
                                                  variant="default",
                                                  radius="md",
                                              ),
                                              href=f"/test_suites/edit/{dataset_id}",
                                              underline=False,
                                          ),
                                      ],
                                  ),
                              ],
                          ),
                          html.Div(
                              id=Ids.QUESTION_LIST,
                              children=render_questions_content(
                                  questions, dataset_id_int
                              ),
                          ),
                      ],
                  ),
              ],
          ),
          # Hidden stores & placeholders
          dash.dcc.Store(id=Ids.STORE_BUILDER, data=[]),
          dash.dcc.Store(id=Ids.STORE_MODAL, data={}),
          dmc.Select(id=Ids.AGENT_SELECT, style={"display": "none"}),
          html.Div(id=Ids.SAVE_NEW_BTN, style={"display": "none"}),
          html.Div(id=Ids.SAVE_EDIT_BTN, style={"display": "none"}),
          html.Div(id=Ids.CANCEL_NEW_BTN, style={"display": "none"}),
          html.Div(id=Ids.CANCEL_EDIT_BTN, style={"display": "none"}),
          html.Div(id=Ids.PLACEHOLDER_SAVE_BTN, style={"display": "none"}),
          html.Div(id=Ids.MODAL_QUESTION),
          html.Div(id=Ids.MODAL_BULK),
          html.Div(id=Ids.MODAL_DELETE),
          dash.dcc.Store(id="selected-question-index", data=None),
          html.Div(id=Ids.ADD_QUESTION_BTN, style={"display": "none"}),
          # Edit Configuration Modal
          render_config_edit_modal(Ids.MODAL_CONFIG_SAVE_BTN),
          # Run Evaluation Modal
          render_run_eval_modal(),
      ],
  )


def render_questions_content(questions, dataset_id: int):
  """Renders the questions content area."""
  if not questions:
    return []
  return [
      dmc.Anchor(
          dataset_components.render_question_card(q, i, read_only=True),
          href=f"/test_suites/edit/{dataset_id}?test_case_id={q.id}",
          underline=False,
          c="inherit",
          style={"display": "block", "textDecoration": "none"},
      )
      for i, q in enumerate(questions)
  ]


def render_run_eval_modal():
  """Renders the Run Evaluation modal."""
  return dmc.Modal(
      id=EvaluationIds.MODAL_RUN_EVAL,
      title="Run Evaluation",
      size="xl",
      radius="md",
      centered=True,
      children=[
          dmc.Stack(
              gap="lg",
              children=[
                  dmc.Select(
                      id=EvaluationIds.AGENT_SELECT,
                      label="Select Agent",
                      placeholder="Search agents...",
                      data=[],
                      searchable=True,
                  ),
                  html.Div(id=EvaluationIds.AGENT_DETAILS),
                  dmc.Group(
                      justify="flex-end",
                      children=[
                          dmc.Button(
                              "Cancel",
                              id=EvaluationIds.BTN_CANCEL_RUN,
                              variant="subtle",
                          ),
                          dmc.Button(
                              "Start Run", id=EvaluationIds.BTN_START_RUN
                          ),
                      ],
                  ),
              ],
          )
      ],
  )


def render_config_edit_modal(save_btn_id: str):
  """Renders the Edit Configuration modal."""
  return dmc.Modal(
      id=Ids.MODAL_CONFIG_EDIT,
      size="lg",
      radius="md",
      padding="xl",
      withCloseButton=False,
      children=[
          dmc.Group(
              justify="space-between",
              mb="lg",
              children=[
                  dmc.Title("Edit Test Suite", order=3),
                  dmc.ActionIcon(
                      DashIconify(icon="material-symbols:close"),
                      id=Ids.MODAL_CONFIG_CLOSE_BTN_X,
                      variant="subtle",
                      color="gray",
                  ),
              ],
          ),
          dmc.Stack(
              gap="xl",
              children=[
                  dmc.TextInput(id=Ids.NAME, label="Dataset Name"),
                  dmc.Textarea(id=Ids.DESC, label="Description", minRows=3),
                  dmc.Group(
                      justify="flex-end",
                      children=[
                          dmc.Button(
                              "Cancel",
                              id=Ids.MODAL_CONFIG_CANCEL_BTN,
                              variant="subtle",
                          ),
                          dmc.Button("Save", id=save_btn_id),
                      ],
                  ),
              ],
          ),
      ],
  )


def register_page():
  dash.register_page(
      __name__,
      path_template="/test_suites/view/<dataset_id>",
      title="Prism | View Dataset",
      layout=layout,
  )
