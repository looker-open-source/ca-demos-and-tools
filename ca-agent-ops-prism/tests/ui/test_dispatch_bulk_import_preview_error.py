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

"""What a rejected bulk import is allowed to say about the text it rejected.

The preview runs on every keystroke in the paste box, so the error it shows is
the most frequently rendered error in the app. It used to be ``str(e)`` on a
pydantic ValidationError, which prints ``input_value=`` with the whole rejected
test case in it, plus a link to errors.pydantic.dev. The text being pasted is
production questions, and prism has no authentication, so the page it lands on
is readable by anyone who can reach the port.

The field paths say as much about what to fix without putting the value back on
the page. ``agent_detail_callbacks._golden_query_error`` does the same thing for
the golden query box, and this follows it.

Text the YAML scanner refuses never reaches the schema, so there are no fields
to name. It is still the reader's own typo, so it is reported as an input error
carrying the scanner's problem and line, and nothing else off the line.
"""

from __future__ import annotations

from typing import Any

from prism.ui.app import app  # pylint: disable=unused-import
from prism.ui.ids import TestSuiteIds as Ids
from tests.ui import dash_http

# A test case with no question, so the schema rejects it. The value is the part
# that must not come back.
_MISSING_QUESTION = """
- assertions:
    - type: text-contains
      value: SECRET_TOKEN_abc
"""

# An unclosed quote, which the YAML scanner refuses before the schema is
# reached. The scanner echoes the line it choked on.
_UNPARSEABLE = """
- question: "How many orders did SECRET_CUSTOMER place?
"""


def _preview(dash_client, text: str) -> dict[str, Any]:
  """Types ``text`` into the paste box in the structured YAML mode."""
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{Ids.PREVIEW_BULK_ADD}.children")
  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{Ids.INPUT_BULK_TEXT}.value": text,
          f"{Ids.TC_BULK_MODE}.value": "advanced",
      },
  )
  assert response.status_code == 200, response.data[:2000]
  written = dash_http.body(response)["response"]
  return {
      f"{component_id}.{prop}": value
      for component_id, props in written.items()
      for prop, value in props.items()
  }


def test_a_rejected_test_case_is_named_by_its_fields_not_by_its_value(
    dash_client, callback_errors
):
  """The field path is the actionable half of a validation error."""
  values = _preview(dash_client, _MISSING_QUESTION)

  callback_errors.assert_none()
  alert = values[f"{Ids.PREVIEW_BULK_ADD}.children"]
  rendered = str(alert)

  assert alert["props"]["title"] == "Input Error"
  assert "question" in rendered, "nothing said which field was missing"
  assert "SECRET_TOKEN_abc" not in rendered
  assert "input_value" not in rendered
  assert "errors.pydantic.dev" not in rendered
  assert values[f"{Ids.BTN_BULK_ADD_CONFIRM}.disabled"] is True


def test_text_the_parser_refused_says_what_it_refused_and_quotes_nothing(
    dash_client, callback_errors
):
  """A typo in the paste box is the reader's own text, not a server fault.

  Everything that reaches this except used to be reported as a bad test case,
  which sent the user looking for a schema mistake in text the parser never
  read. What it says now is the scanner's problem and the line it is on. Not
  the scanner's str(), which quotes the line back.
  """
  values = _preview(dash_client, _UNPARSEABLE)

  alert = values[f"{Ids.PREVIEW_BULK_ADD}.children"]
  rendered = str(alert)

  assert alert["props"]["title"] == "Input Error"
  assert "not valid YAML" in rendered
  assert "line" in rendered
  assert "SECRET_CUSTOMER" not in rendered
  assert values[f"{Ids.BTN_BULK_ADD_CONFIRM}.disabled"] is True
  # Nothing is logged. A YAML typo is not something to go looking for later.
  callback_errors.assert_none()


def test_valid_yaml_previews_and_enables_the_confirm_button(
    dash_client, callback_errors
):
  """The error paths are only worth anything if the good path still works.

  Catching too much here would turn a valid paste into a parsing error, and
  the Add button would never enable.
  """
  values = _preview(
      dash_client,
      "- question: How many orders are there?\n"
      "  assertions:\n"
      "    - type: text-contains\n"
      "      value: orders\n",
  )

  callback_errors.assert_none()
  assert "1 test cases found" in str(
      values[f"{Ids.VAL_MSG}-bulk-count.children"]
  )
  assert "How many orders are there?" in str(
      values[f"{Ids.PREVIEW_BULK_ADD}.children"]
  )
  assert values[f"{Ids.BTN_BULK_ADD_CONFIRM}.disabled"] is False
