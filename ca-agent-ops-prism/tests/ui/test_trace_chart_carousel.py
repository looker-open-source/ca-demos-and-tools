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

"""The trace page's chart carousel, and what it does with a bad spec.

An agent writes its charts into the trace as JSON strings, so one of them can
fail to parse while the rest are fine. The carousel skips that one, and the
captions and the count both have to agree with what survived.
"""

from __future__ import annotations

import json
from typing import Any

from prism.ui.components import timeline
import pytest


def _event(content: Any) -> dict[str, Any]:
  """One vega-lite timeline event carrying ``content``."""
  return {"content_type": "vegalite", "content": content}


def _timeline(*contents: Any) -> dict[str, Any]:
  """A timeline DTO whose events are the charts given."""
  return {"events": [_event(c) for c in contents]}


def _spec(name: str) -> str:
  """A minimal vega-lite spec, named so a test can find its slide."""
  return json.dumps({"mark": "bar", "description": name})


def _captions(rendered: Any) -> list[str]:
  """Every "CHART n OF m" line in the rendered carousel."""
  return [
      s
      for s in str(rendered).split("'")
      if s.startswith("CHART ") and " OF " in s
  ]


def test_a_chart_that_will_not_parse_is_left_out_of_the_count():
  """The captions used to be numbered off the list before it was filtered.

  Three events with a broken one in the middle gave two slides reading "CHART
  1 OF 3" and "CHART 3 OF 3", under a header badge saying 2 Charts. Every
  number on screen disagreed with every other one.
  """
  rendered = timeline.render_chart_carousel(
      _timeline(_spec("first"), "{not json", _spec("third"))
  )

  assert _captions(rendered) == ["CHART 1 OF 2", "CHART 2 OF 2"]
  assert "2 Charts" in str(rendered)
  assert "first" in str(rendered)
  assert "third" in str(rendered)


def test_every_chart_parsing_leaves_the_numbering_alone():
  """The straightforward case, so the fix above cannot pass by dropping one."""
  rendered = timeline.render_chart_carousel(
      _timeline(_spec("a"), _spec("b"), _spec("c"))
  )

  assert _captions(rendered) == [
      "CHART 1 OF 3",
      "CHART 2 OF 3",
      "CHART 3 OF 3",
  ]
  assert "3 Charts" in str(rendered)


def test_one_chart_is_labelled_in_the_singular():
  """The header badge read "1 Charts" for a trace that drew a single chart.

  One chart is the common case: an agent answering a question usually produces
  one. The count came straight off len(slides) with the plural spelled into
  the f-string.
  """
  rendered = str(timeline.render_chart_carousel(_timeline(_spec("only"))))

  assert "1 Chart" in rendered
  assert "1 Charts" not in rendered


@pytest.mark.parametrize("contents", [(), ("{not json",)])
def test_a_section_with_no_usable_chart_is_not_rendered(contents):
  """Nothing to show means no card, not an empty one.

  The caller puts the return value straight into the page, so a card with an
  empty carousel in it would leave a titled, bordered gap under the timeline.
  """
  assert timeline.render_chart_carousel(_timeline(*contents)) is None


def test_the_carousel_does_not_resize_the_caller_s_own_spec():
  """The inline renderer draws the same dict at its own size.

  A spec that arrives already parsed belongs to the event, and the carousel
  used to set width, height and autosize on it in place. Both renderers read
  the same events, so whichever ran second inherited the other's sizing.
  """
  spec = {"mark": "bar", "description": "shared"}
  timeline.render_chart_carousel(_timeline(spec))

  assert spec == {"mark": "bar", "description": "shared"}
