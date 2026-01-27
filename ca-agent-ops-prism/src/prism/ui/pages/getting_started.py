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

"""Getting Started page layout - Ultimate Onboarding Version."""

from typing import Any

import dash
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.ui.components.page_layout import render_page
from prism.ui.pages.getting_started_ids import GettingStartedIds


def _pro_tip(content: str):
  """Renders a 'Pro-Tip' alert."""
  return dmc.Alert(
      content,
      title="Pro-Tip",
      color="blue",
      variant="light",
      radius="md",
      icon=DashIconify(icon="bi:lightbulb", width=18),
      mt="md",
  )


def _deep_dive(title: str, content: str | list[str]):
  """Renders a 'Deep Dive' accordion."""
  if isinstance(content, list):
    content = dmc.List(
        spacing="xs",
        size="sm",
        children=[dmc.ListItem(item) for item in content],
    )
  else:
    content = dmc.Text(content, size="sm")

  return dmc.Accordion(
      variant="separated",
      radius="md",
      mt="md",
      children=[
          dmc.AccordionItem(
              value="item-1",
              children=[
                  dmc.AccordionControl(
                      title,
                      icon=DashIconify(
                          icon="bi:info-circle", color="indigo", width=18
                      ),
                  ),
                  dmc.AccordionPanel(content),
              ],
          )
      ],
  )


def _section_card(title: str, children: list[Any]):
  """Renders a section in a card."""
  return dmc.Paper(
      withBorder=True,
      p="lg",
      radius="md",
      shadow="sm",
      children=[
          dmc.Title(title, order=3, mb="lg", c="indigo"),
          *children,
      ],
  )


def _assertion_item(
    icon: str,
    color: str,
    title: str,
    badge: str,
    desc: str,
):
  """Renders a single assertion list item."""
  return dmc.Group(
      align="start",
      wrap="nowrap",
      mb="sm",
      children=[
          dmc.ThemeIcon(
              DashIconify(icon=icon, width=20),
              size="lg",
              radius="md",
              variant="light",
              color=color,
          ),
          dmc.Stack(
              gap=2,
              children=[
                  dmc.Group(
                      children=[
                          dmc.Text(title, fw=600, size="sm"),
                          dmc.Badge(
                              badge,
                              size="xs",
                              variant="dot",
                              color=color,
                          ),
                      ]
                  ),
                  dmc.Text(desc, size="xs", c="dimmed", lh=1.4),
              ],
          ),
      ],
  )


def _render_assertion_list():
  """Renders the list of supported assertions."""
  return dmc.Stack(
      gap="md",
      mt="md",
      children=[
          _assertion_item(
              "material-symbols:text-fields",
              "blue",
              "Text Contains",
              "STRING",
              "Validates that the response text contains a specific substring.",
          ),
          _assertion_item(
              "material-symbols:manage-search",
              "orange",
              "Query Contains",
              "SQL",
              "Checks if the generated SQL contains specific keywords.",
          ),
          _assertion_item(
              "material-symbols:query-stats",
              "pink",
              "Looker Query Match",
              "LOOKML",
              "Matches Looker query parameters using YAML configuration.",
          ),
          _assertion_item(
              "material-symbols:table-rows",
              "teal",
              "Data Check Row",
              "DATA",
              "Validates values in specific columns of the result row.",
          ),
          _assertion_item(
              "material-symbols:format-list-numbered",
              "cyan",
              "Data Check Row Count",
              "DATA",
              "Checks the number of rows in the result.",
          ),
          _assertion_item(
              "material-symbols:bar-chart",
              "indigo",
              "Chart Check Type",
              "CHART",
              "Checks if the chart type matches the expected type.",
          ),
          _assertion_item(
              "material-symbols:timer",
              "indigo",
              "Latency Limit",
              "PERF",
              "Ensures response time does not exceed threshold.",
          ),
          _assertion_item(
              "material-symbols:psychology",
              "grape",
              "AI Judge",
              "LLM",
              "Uses an LLM to evaluate the response based on criteria.",
          ),
      ],
  )


