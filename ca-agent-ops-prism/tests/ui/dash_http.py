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

"""Drives Dash callbacks over HTTP, without a browser.

``app.server`` is an ordinary Flask app and ``/_dash-update-component`` is an
ordinary route, so ``app.server.test_client()`` can POST the body the browser
would have sent and read the real response. That covers three things calling a
callback function directly cannot:

* Serialization. The return value has to survive Dash's JSON encoder. A
  SQLAlchemy row or a stray ``Decimal`` is a 500 here and a pass there.
* Pruning. ``suppress_callback_exceptions=True`` means a callback whose
  components are never rendered is absent from the map, and importing its
  function still works.
* Dependency wiring. The payload addresses inputs by id and property, so a
  callback whose declared dependencies drifted away from its signature fails.
  Direct invocation passes positionally and notices nothing.
"""

from __future__ import annotations

import json
from typing import Any

from dash import _callback
from prism.ui.app import app

# Properties of the location components. A callback whose every input is one of
# these fires on page load and nothing else, which is where the pages read the
# database and turn rows into components.
_URL_PROPERTIES = frozenset({"pathname", "search", "href", "hash"})


def dependencies(client) -> list[dict[str, Any]]:
  """Returns the callback graph the browser would fetch on load."""
  response = client.get("/_dash-dependencies")
  assert response.status_code == 200, response.status_code
  return json.loads(response.data)


def url_only(deps: list[dict[str, Any]]) -> list[dict[str, Any]]:
  """Returns the callbacks driven solely by the URL."""
  return [
      dep
      for dep in deps
      if dep["inputs"]
      and all(i["property"] in _URL_PROPERTIES for i in dep["inputs"])
  ]


def _one_output(spec: str) -> dict[str, Any]:
  """Parses a single ``<id>.<property>`` output, dropping any hash suffix."""
  # Dash appends @<sha> to an output declared with allow_duplicate=True, to
  # keep the two callbacks writing it apart. It is not part of the address.
  spec = spec.split("@")[0]
  component_id, prop = spec.rsplit(".", 1)
  if component_id.startswith("{"):
    component_id = json.loads(component_id)
  return {"id": component_id, "property": prop}


def outputs_grouping(spec: str) -> dict[str, Any] | list[dict[str, Any]]:
  """Expands an output spec string into the ``outputs`` field of the payload.

  Dash serializes a multi-output callback as ``..a.b...c.d..`` and needs it
  expanded back. Leaving ``outputs`` off, or getting its length wrong, does not
  produce a useful error: Dash raises IndexError deep inside
  ``dash._grouping.map_grouping`` and the route returns a bare 500 that reads
  like the callback itself blew up.
  """
  if spec.startswith("..") and spec.endswith(".."):
    return [_one_output(s) for s in spec[2:-2].split("...")]
  return _one_output(spec)


def address(dep: dict[str, Any]) -> str:
  """The ``<id>.<property>`` key naming one input or state entry."""
  component_id = dep["id"]
  if isinstance(component_id, dict):
    component_id = json.dumps(
        component_id, sort_keys=True, separators=(",", ":")
    )
  return f"{component_id}.{dep['property']}"


# How the graph spells a wildcard: the key's value is the wrapped token.
_WILDCARDS = (["ALL"], ["MATCH"], ["ALLSMALLER"])


def _parsed_id(dep: dict[str, Any]) -> Any:
  """The component id as an object, since the graph stringifies dict ids."""
  component_id = dep["id"]
  if isinstance(component_id, str) and component_id.startswith("{"):
    return json.loads(component_id)
  return component_id


def _wildcard_key(component_id: Any) -> str | None:
  """The key holding the wildcard, or None if this id names one component."""
  if not isinstance(component_id, dict):
    return None
  for key, value in component_id.items():
    if value in _WILDCARDS:
      return key
  return None


def pattern_address(dep: dict[str, Any], index: Any) -> str:
  """The ``changedPropIds`` key naming one component of a pattern.

  Dash rebuilds ids from the payload and compares the strings, so this has to
  be keyed in sorted order with no spaces, the way the browser writes it.
  """
  component_id = _parsed_id(dep)
  key = _wildcard_key(component_id)
  assert key, f"{dep['id']} does not address a pattern"
  return address({
      "id": dict(component_id, **{key: index}),
      "property": dep["property"],
  })


def _expand_wildcards(grouping: Any, rendered: dict[str, list[Any]]) -> Any:
  """Replaces each wildcard output with the components the page rendered.

  The browser resolves a wildcard output before it posts, so ``outputs`` names
  concrete components and the callback returns one value per component. Leave
  the ALL-shaped id in and Dash answers 200 having written to a component id
  that cannot exist, which reads as a pass.
  """
  if isinstance(grouping, list):
    return [_expand_wildcards(g, rendered) for g in grouping]
  key = _wildcard_key(grouping["id"])
  if key is None:
    return grouping
  indices = rendered.get(address(grouping))
  assert indices is not None, (
      f"{address(grouping)} is a wildcard output. Pass rendered= with the"
      " indices the page puts on screen, because the callback returns one"
      " value per component and Dash checks the count."
  )
  return [
      {
          "id": dict(grouping["id"], **{key: index}),
          "property": grouping["property"],
      }
      for index in indices
  ]


def _input_entry(dep: dict[str, Any], values: dict[str, Any]) -> Any:
  """One ``inputs`` entry, which is itself a list for a wildcard input.

  A callback taking ``{"type": t, "index": ALL}`` receives one value per
  rendered component, so the browser sends a list and Dash passes a list
  through. Send a single dict instead and the callback sees None, reads
  nothing out of ``ctx.triggered`` and returns no_update, which looks from the
  outside exactly like the callback deciding not to act.
  """
  supplied = values.get(address(dep))
  component_id = _parsed_id(dep)
  key = _wildcard_key(component_id)
  if key is None:
    return dict(dep, value=supplied)
  return [
      {
          "id": dict(component_id, **{key: index}),
          "property": dep["property"],
          "value": value,
      }
      for index, value in supplied or []
  ]


