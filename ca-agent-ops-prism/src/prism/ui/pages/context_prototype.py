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

"""Agent Context Prototype Page."""

import dash
from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.ui.pages.context_prototype_ids import ContextPrototypeIds as Ids


def render_bq_table_row(index: int, table_fqn: str = ""):
  """Renders a single BigQuery table input row."""
  return dmc.Group(
      id=Ids.bq_table_row(index),
      mb="sm",
      children=[
          dmc.TextInput(
              placeholder="project.dataset.table",
              value=table_fqn,
              id=Ids.bq_table_input(index),
              radius="md",
              style={"flex": 1},
          ),
          dmc.ActionIcon(
              DashIconify(icon="material-symbols:delete-outline", width=18),
              color="red",
              variant="subtle",
              id=Ids.bq_table_delete(index),
          ),
      ],
  )


def render_looker_explore_row(index: int, model: str = "", explore: str = ""):
  """Renders a single Looker explore input row."""
  return dmc.Group(
      id=Ids.looker_explore_row(index),
      mb="sm",
      children=[
          dmc.TextInput(
              placeholder="Model Name",
              value=model,
              id=Ids.looker_explore_model(index),
              radius="md",
              style={"flex": 1},
          ),
          dmc.TextInput(
              placeholder="Explore Name",
              value=explore,
              id=Ids.looker_explore_name(index),
              radius="md",
              style={"flex": 1},
          ),
          dmc.ActionIcon(
              DashIconify(icon="material-symbols:delete-outline", width=18),
              color="red",
              variant="subtle",
              id=Ids.looker_explore_delete(index),
          ),
      ],
  )


def render_example_row(index: int, question: str = "", sql: str = ""):
  """Renders a single example query row."""
  return dmc.Paper(
      id=Ids.example_row(index),
      p="md",
      radius="md",
      withBorder=True,
      bg="gray.0",
      mb="sm",
      children=dmc.Stack(
          children=[
              dmc.Group(
                  justify="space-between",
                  children=[
                      dmc.Group(
                          gap="xs",
                          children=[
                              DashIconify(
                                  icon="material-symbols:quiz-outline",
                                  width=20,
                                  color="blue",
                              ),
                              dmc.Text(
                                  f"SQL Example #{index + 1}", fw=600, size="sm"
                              ),
                          ],
                      ),
                      dmc.ActionIcon(
                          DashIconify(
                              icon="material-symbols:delete-outline", width=18
                          ),
                          color="red",
                          variant="subtle",
                          id=Ids.example_delete(index),
                      ),
                  ],
              ),
              dmc.TextInput(
                  label="Natural Language Test Case",
                  placeholder="e.g. How many users signed up last week?",
                  value=question,
                  id=Ids.example_question(index),
                  radius="md",
              ),
              dmc.Textarea(
                  label="SQL Query",
                  placeholder="SELECT count(*) FROM users WHERE...",
                  value=sql,
                  id=Ids.example_sql(index),
                  minRows=2,
                  autosize=True,
                  radius="md",
                  styles={
                      "input": {"fontFamily": "monospace", "fontSize": "13px"}
                  },
              ),
          ]
      ),
  )


def render_golden_row(
    index: int, questions: list[str] = None, model: str = "", explore: str = ""
):
  """Renders a single Looker golden query row."""
  qs_str = "\n".join(questions) if questions else ""
  return dmc.Paper(
      id=Ids.golden_row(index),
      p="md",
      radius="md",
      withBorder=True,
      bg="gray.0",
      mb="sm",
      children=dmc.Stack(
          children=[
              dmc.Group(
                  justify="space-between",
                  children=[
                      dmc.Group(
                          gap="xs",
                          children=[
                              DashIconify(
                                  icon="material-symbols:star-outline",
                                  width=20,
                                  color="orange",
                              ),
                              dmc.Text(
                                  f"Looker Golden Query #{index + 1}",
                                  fw=600,
                                  size="sm",
                              ),
                          ],
                      ),
                      dmc.ActionIcon(
                          DashIconify(
                              icon="material-symbols:delete-outline", width=18
                          ),
                          color="red",
                          variant="subtle",
                          id=Ids.golden_delete(index),
                      ),
                  ],
              ),
              dmc.Textarea(
                  label="Natural Language Test Cases (One per line)",
                  placeholder="How many orders?\nTotal sales for last month",
                  value=qs_str,
                  id=Ids.golden_questions(index),
                  minRows=2,
                  autosize=True,
                  radius="md",
              ),
              dmc.SimpleGrid(
                  cols=2,
                  children=[
                      dmc.TextInput(
                          label="Model",
                          value=model,
                          id=Ids.golden_model(index),
                          radius="md",
                      ),
                      dmc.TextInput(
                          label="Explore",
                          value=explore,
                          id=Ids.golden_explore(index),
                          radius="md",
                      ),
                  ],
              ),
          ]
      ),
  )


