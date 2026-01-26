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

"""Shared utilities for the Prism UI."""

import logging
from typing import Any

import dash


logger = logging.getLogger(__name__)


def typed_callback(
    output: Any,
    inputs: list[Any],
    state: list[Any] | None = None,
    prevent_initial_call: bool | str = False,
    allow_duplicate: bool = False,
):
  """Type-safe wrapper for Dash callbacks.

  Converts tuples (id, property) into Dash dependency objects.

  Args:
    output: A single output dependency or a list of them.
    inputs: A list of input dependencies.
    state: A list of state dependencies.
    prevent_initial_call: Whether to prevent the callback from being triggered
      on app load.
    allow_duplicate: Whether to allow multiple callbacks to target the same
      output.

  Returns:
    The decorated callback function.
  """

  def _wrap(dep, dep_type, **kwargs):
    if (
        isinstance(dep, (list, tuple))
        and len(dep) == 2
        and isinstance(dep[0], (str, dict))
    ):
      return dep_type(dep[0], dep[1], **kwargs)
    return dep

  # Wrap output(s)
  if isinstance(output, list):
    wrapped_output = [
        _wrap(o, dash.Output, allow_duplicate=allow_duplicate) for o in output
    ]
  else:
    wrapped_output = _wrap(output, dash.Output, allow_duplicate=allow_duplicate)

  # Wrap inputs
  wrapped_inputs = [_wrap(i, dash.Input) for i in inputs]

  # Wrap state
  wrapped_state = [_wrap(s, dash.State) for s in state or []]

  def decorator(func):
    return dash.callback(
        output=wrapped_output,
        inputs=wrapped_inputs,
        state=wrapped_state,
        prevent_initial_call=prevent_initial_call,
    )(func)

  return decorator


# Expose dash helpers for convenience with @typed_callback
typed_callback.Input = dash.Input
typed_callback.Output = dash.Output
typed_callback.State = dash.State
typed_callback.ALL = dash.ALL
typed_callback.no_update = dash.no_update


def _triggered_id():
  """Returns the ID of the component that triggered the callback.

  If it's a pattern-matching ID, returns the dictionary.
  Otherwise, returns the string ID.
  """

  return dash.ctx.triggered_id


typed_callback.triggered_id = _triggered_id


def handle_errors(func):
  """Decorator to catch and log exceptions in callbacks."""

  def wrapper(*args, **kwargs):
    try:
      return func(*args, **kwargs)
    except Exception as e:
      logger.exception("Error in callback %s: %s", func.__name__, e)
      return dash.no_update

  return wrapper


def parse_textarea_list(value: str | None) -> list[str]:
  """Parses a newline-separated string into a list of cleaned strings."""
  if not value:
    return []
  return [
      item.strip() for item in value.split("\n") if item and not item.isspace()
  ]


def is_valid_bq_table(path: str) -> bool:
  """Checks if a string is a valid-looking BQ table FQN (proj.ds.tab)."""
  parts = path.split(".")
  return len(parts) == 3 and all(parts)


def is_valid_looker_explore(path: str) -> bool:
  """Checks if a string is a valid-looking Looker explore (model.explore)."""
  parts = path.split(".")
  return len(parts) == 2 and all(parts)