def layout():
  """Returns the expanded getting started page layout."""
  return render_page(
      title="Welcome to Prism",
      description=(
          "The mission-control for evaluating and perfecting your Gemini Data"
          " Analytics agents. This guide will take you from total novice to"
          " evaluation expert."
      ),
      container_id=GettingStartedIds.ROOT,
      children=[
          dmc.Stack(
              gap="xl",
              children=[
                  # SECTION: GLOSSARY
                  _section_card(
                      "New to Prism? Start Here",
                      [
                          dmc.Text(
                              (
                                  "Prism uses a few key terms to organize your"
                                  " work. Familiarize yourself with these to"
                                  " navigate like a pro."
                              ),
                              size="sm",
                              mb="md",
                          ),
                          dmc.Accordion(
                              variant="contained",
                              radius="md",
                              children=[
                                  dmc.AccordionItem(
                                      value="agent",
                                      children=[
                                          dmc.AccordionControl(
                                              "What is an Agent?"
                                          ),
                                          dmc.AccordionPanel(
                                              "An Agent is your Gemini Data"
                                              " Analytics (GDA) model. It"
                                              " includes the system"
                                              " instructions, data sources, and"
                                              " specific configurations that"
                                              " define its personality and"
                                              " capabilities."
                                          ),
                                      ],
                                  ),
                                  dmc.AccordionItem(
                                      value="suite",
                                      children=[
                                          dmc.AccordionControl(
                                              "What is a Test Suite?"
                                          ),
                                          dmc.AccordionPanel(
                                              "A Test Suite is a collection of"
                                              " 'Examples' (Test Cases) that"
                                              " you want to test your agent"
                                              " against. Think of it as a"
                                              " standardized benchmark for your"
                                              " business use cases."
                                          ),
                                      ],
                                  ),
                                  dmc.AccordionItem(
                                      value="assertion",
                                      children=[
                                          dmc.AccordionControl(
                                              "What is an Assertion?"
                                          ),
                                          dmc.AccordionPanel(
                                              "An Assertion is a specific check"
                                              " (e.g., 'Does the SQL contain"
                                              " GROUP BY?') that Prism performs"
                                              " automatically to see if your"
                                              " agent is behaving correctly."
                                          ),
                                      ],
                                  ),
                                  dmc.AccordionItem(
                                      value="run",
                                      children=[
                                          dmc.AccordionControl(
                                              "What is an Evaluation Run?"
                                          ),
                                          dmc.AccordionPanel(
                                              "An Evaluation Run is the act of"
                                              " execution. When you 'Run' a"
                                              " Suite against an Agent, Prism"
                                              " generates responses for every"
                                              " question and validates them"
                                              " using your assertions."
                                          ),
                                      ],
                                  ),
                              ],
                          ),
                      ],
                  ),
                  # SECTION: GETTING STARTED TIMELINE
                  _section_card(
                      "Getting Started: The Road to Evaluation Mastery",
                      [
                          dmc.Text(
                              "Follow this unified timeline to master the"
                              " platform and start perfecting your agents.",
                              mb="lg",
                              c="dimmed",
                              size="sm",
                          ),
                          dmc.Timeline(
                              active=9,
                              bulletSize=36,
                              lineWidth=3,
                              children=[
                                  # STEP 1: ONBOARD AGENT
                                  dmc.TimelineItem(
                                      title="1. Onboard an Agent",
                                      bullet=DashIconify(
                                          icon="bi:robot", width=20
                                      ),
                                      children=[
                                          dmc.Text(
                                              "Connect your Gemini model",
                                              c="dimmed",
                                              size="xs",
                                              fw=500,
                                          ),
                                          dmc.Text(
                                              (
                                                  "Navigate to 'Agents' and"
                                                  " click 'Onboard New Agent'."
                                                  " You can either create a"
                                                  " fresh configuration or"
                                                  " monitor an existing one"
                                                  " already deployed in GDA."
                                              ),
                                              size="sm",
                                              mt="xs",
                                          ),
                                          _pro_tip(
                                              "Use 'Monitor Existing' for"
                                              " production agents where you"
                                              " only want to see how they"
                                              " perform without changing"
                                              " their configuration."
                                          ),
                                      ],
                                  ),
                                  # STEP 2: CREATE SUITE
                                  dmc.TimelineItem(
                                      title="2. Create a Test Suite",
                                      bullet=DashIconify(
                                          icon="bi:journal-text", width=20
                                      ),
                                      children=[
                                          dmc.Text(
                                              "Define your benchmark",
                                              c="dimmed",
                                              size="xs",
                                              fw=500,
                                          ),
                                          dmc.Text(
                                              (
                                                  "Go to 'Test Suites' and"
                                                  " create your first suite."
                                                  " Add a few 'Examples'"
                                                  " (questions) that represent"
                                                  " common user queries for"
                                                  " your data. Grouping them"
                                                  " into suites helps you test"
                                                  " specific capabilities"
                                                  " (e.g., 'Finance Queries')."
                                              ),
                                              size="sm",
                                              mt="xs",
                                          ),
                                      ],
                                  ),
                                  # STEP 3: DEFINE ASSERTIONS
                                  dmc.TimelineItem(
                                      title="3. Define Test Cases & Assertions",
                                      bullet=DashIconify(
                                          icon="bi:check2-square", width=20
                                      ),
                                      children=[
                                          dmc.Text(
                                              "The heart of Prism",
                                              c="dimmed",
                                              size="xs",
                                              fw=500,
                                          ),
                                          dmc.Text(
                                              (
                                                  "Assertions are automated"
                                                  " checks that Prism"
                                                  " performs. We support a wide"
                                                  " range of logic and data"
                                                  " checks:"
                                              ),
                                              size="sm",
                                              mt="xs",
                                          ),
                                          _render_assertion_list(),
                                          _deep_dive(
                                              "Scoring Mechanisms",
                                              [
                                                  (
                                                      "Binary Pass/Fail: Each"
                                                      " assertion returns 1.0"
                                                      " (Pass) or 0.0 (Fail)."
                                                  ),
                                                  (
                                                      "Accuracy: These"
                                                      " assertions contribute"
                                                      " to the final score."
                                                  ),
                                                  (
                                                      "Diagnostic: Useful for"
                                                      " debugging (e.g.,"
                                                      " latency) without"
                                                      " affecting the grade."
                                                  ),
                                              ],
                                          ),
                                          _pro_tip(
                                              "Use 'Suggested Asserts'!"
                                              " Prism automatically"
                                              " analyzes successful runs and"
                                              " proposes relevant assertions"
                                              " for you."
                                          ),
                                      ],
                                  ),
                                  # STEP 4: INFRASTRUCTURE
                                  dmc.TimelineItem(
                                      title="4. Infrastructure & Publishing",
                                      bullet=DashIconify(
                                          icon="bi:cpu", width=20
                                      ),
                                      children=[
                                          dmc.Text(
                                              "Source of Truth",
                                              c="dimmed",
                                              size="xs",
                                              fw=500,
                                          ),
                                          dmc.Text(
                                              (
                                                  "When you update an agent's"
                                                  " system instructions or"
                                                  " metadata in Prism, we"
                                                  " 'Publish' those changes to"
                                                  " the GDA API for you. This"
                                                  " ensures consistency between"
                                                  " your configuration and"
                                                  " evaluation."
                                              ),
                                              size="sm",
                                              mt="xs",
                                          ),
                                      ],
                                  ),
                                  # STEP 5: LAUNCH EVALUATION
                                  dmc.TimelineItem(
                                      title="5. Launch Evaluation",
                                      bullet=DashIconify(
                                          icon="bi:play-circle-fill", width=20
                                      ),
                                      children=[
                                          dmc.Text(
                                              "Execution Engine",
                                              c="dimmed",
                                              size="xs",
                                              fw=500,
                                          ),
                                          dmc.Text(
                                              (
                                                  "Click 'Run Evaluation'."
                                                  " Prism snapshots your"
                                                  " configuration and runs"
                                                  " trials in parallel"
                                                  " background processes for"
                                                  " maximum efficiency."
                                              ),
                                              size="sm",
                                              mt="xs",
                                          ),
                                      ],
                                  ),
                                  # STEP 6: DEBUGGING
                                  dmc.TimelineItem(
                                      title="6. Debug with Trace Results",
                                      bullet=DashIconify(
                                          icon="bi:bug", width=20
                                      ),
                                      children=[
                                          dmc.Text(
                                              "Under the Hood",
                                              c="dimmed",
                                              size="xs",
                                              fw=500,
                                          ),
                                          dmc.Text(
                                              (
                                                  "Every trial has a 'Trace'"
                                                  " view. It shows you the"
                                                  " agent's raw internal"
                                                  " thoughts, intermediate SQL,"
                                                  " and full data result sets."
                                              ),
                                              size="sm",
                                              mt="xs",
                                          ),
                                      ],
                                  ),
                                  # STEP 7: ITERATION
                                  dmc.TimelineItem(
                                      title="7. Delta Analysis & Regression",
                                      bullet=DashIconify(
                                          icon="bi:graph-up-arrow", width=20
                                      ),
                                      children=[
                                          dmc.Text(
                                              "Interpretation",
                                              c="dimmed",
                                              size="xs",
                                              fw=500,
                                          ),
                                          dmc.Text(
                                              (
                                                  "Use the Comparison Dashboard"
                                                  " to perform Delta Analysis."
                                                  " Track Regressions (drops >"
                                                  " 1%) and Improvements"
                                                  " across multiple runs."
                                              ),
                                              size="sm",
                                              mt="xs",
                                          ),
                                      ],
                                  ),
                              ],
                          ),
                      ],
                  ),
              ],
          ),
          dmc.Center(
              mt="xl",
              children=[
                  dmc.Anchor(
                      dmc.Button(
                          "Ready to Start? Go Home",
                          size="lg",
                          radius="md",
                          variant="filled",
                          color="indigo",
                          leftSection=DashIconify(icon="bi:house"),
                      ),
                      href="/",
                      underline=False,
                  )
              ],
          ),
      ],
  )


def register_page():
  dash.register_page(
      __name__,
      path="/getting-started",
      title="Prism | Getting Started Guide",
      layout=layout,
  )