def render_glossary_row(index: int, term: str = "", description: str = ""):
  """Renders a single glossary term row."""
  return dmc.Paper(
      id=Ids.glossary_row(index),
      p="md",
      radius="md",
      withBorder=True,
      bg="gray.0",
      mb="sm",
      children=dmc.Stack(
          children=[
              dmc.Group(
                  justify="space-between",
                  children=[
                      dmc.Group(
                          gap="xs",
                          children=[
                              DashIconify(
                                  icon="material-symbols:menu-book-outline",
                                  width=20,
                                  color="teal",
                              ),
                              dmc.Text(
                                  f"Glossary Term #{index + 1}",
                                  fw=600,
                                  size="sm",
                              ),
                          ],
                      ),
                      dmc.ActionIcon(
                          DashIconify(
                              icon="material-symbols:delete-outline", width=18
                          ),
                          color="red",
                          variant="subtle",
                          id=Ids.glossary_delete(index),
                      ),
                  ],
              ),
              dmc.SimpleGrid(
                  cols=2,
                  children=[
                      dmc.TextInput(
                          label="Term (Display Name)",
                          placeholder="e.g. YTD Revenue",
                          value=term,
                          id=Ids.glossary_term(index),
                          radius="md",
                      ),
                      dmc.TextInput(
                          label="Description",
                          placeholder="Year-to-date revenue calculated from...",
                          value=description,
                          id=Ids.glossary_desc(index),
                          radius="md",
                      ),
                  ],
              ),
          ]
      ),
  )


def render_relation_row(
    index: int,
    left_table: str = "",
    left_cols: str = "",
    right_table: str = "",
    right_cols: str = "",
):
  """Renders a single schema relationship row."""
  return dmc.Paper(
      id=Ids.relation_row(index),
      p="md",
      radius="md",
      withBorder=True,
      bg="gray.0",
      mb="sm",
      children=dmc.Stack(
          children=[
              dmc.Group(
                  justify="space-between",
                  children=[
                      dmc.Group(
                          gap="xs",
                          children=[
                              DashIconify(
                                  icon="material-symbols:link",
                                  width=20,
                                  color="indigo",
                              ),
                              dmc.Text(
                                  f"Schema Relationship #{index + 1}",
                                  fw=600,
                                  size="sm",
                              ),
                          ],
                      ),
                      dmc.ActionIcon(
                          DashIconify(
                              icon="material-symbols:delete-outline", width=18
                          ),
                          color="red",
                          variant="subtle",
                          id=Ids.relation_delete(index),
                      ),
                  ],
              ),
              dmc.SimpleGrid(
                  cols=2,
                  children=[
                      dmc.Stack(
                          gap="xs",
                          children=[
                              dmc.TextInput(
                                  label="Left Table FQN",
                                  value=left_table,
                                  id=Ids.relation_left_table(index),
                                  radius="md",
                              ),
                              dmc.TextInput(
                                  label="Join Columns (comma separated)",
                                  value=left_cols,
                                  id=Ids.relation_left_cols(index),
                                  radius="md",
                              ),
                          ],
                      ),
                      dmc.Stack(
                          gap="xs",
                          children=[
                              dmc.TextInput(
                                  label="Right Table FQN",
                                  value=right_table,
                                  id=Ids.relation_right_table(index),
                                  radius="md",
                              ),
                              dmc.TextInput(
                                  label="Join Columns (comma separated)",
                                  value=right_cols,
                                  id=Ids.relation_right_cols(index),
                                  radius="md",
                              ),
                          ],
                      ),
                  ],
              ),
          ]
      ),
  )


