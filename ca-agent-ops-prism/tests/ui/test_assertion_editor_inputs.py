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

"""What the assertion editor gives you to type into.

Assertion values are SQL fragments, regexes and prose. A single-line input
shows a sliding window of one of those, which is what customers hit: they could
not see the value they were editing. Every free-text field in the editor has to
wrap.

The tests walk the real page layouts, not the component in isolation. A field
the assertion modal stops rendering is the failure mode a component-level test
would miss.
"""

from __future__ import annotations

from typing import Any, Iterator

import dash
import dash_mantine_components as dmc
from prism.ui.callbacks import test_suite_questions_callbacks
from prism.ui.components import assertion_components
from prism.ui.ids import TestSuiteIds
import pytest

# Importing either of these registers every page and every callback.
from prism.ui.app import app  # pylint: disable=unused-import
from tests.ui import dash_http

_VALUE_FIELDS = [TestSuiteIds.TC_ASSERT_VALUE]

_EXAMPLE_FIELDS = [TestSuiteIds.ASSERT_EXAMPLE_VALUE]


def _walk(component: Any) -> Iterator[Any]:
  """Yields every component in a rendered tree, depth first."""
  yield component
  children = getattr(component, "children", None)
  if children is None:
    return
  if not isinstance(children, (list, tuple)):
    children = [children]
  for child in children:
    if child is not None and not isinstance(child, (str, int, float)):
      yield from _walk(child)


def _all_page_components() -> list[Any]:
  """Every component in every registered page layout.

  Layouts are functions when the page takes URL parameters, so they have to be
  called. Anything that will not render without arguments is skipped; the
  editor pages are not among them.
  """
  components = []
  for page in dash.page_registry.values():
    layout = page.get("layout")
    if callable(layout):
      try:
        layout = layout()
      except TypeError:
        continue
    if layout is not None:
      components.extend(_walk(layout))
  return components


@pytest.fixture(name="page_components", scope="module")
def _page_components() -> list[Any]:
  return _all_page_components()


def _find(components: list[Any], component_id: str) -> Any:
  """The one component carrying ``component_id``."""
  found = [c for c in components if getattr(c, "id", None) == component_id]
  assert len(found) == 1, f"expected one {component_id}, got {len(found)}"
  return found[0]


@pytest.mark.parametrize("field_id", _VALUE_FIELDS)
def test_every_assertion_value_field_wraps(page_components, field_id):
  """The field the customer types the assertion into.

  It was a dmc.TextInput, which is one line with no scrollback. All three pages
  share one component, so all three had it.
  """
  field = _find(page_components, field_id)

  assert isinstance(field, dmc.Textarea), f"still a {type(field).__name__}"
  assert field.autosize, "a fixed-height box is the same problem again"


@pytest.mark.parametrize("field_id", _EXAMPLE_FIELDS)
def test_every_example_field_wraps(page_components, field_id):
  """The read-only example sits beside the value field and must match it.

  A long example was clipped here while the same text wrapped in the box next
  to it.
  """
  field = _find(page_components, field_id)

  assert isinstance(field, dmc.Textarea), f"still a {type(field).__name__}"
  assert field.autosize
  assert field.readOnly, "the example is not editable"


def _value_rows(assert_type: str) -> int:
  """The resting height the type callback gives the value box."""
  outputs = test_suite_questions_callbacks.update_assertion_ui(assert_type)
  position = dash_http.output_position(TestSuiteIds.TC_ASSERT_VALUE, "minRows")
  return outputs[position]


@pytest.mark.parametrize("field_id", _VALUE_FIELDS + _EXAMPLE_FIELDS)
def test_the_value_field_opens_tall_enough_to_look_multi_line(
    page_components, field_id
):
  """A box resting at one row reads as a single-line field.

  It wrapped and it grew, but nothing on screen said so, and an AI Judge
  prompt is a paragraph. Opening at several rows is what says it takes more
  than a line. The example box sits beside it and has to match, or the two
  are different heights with nothing typed in either.
  """
  field = _find(page_components, field_id)

  assert field.minRows > 1
  assert field.maxRows, "unbounded growth would push the form off screen"


def test_the_types_that_take_a_number_drop_back_to_one_row():
  """A millisecond count does not need four rows of box to hold it.

  One Textarea is shared by every type that takes a value, so the resting
  height is picked per type by the callback rather than on the component.
  """
  rows = _value_rows("duration-max-ms")

  assert rows == 1


@pytest.mark.parametrize("assert_type", ["ai-judge", "query-contains"])
def test_the_types_that_take_prose_keep_the_taller_box(assert_type):
  """The AI Judge prompt and a query fragment are the reason for the height."""
  assert _value_rows(assert_type) > 1


def test_no_free_text_field_in_the_editor_is_single_line():
  """The general rule, so the next field added does not regress it.

  The parametrized tests above name the fields that exist today. This one
  fails on a new dmc.TextInput nobody thought to add to those lists.

  Walked from the editor root, not from the code editor inside it. The value
  and example boxes live in that subtree, but the type select, the guide card,
  the accuracy toggle and the validation alert are its siblings, and a field
  added beside any of them is the one nobody would think to list.

  Selects and the chart-type dropdown are not free text and are exempt.
  Anything the user types into is not.
  """
  editor = assertion_components.render_assertion_form_content()
  walked = list(_walk(editor))

  # _walk follows children and nothing else, so a field put in a leftSection or
  # a Tooltip label is invisible to it and the absence below holds over an
  # empty list. Pinning the two fields that are known to be in there is what
  # says the walk reached the form at all.
  ids = {getattr(c, "id", None) for c in walked}
  missing = {
      TestSuiteIds.TC_ASSERT_VALUE,
      TestSuiteIds.ASSERT_EXAMPLE_VALUE,
  } - ids
  assert not missing, f"the walk did not reach {sorted(missing)}"

  single_line = [c for c in walked if isinstance(c, dmc.TextInput)]

  assert not single_line, [c.id for c in single_line]
