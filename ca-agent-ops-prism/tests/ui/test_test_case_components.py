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

"""The test case card, and the assertion style map it renders from.

The style map was duplicated and the copies diverged. The card read the poorer
copy, which was missing the desc key on twelve of its fourteen branches.
"""

from __future__ import annotations

from prism.common.schemas.assertion import AssertionType
from prism.ui.components import assertion_components
from prism.ui.components import test_case_components
from prism.ui.constants import ASSERTS_GUIDE
from prism.ui.models import ui_state
import pytest

_STYLE_KEYS = {"icon", "color", "bg", "label", "badge", "desc"}


def test_there_is_one_assertion_style_map():
  """The two copies had drifted, and the poorer one was still being read.

  ``test_case_components`` held its own version, missing the desc key on
  twelve of its fourteen branches, and the trial page's type filter went
  through it. Importing the canonical one is what stops them diverging again.
  """
  assert (
      test_case_components.get_assertion_style
      is assertion_components.get_assertion_style
  )


@pytest.mark.parametrize("name", [g["name"] for g in ASSERTS_GUIDE])
def test_every_type_the_select_offers_has_a_style_of_its_own(name):
  """An assertion type with no branch gets the generic fallback.

  The fallback says "Validates the response." and is titled "Assertion", which
  is what the missing branches in the old copy rendered. The select is built
  from ASSERTS_GUIDE, so anything in it can reach a card, a badge and the
  trial page's type filter.
  """
  default = assertion_components.get_assertion_style("not-a-type")
  style = assertion_components.get_assertion_style(name)

  assert set(style) == _STYLE_KEYS
  assert style["desc"] != default["desc"], name
  assert style["label"] != default["label"], name


@pytest.mark.parametrize("a_type", list(AssertionType))
def test_every_stored_assertion_type_has_a_style_of_its_own(a_type):
  """A stored assertion is rendered by type, whatever the select offers.

  The two lists are not the same. ASSERTS_GUIDE drives the select and
  AssertionType is what the database holds, so a type that only exists in old
  rows still has to draw.
  """
  default = assertion_components.get_assertion_style("not-a-type")
  style = assertion_components.get_assertion_style(a_type.value)

  assert set(style) == _STYLE_KEYS
  assert style["desc"] != default["desc"], a_type
  assert style["label"] != default["label"], a_type


@pytest.mark.parametrize(
    "name",
    [
        "text-exact-match",
        "sql-valid",
        "custom",
        "llm-evaluation",
        "regex-match",
        "sentiment-score",
        "resolution-confirmation",
    ],
)
def test_a_type_that_was_never_built_gets_the_fallback(name):
  """These seven had branches of their own and no product behind them.

  Nothing in the repo could produce one: they are in neither AssertionType nor
  ASSERTS_GUIDE. Two of them set a Tailwind palette name, so a card built from
  them asked for var(--mantine-color-emerald-0), which resolves to nothing.
  """
  default = assertion_components.get_assertion_style("not-a-type")

  assert assertion_components.get_assertion_style(name) == default


def test_the_active_nav_item_is_the_one_with_a_border():
  """The border colour was picked twice, once at the top and once at the use.

  The variable already held "transparent" for an inactive item, so the second
  conditional could only ever choose the value it was guarding. Its neighbour
  bg_color was read unconditionally on the line above.
  """
  case = ui_state.TestCaseState(question="A question?", asserts=[])

  active = str(test_case_components.render_test_case_nav_item(case, 0, True))
  inactive = str(test_case_components.render_test_case_nav_item(case, 0, False))

  assert "#bfdbfe" in active
  assert "#bfdbfe" not in inactive


def test_the_fallback_label_is_written_like_the_rest():
  """It was the one lowercase label in a map of display text.

  ``get_assertion_style`` is read for a label in seven places and every other
  branch is title case, so an unknown type rendered a badge that looked like a
  bug next to the others.
  """
  assert assertion_components.get_assertion_style("not-a-type")["label"] == (
      "Assertion"
  )
