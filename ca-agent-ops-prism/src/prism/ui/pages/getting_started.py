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


def _step_card(title: str, description: str, children: list[Any]):
  """Renders a major step in the journey."""
  return dmc.Paper(
      withBorder=True,
      p="xl",
      radius="md",
      shadow="sm",
      mb="xl",
      children=[
          dmc.Group(
              gap="sm",
              mb="md",
              children=[
                  dmc.Title(title, order=4, c="indigo"),
              ],
          ),
          dmc.Text(description, mb="lg", size="md", fw=500),
          *children,
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
    keywords: list[str],
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
                  dmc.Group(
                      gap=4,
                      children=[
                          dmc.Badge(
                              k,
                              size="xs",
                              variant="outline",
                              color="gray",
                              radius="sm",
                              tt="none",
                          )
                          for k in keywords
                      ],
                  ),
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
              ["Simple keyword check", "Logic"],
          ),
          _assertion_item(
              "material-symbols:manage-search",
              "orange",
              "Query Contains",
              "SQL",
              "Checks if the generated SQL contains specific keywords.",
              ["SQL structure", "Logic"],
          ),
          _assertion_item(
              "material-symbols:query-stats",
              "pink",
              "Looker Query Match",
              "LOOKML",
              "Matches Looker query parameters using YAML configuration.",
              ["API parameters", "Logic"],
          ),
          _assertion_item(
              "material-symbols:table-rows",
              "teal",
              "Data Check Row",
              "DATA",
              "Validates values in specific columns of the result row.",
              ["Exact verification", "Data"],
          ),
          _assertion_item(
              "material-symbols:format-list-numbered",
              "cyan",
              "Data Check Row Count",
              "DATA",
              "Checks the number of rows in the result.",
              ["Volume check", "Data"],
          ),
          _assertion_item(
              "material-symbols:bar-chart",
              "indigo",
              "Chart Check Type",
              "CHART",
              "Checks if the chart type matches the expected type.",
              ["Visuals", "Metadata"],
          ),
          _assertion_item(
              "material-symbols:timer",
              "indigo",
              "Latency Limit",
              "PERF",
              "Ensures response time does not exceed threshold.",
              ["Performance", "SLA"],
          ),
          _assertion_item(
              "material-symbols:psychology",
              "grape",
              "AI Judge",
              "LLM",
              "Uses an LLM to evaluate the response based on criteria.",
              ["Semantic", "Vibe Check"],
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
                  # SECTION: YOUR FIRST EVALUATION (The Walkthrough)
                  _section_card(
                      "Your First Evaluation: A 4-Step Guide",
                      [
                          dmc.Text(
                              "Follow these steps to hit the ground running"
                              " with your first benchmark.",
                              mb="lg",
                              c="dimmed",
                              size="sm",
                          ),
                          dmc.Timeline(
                              active=4,
                              bulletSize=36,
                              lineWidth=3,
                              children=[
                                  dmc.TimelineItem(
                                      title="Step 1: Onboard an Agent",
                                      bullet=dmc.Text("1", size="md", fw=700),
                                      children=[
                                          dmc.Text(
                                              "Connect your Gemini model",
                                              c="dimmed",
                                              size="sm",
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
                                              mt="sm",
                                          ),
                                      ],
                                  ),
                                  dmc.TimelineItem(
                                      title="Step 2: Create a Test Suite",
                                      bullet=dmc.Text("2", size="md", fw=700),
                                      children=[
                                          dmc.Text(
                                              "Define your benchmark",
                                              c="dimmed",
                                              size="sm",
                                          ),
                                          dmc.Text(
                                              (
                                                  "Go to 'Test Suites' and"
                                                  " create your first suite."
                                                  " Add a few 'Examples'"
                                                  " (questions) that represent"
                                                  " common user queries for"
                                                  " your data."
                                              ),
                                              size="sm",
                                              mt="sm",
                                          ),
                                      ],
                                  ),
                                  # STEP 3: ADD TEST CASES
                                  dmc.TimelineItem(
                                      title="3. Add Test Cases",
                                      bullet=dmc.Text("3", size="md", fw=700),
                                      children=[
                                          dmc.Text(
                                              "Define specific scenarios",
                                              c="dimmed",
                                              size="sm",
                                          ),
                                          _step_card(
                                              "Choosing the Right Assertion",
                                              (
                                                  "Assertions are the heart of"
                                                  " Prism's automated grading"
                                                  " system. Prism supports a"
                                                  " wide range of checks:"
                                              ),
                                              [
                                                  _render_assertion_list(),
                                                  _deep_dive(
                                                      "Understanding Scoring",
                                                      [
                                                          (
                                                              "Binary"
                                                              " Pass/Fail: Each"
                                                              " assertion"
                                                              " returns 1.0"
                                                              " (Pass) or 0.0"
                                                              " (Fail)."
                                                          ),
                                                          (
                                                              "Accuracy: These"
                                                              " assertions"
                                                              " contribute to"
                                                              " the final"
                                                              " score."
                                                          ),
                                                          (
                                                              "Diagnostic:"
                                                              " Useful for"
                                                              " debugging"
                                                              " (e.g., latency"
                                                              " checks) without"
                                                              " affecting the"
                                                              " agent's grade."
                                                          ),
                                                      ],
                                                  ),
                                                  _pro_tip(
                                                      "Use 'Suggested Asserts'!"
                                                      " Prism automatically"
                                                      " analyzes successful"
                                                      " runs and uses LLMs +"
                                                      " Heuristics to propose"
                                                      " relevant assertions for"
                                                      " you."
                                                  ),
                                              ],
                                          ),
                                      ],
                                  ),
                                  # STEP 4: LAUNCH EVALUATION
                                  dmc.TimelineItem(
                                      title="4. Launch Evaluation",
                                      bullet=dmc.Text("4", size="md", fw=700),
                                      children=[
                                          dmc.Text(
                                              "See the results",
                                              c="dimmed",
                                              size="sm",
                                          ),
                                          dmc.Text(
                                              (
                                                  "Click 'Run Evaluation' from"
                                                  " the Home screen or a Suite"
                                                  " page. Prism will handle the"
                                                  " background execution,"
                                                  " retries, and scoring. Once"
                                                  " finished, dive into the"
                                                  " results!"
                                              ),
                                              size="sm",
                                              mt="sm",
                                          ),
                                      ],
                                  ),
                                  # STEP 5: INFRASTRUCTURE
                                  dmc.TimelineItem(
                                      title=(
                                          "5. Infrastructure: Monitored Agents"
                                      ),
                                      bullet=dmc.Text("5", size="md", fw=700),
                                      children=[
                                          _step_card(
                                              "The Foundation of Evaluation",
                                              (
                                                  "Prism acts as a management"
                                                  " layer for your GDA agents."
                                                  " Your changes here are"
                                                  " persistent and serve as the"
                                                  " source of truth for all"
                                                  " tests."
                                              ),
                                              [
                                                  dmc.Text(
                                                      (
                                                          "When you update an"
                                                          " agent's system"
                                                          " instructions or"
                                                          " metadata in Prism,"
                                                          " we 'Publish' those"
                                                          " changes to the GDA"
                                                          " API for you. This"
                                                          " ensures that when"
                                                          " you run an"
                                                          " evaluation, you're"
                                                          " testing exactly"
                                                          " what you intended."
                                                      ),
                                                      size="sm",
                                                  ),
                                                  _pro_tip(
                                                      "Use 'Monitor Existing'"
                                                      " for production agents"
                                                      " where you only want to"
                                                      " see how they perform"
                                                      " without changing their"
                                                      " configuration."
                                                  ),
                                              ],
                                          )
                                      ],
                                  ),
                                  # STEP 6: BENCHMARKING
                                  dmc.TimelineItem(
                                      title="6. Benchmarking strategies",
                                      bullet=dmc.Text("6", size="md", fw=700),
                                      children=[
                                          _step_card(
                                              "Building Repeatable Benchmarks",
                                              (
                                                  "Test Suites allow you to run"
                                                  " the same set of tests"
                                                  " against different model"
                                                  " versions or prompts."
                                              ),
                                              [
                                                  dmc.Text(
                                                      (
                                                          "Think of a Test"
                                                          " Suite as a"
                                                          " folder/collection"
                                                          " of 'Test Cases'."
                                                          " Each case"
                                                          " represents a"
                                                          " specific question"
                                                          " or scenario you"
                                                          " want to verify."
                                                          " Grouping them into"
                                                          " suites helps you"
                                                          " test specific"
                                                          " capabilities (e.g.,"
                                                          " 'Finance Queries'"
                                                          " vs 'HR Queries')."
                                                      ),
                                                      size="sm",
                                                  ),
                                              ],
                                          )
                                      ],
                                  ),
                                  # STEP 7: VALIDATION
                                  dmc.TimelineItem(
                                      title="7. Validation Logic",
                                      bullet=dmc.Text("7", size="md", fw=700),
                                      children=[
                                          dmc.Text(
                                              (
                                                  "See Step 3 for the detailed"
                                                  " assertion list."
                                              ),
                                              size="sm",
                                              c="dimmed",
                                          )
                                      ],
                                  ),
                                  # STEP 8: EXECUTION
                                  dmc.TimelineItem(
                                      title="8. Execution: Under the Hood",
                                      bullet=dmc.Text("8", size="md", fw=700),
                                      children=[
                                          _step_card(
                                              "How Runs Work",
                                              (
                                                  "When an evaluation starts,"
                                                  " Prism snapshots everything"
                                                  " for absolute consistency."
                                              ),
                                              [
                                                  dmc.Text(
                                                      (
                                                          "Prism runs trials in"
                                                          " parallel background"
                                                          " processes. If an"
                                                          " evaluation is"
                                                          " taking long, it’s"
                                                          " usually because the"
                                                          " agent is 'thinking'"
                                                          " or the data"
                                                          " warehouse is busy."
                                                      ),
                                                      size="sm",
                                                  ),
                                                  _deep_dive(
                                                      "Debug with Trace"
                                                      " Results",
                                                      (
                                                          "Every trial has a"
                                                          " 'Trace' view. This"
                                                          " is your best friend"
                                                          " when debugging. It"
                                                          " shows you the"
                                                          " agent's raw"
                                                          " internal thoughts,"
                                                          " intermediate SQL,"
                                                          " and data result"
                                                          " sets."
                                                      ),
                                                  ),
                                              ],
                                          )
                                      ],
                                  ),
                                  # STEP 9: ITERATION
                                  dmc.TimelineItem(
                                      title=(
                                          "9. Iteration: Interpreting Results"
                                      ),
                                      bullet=dmc.Text("9", size="md", fw=700),
                                      children=[
                                          _step_card(
                                              "Making Sense of the Data",
                                              (
                                                  "Prism isn't just for one-off"
                                                  " tests; it's for iterative"
                                                  " improvement."
                                              ),
                                              [
                                                  dmc.Text(
                                                      (
                                                          "Once you have"
                                                          " multiple runs, use"
                                                          " the Comparison"
                                                          " Dashboard to"
                                                          " perform Delta"
                                                          " Analysis."
                                                      ),
                                                      size="sm",
                                                  ),
                                                  dmc.List(
                                                      spacing="xs",
                                                      size="sm",
                                                      children=[
                                                          dmc.ListItem(
                                                              dmc.Text([
                                                                  dmc.Text(
                                                                      "Regression:",
                                                                      fw=700,
                                                                      span=True,
                                                                      c="red",
                                                                  ),
                                                                  (
                                                                      " Any"
                                                                      " question"
                                                                      " where the"
                                                                      " score"
                                                                      " dropped"
                                                                      " by more"
                                                                      " than 1%."
                                                                  ),
                                                              ])
                                                          ),
                                                          dmc.ListItem(
                                                              dmc.Text([
                                                                  dmc.Text(
                                                                      "Improved:",
                                                                      fw=700,
                                                                      span=True,
                                                                      c="green",
                                                                  ),
                                                                  (
                                                                      " Score"
                                                                      " increased"
                                                                      " by more"
                                                                      " than 1%."
                                                                  ),
                                                              ])
                                                          ),
                                                          dmc.ListItem(
                                                              dmc.Text([
                                                                  dmc.Text(
                                                                      "Stable:",
                                                                      fw=700,
                                                                      span=True,
                                                                      c="dimmed",
                                                                  ),
                                                                  (
                                                                      " Score"
                                                                      " changed"
                                                                      " < 1%."
                                                                  ),
                                                              ])
                                                          ),
                                                      ],
                                                  ),
                                              ],
                                          )
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
