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

"""Every time on screen says which clock it is on.

Timestamps are stored in UTC. ``utils.format_timestamp`` used to hand them to a
bare ``astimezone()``, which resolves to the server's zone, and on Cloud Run
that is UTC. The local time it promised only ever appeared on a developer's
machine, so in production every reading was the UTC clock wearing no label.

``tests/ui/test_run_started_column.py`` pins the formatter itself. What is
pinned here is the three places that were not going through it: the agent
detail header, the history suggestion labels, and the trace timeline badges.
Each of those formatted the stored clock on its own, so one screen could show
two different times for one instant.
"""

from __future__ import annotations

import datetime
from typing import Any

from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.assertion import AssertionType
from prism.server.models.agent import Agent
from prism.server.models.assertion import SuggestedAssertion
from prism.server.models.example import Example
from prism.server.models.run import Trial
from prism.server.repositories.agent_repository import AgentRepository
from prism.ui.components import timeline
from prism.ui.ids import TestSuiteIds as Ids
from prism.ui.pages.agent_ids import AgentIds
from prism.ui.utils import format_timestamp
from tests.ui import dash_http

_UTC = datetime.timezone.utc

# Five past nine in the morning, UTC. Chosen because +05:30 moves it across
# the hour and not only across the minute, so a formatter that never converted
# is a different string and not a coincidence.
_INSTANT = datetime.datetime(2026, 3, 1, 9, 5, 0, 123000, tzinfo=_UTC)
_IN_KOLKATA = _INSTANT.astimezone(
    datetime.timezone(datetime.timedelta(hours=5, minutes=30))
)


def _values(response) -> dict[str, Any]:
  """The property values a 200 carries, keyed by ``<id>.<property>``."""
  written = dash_http.body(response).get("response", {})
  return {
      f"{component_id}.{prop}": value
      for component_id, props in written.items()
      for prop, value in props.items()
  }


def _callback(
    deps: list[dict[str, Any]], *addresses: str, writes: str = ""
) -> dict[str, Any]:
  """The one server callback taking all of ``addresses`` as inputs.

  Addressed by input, because both outputs read here are declared
  allow_duplicate and every loading overlay has a clientside twin writing the
  same property. ``writes`` is needed on top of that for the suggestions
  button: two callbacks fire on that click, one to open the modal and one to
  fill it in.
  """
  wanted = set(addresses)
  matches = [
      dep
      for dep in deps
      if dep.get("clientside_function") is None
      and wanted <= {dash_http.address(i) for i in dep["inputs"]}
      and (not writes or writes in dep["output"])
  ]
  assert (
      len(matches) == 1
  ), f"expected one server callback on {wanted}, found {len(matches)}"
  return matches[0]


def _text(node: Any) -> list[str]:
  """The rendered text of a serialized tree, in document order.

  Follows ``children`` and nothing else. Walking every value instead picks up
  the class names, the component type and the namespace, which are strings in
  the serialized form and are not on screen.
  """
  if isinstance(node, str):
    return [node]
  if isinstance(node, list):
    return [s for item in node for s in _text(item)]
  if isinstance(node, dict):
    return _text(node.get("props", {}).get("children"))
  return []


def test_the_agent_detail_header_says_which_clock_last_updated_is_on(
    dash_client, callback_errors, db_session
):
  """The header is the only place the agent's own edit time is shown.

  It formatted ``modified_at`` itself instead of calling the shared formatter,
  so the same agent read one way here and another wherever the formatter was
  used, differing by the server's UTC offset. There is no way to tell the two
  apart on screen unless the string says which clock it is.
  """
  config = AgentConfig(project_id="p", location="l", agent_resource_id="r")
  agent = AgentRepository(db_session).create(name="Dated Agent", config=config)
  # Assigned explicitly, so the column's onupdate leaves it alone.
  agent.modified_at = _INSTANT
  db_session.commit()

  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps,
      "url.pathname",
      f"{AgentIds.Detail.STORE_REFRESH_TRIGGER}.data",
  )
  response = dash_http.fire_url(dash_client, dep, f"/agents/view/{agent.id}")

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  description = _values(response)[f"{AgentIds.Detail.DESCRIPTION}.children"]

  assert _text(description) == ["Last updated ", "2026-03-01 09:05 UTC"]


