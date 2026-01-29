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

"""UI Constants."""

import enum


class ComponentProperty(enum.StrEnum):
  """Common component properties to avoid magic strings."""

  N_CLICKS = "n_clicks"
  VALUE = "value"
  DATA = "data"
  OPENED = "opened"
  CHILDREN = "children"
  HREF = "href"
  PATHNAME = "pathname"
  SEARCH = "search"
  ACTIVE = "active"
  STYLE = "style"
  DISABLED = "disabled"
  VISIBLE = "visible"
  CHECKED = "checked"
  LABEL = "label"
  COLOR = "color"
  LOADING = "loading"
  HIDE = "hide"
  HIDDEN = "hidden"


# Alias for brevity
# Alias for brevity
CP = ComponentProperty

# Global Redirect Handler ID
REDIRECT_HANDLER = "redirect-handler"
GLOBAL_PROJECT_ID_STORE = "global-project-id-store"


CHART_TYPE_OPTIONS = [
    {"label": "Area", "value": "area"},
    {"label": "Bar", "value": "bar"},
    {"label": "Circle", "value": "circle"},
    {"label": "Line", "value": "line"},
    {"label": "Point", "value": "point"},
    {"label": "Rect", "value": "rect"},
    {"label": "Rule", "value": "rule"},
    {"label": "Square", "value": "square"},
    {"label": "Text", "value": "text"},
    {"label": "Tick", "value": "tick"},
    {"label": "Geoshape", "value": "geoshape"},
    {"label": "Boxplot", "value": "boxplot"},
    {"label": "Error Band", "value": "errorband"},
    {"label": "Error Bar", "value": "errorbar"},
]


ASSERTS_GUIDE = [
    {
        "name": "text-contains",
        "label": "Text Contains",
        "description": (
            "Checks if the agent's final text response contains a specific"
            " substring."
        ),
        "example": "Expected text",
    },
    {
        "name": "query-contains",
        "label": "Query Contains",
        "description": (
            "Checks if the generated SQL or Looker query contains a specific"
            " substring."
        ),
        "example": "FROM `my_table`",
    },
    {
        "name": "duration-max-ms",
        "label": "Max Duration (ms)",
        "description": (
            "Checks if the total time for the trial was below a threshold."
        ),
        "example": "5000",
    },
    {
        "name": "data-check-row-count",
        "label": "Row Count Match",
        "description": (
            "Checks if the structured data result has an exact number of rows."
        ),
        "example": "3",
    },
    {
        "name": "data-check-row",
        "label": "Row Value Match",
        "description": (
            "Checks if a row exists that matches all specified column-value"
            " pairs."
        ),
        "example": "city: 'Paris'\npopulation: 2141000",
    },
    {
        "name": "chart-check-type",
        "label": "Chart Type Match",
        "description": "Checks if a generated chart is of a specific type.",
        "example": "bar",
    },
    {
        "name": "looker-query-match",
        "label": "Looker Query Match",
        "description": (
            "Checks if the generated Looker query matches the specified"
            " structure (model, explore, fields, filters, sorts, limit)."
            " Supports partial matching."
        ),
        "example": (
            "model: 'thelook'\nexplore: 'orders'\nfields: ['orders.id',"
            " 'orders.status', 'users.name']\nfilters:\n  orders.created_at:"
            " 'last 7 days'\n  users.state: 'California'\nsorts:"
            " ['orders.created_at desc']\nlimit: '100'"
        ),
    },
    {
        "name": "ai-judge",
        "label": "AI Judge",
        "description": (
            "Asks an LLM to evaluate the response based on your natural"
            " language instructions. Non-deterministic."
        ),
        "example": (
            "The agent should be polite and confirm that the order has been"
            " placed."
        ),
    },
]