def render_context_summary(data: dict):
  """Renders an elegant, concise summary card of the agent context."""
  ds_refs = data.get("datasource_references", {})
  ds_type = (
      "BigQuery"
      if "bq" in ds_refs
      else "Looker"
      if "looker" in ds_refs
      else "None"
  )

  # Metrics
  num_bq_tables = len(ds_refs.get("bq", {}).get("table_references", []))
  num_looker_explores = len(
      ds_refs.get("looker", {}).get("explore_references", [])
  )
  num_examples = len(data.get("example_queries", []))
  num_golden = len(data.get("looker_golden_queries", []))
  num_glossary = len(data.get("glossary_terms", []))
  num_relations = len(data.get("schema_relationships", []))
  python_enabled = (
      data.get("options", {})
      .get("analysis", {})
      .get("python", {})
      .get("enabled", False)
  )
  max_bytes = (
      data.get("options", {})
      .get("datasource", {})
      .get("big_query_max_billed_bytes")
  )

  def summary_stat(icon, label, value, color="blue"):
    return dmc.Group(
        gap="xs",
        children=[
            dmc.ThemeIcon(
                DashIconify(icon=icon, width=16),
                variant="light",
                color=color,
                size="sm",
                radius="sm",
            ),
            dmc.Stack(
                gap=0,
                children=[
                    dmc.Text(
                        label, size="10px", c="dimmed", fw=600, tt="uppercase"
                    ),
                    dmc.Text(value, size="sm", fw=600),
                ],
            ),
        ],
    )

  return dmc.Card(
      p="lg",
      radius="md",
      withBorder=True,
      children=[
          dmc.Stack(
              gap="md",
              children=[
                  dmc.Group(
                      justify="space-between",
                      children=[
                          dmc.Group(
                              children=[
                                  dmc.Avatar(
                                      DashIconify(
                                          icon=(
                                              "material-symbols:robot-2-outline"
                                          )
                                      ),
                                      color="blue",
                                      radius="md",
                                  ),
                                  dmc.Stack(
                                      gap=0,
                                      children=[
                                          dmc.Text(
                                              "Agent Personality & Logic",
                                              fw=700,
                                              size="md",
                                          ),
                                          dmc.Text(
                                              "System Instruction: "
                                              + (
                                                  data.get(
                                                      "system_instruction"
                                                  )[:60]
                                                  + "..."
                                                  if data.get(
                                                      "system_instruction"
                                                  )
                                                  else "Not set"
                                              ),
                                              size="xs",
                                              c="dimmed",
                                              lineClamp=1,
                                          ),
                                      ],
                                  ),
                              ]
                          ),
                          dmc.Badge(
                              "Active Calibration",
                              variant="dot",
                              color="green",
                              size="sm",
                          ),
                      ],
                  ),
                  dmc.Divider(variant="dotted"),
                  dmc.SimpleGrid(
                      cols=4,
                      children=[
                          # Column 1: Datasources
                          dmc.Stack(
                              gap="sm",
                              children=[
                                  dmc.Text(
                                      "Datasources", size="xs", fw=700, c="blue"
                                  ),
                                  summary_stat(
                                      "material-symbols:database",
                                      "Type",
                                      ds_type,
                                      color="blue",
                                  ),
                                  summary_stat(
                                      "material-symbols:table-view",
                                      "Reach",
                                      f"{num_bq_tables} Tables"
                                      if ds_type == "BigQuery"
                                      else f"{num_looker_explores} Explores",
                                      color="blue",
                                  ),
                              ],
                          ),
                          # Column 2: Tuning
                          dmc.Stack(
                              gap="sm",
                              children=[
                                  dmc.Text(
                                      "Tuning", size="xs", fw=700, c="orange"
                                  ),
                                  summary_stat(
                                      "material-symbols:quiz",
                                      "SQL Examples",
                                      f"{num_examples} items",
                                      color="orange",
                                  ),
                                  summary_stat(
                                      "material-symbols:star",
                                      "Golden Queries",
                                      f"{num_golden} items",
                                      color="orange",
                                  ),
                              ],
                          ),
                          # Column 3: Knowledge
                          dmc.Stack(
                              gap="sm",
                              children=[
                                  dmc.Text(
                                      "Knowledge", size="xs", fw=700, c="teal"
                                  ),
                                  summary_stat(
                                      "material-symbols:menu-book",
                                      "Glossary",
                                      f"{num_glossary} terms",
                                      color="teal",
                                  ),
                                  summary_stat(
                                      "material-symbols:link",
                                      "Relations",
                                      f"{num_relations} hints",
                                      color="teal",
                                  ),
                              ],
                          ),
                          # Column 4: Capabilities
                          dmc.Stack(
                              gap="sm",
                              children=[
                                  dmc.Text(
                                      "Capabilities",
                                      size="xs",
                                      fw=700,
                                      c="indigo",
                                  ),
                                  summary_stat(
                                      "material-symbols:terminal",
                                      "Python",
                                      "Enabled"
                                      if python_enabled
                                      else "Disabled",
                                      color="indigo",
                                  ),
                                  summary_stat(
                                      "material-symbols:speed",
                                      "BQ Limit",
                                      f"{max_bytes/1e9:.1f} GB"
                                      if max_bytes
                                      else "Unlimited",
                                      color="indigo",
                                  ),
                              ],
                          ),
                      ],
                  ),
              ],
          )
      ],
  )