def test_the_agent_detail_header_agrees_with_the_shared_formatter(
    dash_client, callback_errors, db_session
):
  """Same instant, same string, whatever zone it arrived in.

  The row is written from a +05:30 clock and read back through the formatter
  the rest of the pages use. A header that kept its own formatting passes the
  test above and fails this one.
  """
  config = AgentConfig(project_id="p", location="l", agent_resource_id="r")
  agent = AgentRepository(db_session).create(name="Travelled", config=config)
  agent.modified_at = _IN_KOLKATA
  db_session.commit()
  db_session.expire_all()

  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps,
      "url.pathname",
      f"{AgentIds.Detail.STORE_REFRESH_TRIGGER}.data",
  )
  response = dash_http.fire_url(dash_client, dep, f"/agents/view/{agent.id}")

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  description = _values(response)[f"{AgentIds.Detail.DESCRIPTION}.children"]
  stored = db_session.get(Agent, agent.id).modified_at

  assert _text(description)[-1] == format_timestamp(stored)
  assert _text(description)[-1] == "2026-03-01 09:05 UTC"


def test_the_history_suggestion_labels_say_when_the_trial_ran(
    dash_client, callback_errors, db_session, seeded
):
  """One label per trial, and it is all there is to tell two runs apart.

  The modal lists suggestions from every past trial of the test case, grouped
  under a heading that is a timestamp, an agent name and two ids. The
  timestamp formatted the stored clock directly, so the heading disagreed with
  the run page it came from.
  """
  example = (
      db_session.query(Example).filter_by(test_suite_id=seeded.suite_id).one()
  )
  trial = (
      db_session.query(Trial)
      .filter_by(run_id=seeded.run_id)
      .order_by(Trial.id)
      .all()
  )[-1]
  trial.created_at = _IN_KOLKATA
  db_session.add(
      SuggestedAssertion(
          trial_id=trial.id,
          type=AssertionType("text-contains"),
          weight=1.0,
          params={"value": "orders", "mode": "contains"},
          reasoning="the answer should mention orders",
      )
  )
  db_session.commit()

  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps,
      f"{Ids.TC_HISTORY_SUGGESTIONS_BTN}.n_clicks",
      writes=f"{Ids.STORE_HISTORY_SUGGESTIONS}.data",
  )
  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{Ids.TC_HISTORY_SUGGESTIONS_BTN}.n_clicks": 1,
          f"{Ids.STORE_BUILDER}.data": [
              {"id": example.id, "question": seeded.question, "asserts": []}
          ],
          f"{Ids.STORE_SELECTED_INDEX}.data": 0,
      },
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  offered = _values(response)[f"{Ids.STORE_HISTORY_SUGGESTIONS}.data"]

  assert len(offered) == 1, offered
  assert offered[0]["_group_label"].startswith("2026-03-01 09:05 UTC - ")


def _timeline(timestamp: Any) -> dict[str, Any]:
  """A one-group timeline whose first event carries ``timestamp``."""
  return {
      "total_duration_ms": 1000,
      "groups": [{
          "title": "Data Query",
          "duration_ms": 1000,
          "icon": "bi:database",
          "events": [{
              "title": "Agent Thought",
              "content": "counting the orders",
              "content_type": "text",
              "timestamp": timestamp,
              "duration_ms": 1000,
              "cumulative_duration_ms": 1000,
          }],
      }],
  }


def test_the_trace_timeline_badges_read_the_same_clock_as_the_cards():
  """Both spellings of an event time end up on the UTC clock.

  The timeline is built from a Timeline DTO, and an event timestamp reaches
  this as a datetime when the DTO is dumped in python mode and as an ISO
  string when it has been through JSON. The badge used to render whichever
  arrived, unconverted and unlabelled, directly under a trial card the shared
  formatter had already drawn in UTC.
  """
  from_object = str(timeline.render_trace_timeline(_timeline(_IN_KOLKATA)))
  from_json = str(
      timeline.render_trace_timeline(_timeline(_IN_KOLKATA.isoformat()))
  )

  for rendered in (from_object, from_json):
    assert "09:05:00.123 UTC" in rendered
    # What the badge said before, which is the same instant read as +05:30.
    assert "14:35:00.123" not in rendered


def test_a_timeline_event_time_keeps_its_milliseconds():
  """The badges have always been sub-second and the trace needs them to be.

  Two events of one group can be tens of milliseconds apart, and the point of
  the badge is to line the trace up against the agent's own logs.
  """
  rendered = str(timeline.render_trace_timeline(_timeline(_INSTANT)))

  assert "09:05:00.123 UTC" in rendered


def test_a_timestamp_the_timeline_cannot_parse_is_left_as_it_arrived():
  """A trace is an agent's output, so the field is whatever it wrote.

  Anything unparseable goes on the badge verbatim rather than being dropped or
  turned into an error. Nothing else on the page would show that the trace was
  malformed.
  """
  rendered = str(timeline.render_trace_timeline(_timeline("not a timestamp")))

  assert "not a timestamp" in rendered