def fire(
    client,
    dep: dict[str, Any],
    values: dict[str, Any],
    changed=None,
    rendered=None,
):
  """POSTs ``dep`` to the update route and returns the Flask response.

  Args:
    client: A Flask test client for ``app.server``.
    dep: One entry from ``dependencies()``.
    values: Maps ``"<id>.<property>"`` to the value to send. Anything the
      callback declares and this does not name is sent as None, which is what
      the browser sends for a component nothing has populated yet. A wildcard
      input is keyed by its ALL-shaped address and takes ``[(index, value),
      ...]``, one pair per rendered component, in the order the page renders
      them. ``pattern_address`` names one of them for ``changed``.
    changed: The addresses to report as having just changed, which is what
      ``dash.ctx.triggered_id`` reads. Defaults to every input, the page-load
      case. Callbacks that branch on which button fired need it set.
    rendered: Maps a wildcard output's ALL-shaped address to the indices on
      screen. Required if the callback has one, because Dash counts the values
      it returns against the components named here.

  Returns:
    The response. 200 carries the new property values, 204 means the callback
    raised PreventUpdate, and 500 means it raised anything else without
    ``@handle_errors`` to catch it.
  """
  inputs = [_input_entry(i, values) for i in dep["inputs"]]
  state = [_input_entry(s, values) for s in dep.get("state", [])]
  if changed is None:
    changed = [
        address(entry)
        for i in inputs
        for entry in (i if isinstance(i, list) else [i])
    ]

  return client.post(
      "/_dash-update-component",
      json={
          "output": dep["output"],
          "outputs": _expand_wildcards(
              outputs_grouping(dep["output"]), rendered or {}
          ),
          "inputs": inputs,
          "state": state,
          "changedPropIds": list(changed),
      },
  )


def fire_url(client, dep: dict[str, Any], pathname: str, search: str = ""):
  """Fires a URL-driven callback as if the browser had just navigated.

  Values go in by property rather than by id, because the app has three
  location components: its own ``url``, ``comp-loc-url`` on the comparison
  page, and the ``_pages_location`` Dash adds for its own router. Addressing
  them by id means forgetting one and reading the resulting TypeError as a
  defect in the callback.
  """
  by_property = {
      "pathname": pathname,
      "search": search,
      "hash": "",
      "href": f"http://localhost{pathname}{search}",
  }
  values = {
      address(dep_entry): by_property[dep_entry["property"]]
      for dep_entry in dep["inputs"] + dep.get("state", [])
      if dep_entry["property"] in _URL_PROPERTIES
  }
  return fire(client, dep, values)


def find(
    deps: list[dict[str, Any]],
    address: str,
    triggered_by: str | None = None,
) -> dict[str, Any]:
  """Returns the one callback writing ``"<id>.<property>"``.

  The property is part of the key because one component often has two
  callbacks behind it, one filling a dropdown's ``data`` and another setting
  its ``value``. ``triggered_by`` narrows further, by component id, for the
  stores that more than one callback clears.
  """
  component_id, prop = address.rsplit(".", 1)
  matches = [
      dep
      for dep in deps
      if any(
          o["id"] == component_id and o["property"] == prop
          for o in _as_list(dep["output"])
      )
      and (
          triggered_by is None
          or any(i["id"] == triggered_by for i in dep["inputs"])
      )
  ]
  assert len(matches) == 1, (
      f"expected exactly one callback writing {address!r}"
      + (f" from {triggered_by!r}" if triggered_by else "")
      + f", found {len(matches)}"
  )
  return matches[0]


def _as_list(spec: str) -> list[dict[str, Any]]:
  """The output spec as a list, however many outputs it declares."""
  grouping = outputs_grouping(spec)
  return grouping if isinstance(grouping, list) else [grouping]


def body(response) -> dict[str, Any]:
  """The decoded response, or {} for the 204 a PreventUpdate produces."""
  if response.status_code == 204:
    return {}
  return json.loads(response.data)


def _registered_outputs(spec: dict[str, Any]) -> list[Any]:
  """One registration's outputs, as a list however many it declares.

  A single-output callback is registered with a bare Output, not a list of
  one, and iterating that raises instead of matching nothing.
  """
  outputs = spec["output"]
  return outputs if isinstance(outputs, list) else [outputs]


def output_position(component_id: str, prop: str) -> int:
  """Where in a callback's return tuple ``<id>.<property>`` lands.

  For the tests that call a callback function directly and get a bare tuple
  back. Reading one value out of that tuple by counting is a trap: appending
  an output shifts everything after it, and the assertion goes on passing
  against whatever moved into the slot. Look the position up by name instead.

  ``app._setup_server()`` moves the registrations off the module globals and
  onto the app on the first request, so read whichever one is populated.
  """
  specs = _callback.GLOBAL_CALLBACK_MAP or app.callback_map
  assert specs, "no callbacks registered"
  matches = [
      _registered_outputs(spec)
      for spec in specs.values()
      if any(
          o.component_id == component_id and o.component_property == prop
          for o in _registered_outputs(spec)
      )
  ]
  assert len(matches) == 1, (
      f"expected exactly one callback writing {component_id}.{prop}, found"
      f" {len(matches)}"
  )
  (outputs,) = matches
  return next(
      position
      for position, o in enumerate(outputs)
      if o.component_id == component_id and o.component_property == prop
  )