def layout():
  """Returns the layout for the context prototype page."""
  return dmc.Container(
      size="lg",
      py="xl",
      children=[
          dash.dcc.Store(
              id=Ids.STORE_STATE,
              data={
                  "examples": 1,
                  "glossary": 1,
                  "golden": 1,
                  "relations": 0,
                  "bq_tables": 1,
                  "looker_explores": 1,
              },
          ),
          dmc.Stack(
              gap="lg",
              children=[
                  dmc.Group(
                      justify="space-between",
                      children=[
                          dmc.Stack(
                              gap=0,
                              children=[
                                  dmc.Title("Full GDA Context Editor", order=2),
                                  dmc.Text(
                                      "Comprehensive interface for all agent"
                                      " context fields",
                                      c="dimmed",
                                      size="sm",
                                  ),
                              ],
                          ),
                          dmc.Button(
                              "Publish Context",
                              id=Ids.BTN_SAVE,
                              leftSection=DashIconify(
                                  icon="material-symbols:publish"
                              ),
                              radius="md",
                              size="md",
                          ),
                      ],
                  ),
                  dmc.Tabs(
                      id=Ids.TABS,
                      value="datasources",
                      variant="pills",
                      radius="md",
                      children=[
                          dmc.TabsList(
                              mb="xl",
                              children=[
                                  dmc.TabsTab(
                                      "Datasources",
                                      value="datasources",
                                      leftSection=DashIconify(
                                          icon="material-symbols:database"
                                      ),
                                  ),
                                  dmc.TabsTab(
                                      "Instructions",
                                      value="instruction",
                                      leftSection=DashIconify(
                                          icon="material-symbols:description-outline"
                                      ),
                                  ),
                                  dmc.TabsTab(
                                      "Examples",
                                      value="examples",
                                      leftSection=DashIconify(
                                          icon="material-symbols:quiz-outline"
                                      ),
                                  ),
                                  dmc.TabsTab(
                                      "Knowledge",
                                      value="knowledge",
                                      leftSection=DashIconify(
                                          icon="material-symbols:menu-book-outline"
                                      ),
                                  ),
                                  dmc.TabsTab(
                                      "Advanced",
                                      value="advanced",
                                      leftSection=DashIconify(
                                          icon="material-symbols:settings-outline"
                                      ),
                                  ),
                              ],
                          ),
                          # --- DATASOURCES PANEL ---
                          dmc.TabsPanel(
                              value="datasources",
                              children=dmc.Paper(
                                  p="xl",
                                  radius="md",
                                  children=dmc.Stack(
                                      children=[
                                          dmc.Text(
                                              "Agent Datasources",
                                              fw=600,
                                              size="lg",
                                          ),
                                          dmc.SegmentedControl(
                                              id=Ids.SELECT_DS_TYPE,
                                              value="bq",
                                              data=[
                                                  {
                                                      "label": "BigQuery",
                                                      "value": "bq",
                                                  },
                                                  {
                                                      "label": "Looker",
                                                      "value": "looker",
                                                  },
                                              ],
                                              radius="md",
                                              fullWidth=True,
                                          ),
                                          # BigQuery Section
                                          html.Div(
                                              id="section-bq-ds",
                                              children=dmc.Stack(
                                                  children=[
                                                      dmc.Text(
                                                          "Tables",
                                                          fw=500,
                                                          size="sm",
                                                      ),
                                                      html.Div(
                                                          id=Ids.BQ_TABLE_LIST
                                                      ),
                                                      dmc.Button(
                                                          "Add Table",
                                                          id=Ids.BTN_ADD_BQ_TABLE,
                                                          variant="light",
                                                          size="xs",
                                                          radius="md",
                                                          leftSection=DashIconify(
                                                              icon="material-symbols:add"
                                                          ),
                                                      ),
                                                  ]
                                              ),
                                          ),
                                          # Looker Section
                                          html.Div(
                                              id="section-looker-ds",
                                              style={"display": "none"},
                                              children=dmc.Stack(
                                                  children=[
                                                      dmc.TextInput(
                                                          label=(
                                                              "Looker"
                                                              " Instance URI"
                                                          ),
                                                          id=Ids.LOOKER_URI,
                                                          placeholder="https://myinstance.looker.com",
                                                          radius="md",
                                                      ),
                                                      dmc.Text(
                                                          "Explores",
                                                          fw=500,
                                                          size="sm",
                                                      ),
                                                      html.Div(
                                                          id=Ids.LOOKER_EXPLORE_LIST
                                                      ),
                                                      dmc.Button(
                                                          "Add Explore",
                                                          id=Ids.BTN_ADD_LOOKER_EXPLORE,
                                                          variant="light",
                                                          size="xs",
                                                          radius="md",
                                                          leftSection=DashIconify(
                                                              icon="material-symbols:add"
                                                          ),
                                                      ),
                                                  ]
                                              ),
                                          ),
                                      ]
                                  ),
                              ),
                          ),
                          # --- INSTRUCTIONS PANEL ---
                          dmc.TabsPanel(
                              value="instruction",
                              children=dmc.Paper(
                                  p="xl",
                                  radius="md",
                                  children=dmc.Stack(
                                      children=[
                                          dmc.Text(
                                              "System Instruction",
                                              fw=600,
                                              size="lg",
                                          ),
                                          dmc.Textarea(
                                              placeholder=(
                                                  "Persona and behavior"
                                                  " instructions..."
                                              ),
                                              id=Ids.INSTRUCTION,
                                              minRows=10,
                                              autosize=True,
                                              radius="md",
                                          ),
                                      ]
                                  ),
                              ),
                          ),
                          # --- EXAMPLES PANEL ---
                          dmc.TabsPanel(
                              value="examples",
                              children=dmc.Paper(
                                  p="xl",
                                  radius="md",
                                  children=dmc.Stack(
                                      children=[
                                          # SQL Examples
                                          dmc.Group(
                                              justify="space-between",
                                              children=[
                                                  dmc.Text(
                                                      "SQL Example Queries"
                                                      " (BigQuery)",
                                                      fw=600,
                                                      size="lg",
                                                  ),
                                                  dmc.Button(
                                                      "Add SQL Example",
                                                      id=Ids.BTN_ADD_EXAMPLE,
                                                      leftSection=DashIconify(
                                                          icon="material-symbols:add"
                                                      ),
                                                      variant="light",
                                                      radius="md",
                                                  ),
                                              ],
                                          ),
                                          html.Div(id=Ids.EXAMPLE_LIST),
                                          dmc.Divider(my="xl"),
                                          # Looker Golden Queries
                                          dmc.Group(
                                              justify="space-between",
                                              children=[
                                                  dmc.Text(
                                                      "Golden Queries (Looker)",
                                                      fw=600,
                                                      size="lg",
                                                  ),
                                                  dmc.Button(
                                                      "Add Golden Query",
                                                      id=Ids.BTN_ADD_GOLDEN,
                                                      leftSection=DashIconify(
                                                          icon="material-symbols:add"
                                                      ),
                                                      variant="light",
                                                      radius="md",
                                                  ),
                                              ],
                                          ),
                                          html.Div(id=Ids.GOLDEN_LIST),
                                      ]
                                  ),
                              ),
                          ),
                          # --- KNOWLEDGE (Glossary + Relations) ---
                          dmc.TabsPanel(
                              value="knowledge",
                              children=dmc.Paper(
                                  p="xl",
                                  radius="md",
                                  children=dmc.Stack(
                                      children=[
                                          # Glossary
                                          dmc.Group(
                                              justify="space-between",
                                              children=[
                                                  dmc.Text(
                                                      "Glossary Terms",
                                                      fw=600,
                                                      size="lg",
                                                  ),
                                                  dmc.Button(
                                                      "Add Term",
                                                      id=Ids.BTN_ADD_GLOSSARY,
                                                      leftSection=DashIconify(
                                                          icon="material-symbols:add"
                                                      ),
                                                      variant="light",
                                                      radius="md",
                                                  ),
                                              ],
                                          ),
                                          html.Div(id=Ids.GLOSSARY_LIST),
                                          dmc.Divider(my="xl"),
                                          # Relationships
                                          dmc.Group(
                                              justify="space-between",
                                              children=[
                                                  dmc.Text(
                                                      "Schema Relationships"
                                                      " (Join Hints)",
                                                      fw=600,
                                                      size="lg",
                                                  ),
                                                  dmc.Button(
                                                      "Add Relationship",
                                                      id=Ids.BTN_ADD_RELATION,
                                                      leftSection=DashIconify(
                                                          icon="material-symbols:add"
                                                      ),
                                                      variant="light",
                                                      radius="md",
                                                  ),
                                              ],
                                          ),
                                          html.Div(id=Ids.RELATION_LIST),
                                      ]
                                  ),
                              ),
                          ),
                          # --- ADVANCED PANEL ---
                          dmc.TabsPanel(
                              value="advanced",
                              children=dmc.Paper(
                                  p="xl",
                                  radius="md",
                                  children=dmc.Stack(
                                      gap="xl",
                                      children=[
                                          dmc.Stack(
                                              gap="xs",
                                              children=[
                                                  dmc.Text(
                                                      "Analysis Options",
                                                      fw=600,
                                                      size="lg",
                                                  ),
                                                  dmc.Group(
                                                      justify="space-between",
                                                      children=[
                                                          dmc.Stack(
                                                              gap=0,
                                                              children=[
                                                                  dmc.Text(
                                                                      "Python"
                                                                      " Analysis",
                                                                      fw=500,
                                                                  ),
                                                                  dmc.Text(
                                                                      "Allow"
                                                                      " usage"
                                                                      " of Python"
                                                                      " for calculations.",
                                                                      size="xs",
                                                                      c="dimmed",
                                                                  ),
                                                              ],
                                                          ),
                                                          dmc.Switch(
                                                              id=Ids.SWITCH_PYTHON,
                                                              size="md",
                                                              checked=True,
                                                          ),
                                                      ],
                                                  ),
                                              ],
                                          ),
                                          dmc.Divider(),
                                          dmc.Stack(
                                              gap="xs",
                                              children=[
                                                  dmc.Text(
                                                      "Resource Controls",
                                                      fw=600,
                                                      size="lg",
                                                  ),
                                                  dmc.NumberInput(
                                                      id=Ids.INPUT_MAX_BYTES,
                                                      label=(
                                                          "BQ Max Billed Bytes"
                                                      ),
                                                      radius="md",
                                                      style={"maxWidth": 300},
                                                  ),
                                              ],
                                          ),
                                      ],
                                  ),
                              ),
                          ),
                      ],
                  ),
                  # Output Preview
                  dmc.Paper(
                      p="md",
                      radius="md",
                      bg="dark.7",
                      children=[
                          dmc.Group(
                              mb="sm",
                              children=[
                                  DashIconify(
                                      icon="material-symbols:code",
                                      color="gray.5",
                                  ),
                                  dmc.Text(
                                      "Full Context JSON Object",
                                      c="gray.5",
                                      size="xs",
                                      fw=600,
                                  ),
                              ],
                          ),
                          dmc.Code(
                              id=Ids.OUTPUT_JSON,
                              block=True,
                              color="gray",
                              children="{}",
                              style={
                                  "backgroundColor": "transparent",
                                  "color": "#a5d6ff",
                              },
                          ),
                      ],
                  ),
                  # --- Elegant Summary Card ---
                  dmc.Stack(
                      gap="xs",
                      children=[
                          dmc.Divider(
                              label="Concise Summary View",
                              labelPosition="center",
                              my="xl",
                          ),
                          html.Div(id=Ids.SUMMARY_CARD),
                      ],
                  ),
              ],
          ),
      ],
  )


def register_page():
  dash.register_page(
      __name__,
      path="/agents/context-prototype",
      title="Prism | Context",
      layout=layout,
  )
