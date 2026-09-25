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

import datetime
import functools
import logging
import time
from typing import Any
import uuid
import dash
import flask
from prism.common.schemas.execution import RunStatus
from prism.ui.constants import NOTIFICATION_CONTAINER

logger = logging.getLogger(__name__)

# Every RunStatus member, because the three copies of this map that this
# replaced each knew about five of them. EXECUTING and EVALUATING are only ever
# written to a trial's status, never to a run's, so on a run they cannot come
# up; a trial in either fell through to a grey badge showing the raw enum name,
# which reads as a trial that crashed. PAUSED is a run status and was missing
# from the run maps too, so a paused run got the same grey badge next to a "--"
# duration.
#
# Labels are title case. The badge renders them uppercase.
_RUN_STATUS_DISPLAY = {
    RunStatus.PENDING: ("gray", "Pending"),
    RunStatus.RUNNING: ("blue", "In Progress"),
    RunStatus.EXECUTING: ("blue", "Executing"),
    RunStatus.EVALUATING: ("blue", "Evaluating"),
    RunStatus.COMPLETED: ("green", "Completed"),
    RunStatus.FAILED: ("red", "Failed"),
    RunStatus.CANCELLED: ("gray", "Cancelled"),
    RunStatus.PAUSED: ("yellow", "Paused"),
}


def run_status_display(status: RunStatus | str) -> tuple[str, str]:
  """Returns the (colour, label) a run or trial status is drawn with.

  Takes the raw string too, for the dashboard rows that come back as dicts.

  A member missing from the map reads as a grey badge carrying its raw enum
  name. This was a bare subscript, so a new RunStatus member added without a
  line in the map raised KeyError out of whatever page drew the badge.
  """
  try:
    key = RunStatus(status)
  except ValueError:
    return ("gray", str(status))
  return _RUN_STATUS_DISPLAY.get(key, ("gray", key.name))


# Keyed on the same labels render_coverage_badge writes tooltips for. The
# three copies of this that it replaced agreed on the labels and disagreed on
# the colours, so one suite with test cases and no assertions was grey on
# /test_suites, orange on /test_suites/view/<id> and red in the Run Evaluation
# modal. Grey on the list was the worst of the three: it is the same grey as
# "No Test Cases", so the two states the badge exists to tell apart looked
# identical.
_COVERAGE_DISPLAY = {
    "full": ("green", "Full Coverage"),
    "partial": ("yellow", "Partial Coverage"),
    "none": ("red", "No Coverage"),
    "empty": ("gray", "No Test Cases"),
}


def coverage_display(question_count: int, coverage: float) -> tuple[str, str]:
  """Returns the (colour, label) an assertion coverage ratio is drawn with.

  coverage is questions_with_assertions / question_count, which is what
  SuiteWithStats carries. An empty suite has a ratio of 0.0 and so has to be
  separated on the count, or it reads as a suite whose test cases all lack
  assertions.
  """
  if question_count == 0:
    return _COVERAGE_DISPLAY["empty"]
  if coverage >= 1.0:
    return _COVERAGE_DISPLAY["full"]
  if coverage > 0:
    return _COVERAGE_DISPLAY["partial"]
  return _COVERAGE_DISPLAY["none"]


def id_from_pathname(pathname: str | None) -> int:
  """Returns the trailing integer id from a URL path.

  Raises ValueError when the path does not end in one, which every caller
  handles. The rstrip is why this is shared: a third of the callbacks
  that parsed the path by hand had it and the rest did not, so the same page
  worked at /agents/view/3 and 500ed at /agents/view/3/.
  """
  return int((pathname or "").rstrip("/").split("/")[-1])


def typed_callback(
    output: Any,
    inputs: list[Any],
    state: list[Any] | None = None,
    prevent_initial_call: bool | str = False,
    allow_duplicate: bool = False,
    running: list[Any] | None = None,
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
    running: ``(Output, while_running, when_done)`` triples that Dash applies
      for the lifetime of the call. Use it to disable the button that started an
      expensive action; without it a double-click starts the action twice.

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

  if isinstance(output, list):
    wrapped_output = [
        _wrap(o, dash.Output, allow_duplicate=allow_duplicate) for o in output
    ]
  else:
    wrapped_output = _wrap(output, dash.Output, allow_duplicate=allow_duplicate)

  wrapped_inputs = [_wrap(i, dash.Input) for i in inputs]

  wrapped_state = [_wrap(s, dash.State) for s in state or []]

  def decorator(func):
    # Every callback gets handle_errors. Opting in per callback left 113 of 121
    # without it, and an uncaught exception there is a 500 the user never sees:
    # Dash logs it and the page sits unchanged.
    return dash.callback(
        output=wrapped_output,
        inputs=wrapped_inputs,
        state=wrapped_state,
        prevent_initial_call=prevent_initial_call,
        running=running,
    )(handle_errors(func))

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


def _no_update_for_current_outputs() -> Any:
  """Returns a no_update value shaped like the running callback's outputs.

  One per output, not a bare ``dash.no_update``. Dash 4 accepts either and
  leaves every output alone either way, so this buys a shape that matches what
  the callback declared rather than a behaviour change. Returning the shape is
  still the safer of the two: the bare form is special-cased inside Dash on the
  way to ``PreventUpdate``, and that path skips the return validation this one
  goes through.
  """
  try:
    outputs = dash.ctx.outputs_list
  except Exception:  # pylint: disable=broad-except
    # No callback context (called directly, e.g. from a unit test).
    return dash.no_update
  if isinstance(outputs, list):
    return [dash.no_update] * len(outputs)
  return dash.no_update


# One id for every callback failure, because they all render the same text.
# Mantine's show() ignores a notification whose id is already on screen, so
# reusing the id is what turns a burst of failures into a single toast.
TOAST_ID = "callback-error"

# How long one toast speaks for the failures behind it. Without this the
# polling pages (evaluation_detail and trial_detail refresh every 3s) send 20 a
# minute for as long as the error lasts, and a page load that finds the
# database down sends one per page-load callback. Dismissing the toast also
# buys this much quiet.
_TOAST_WINDOW_SECONDS = 30.0

# The window lives in the reader's Flask session, not in a module global. The
# Dockerfile runs one gunicorn worker for eight threads, so a global window let
# the first reader to hit a failure take the toast away from every other reader
# for the next 30 seconds. The stored value is a monotonic clock reading, which
# only means anything inside this process; the signing key is generated per
# process too, so a restart throws the session away with it.
_LAST_TOAST_KEY = "prism_last_toast_at"


def _notify_failure(callback_name: str, ref: str) -> None:
  """Raises a toast for a callback that failed.

  ``dash.set_props`` writes to a component the callback never declared as an
  output, so this works from any callback without adding a notification output
  to its signature.

  The message is fixed. The exception text is not safe to render: a SQLAlchemy
  error carries the statement and its bound parameters. ``ref`` is what ties
  what the user saw to the traceback in the log.

  Every failure is logged. Only the first one in a window is shown, and the
  window is the reader's own.
  """
  if not flask.has_request_context():
    # Called outside a request, so there is no session to read the window from
    # and no context for set_props either. The log already has the failure.
    logger.debug("No request context, no toast for %s", callback_name)
    return

  now = time.monotonic()
  if now - flask.session.get(_LAST_TOAST_KEY, 0.0) < _TOAST_WINDOW_SECONDS:
    return

  try:
    dash.set_props(
        NOTIFICATION_CONTAINER,
        {
            "sendNotifications": [{
                "id": TOAST_ID,
                "title": "Something went wrong",
                "message": (
                    f"Prism could not complete that action (ref {ref}). The"
                    " details are in the server log."
                ),
                "color": "red",
                # Stays until dismissed. An error that closes itself after four
                # seconds is one the user can miss, and a toast still on screen
                # is what makes the id deduplicate the next failure.
                "autoClose": False,
            }]
        },
    )
  except dash.exceptions.MissingCallbackContextException:
    # set_props needs a callback context, which a test calling the callback
    # directly does not have. The log already has the failure, so there is
    # nothing to add. The window stays open, since nothing was shown.
    logger.debug("No callback context, no toast for %s", callback_name)
    return

  flask.session[_LAST_TOAST_KEY] = now


def handle_errors(func):
  """Decorator to catch and log exceptions in callbacks.

  Logs the traceback, raises a toast, and returns no_update so the page keeps
  its current state.

  ``typed_callback`` applies this already, so writing it there does nothing.
  A raw ``@dash.callback`` still needs it by hand, and it must go below the
  registration decorator. Decorators apply bottom-up and ``dash.callback``
  registers whatever function it is handed, so a ``@handle_errors`` stacked
  above one wraps an object Dash never calls. It is dead code.
  """

  @functools.wraps(func)
  def wrapper(*args, **kwargs):
    try:
      return func(*args, **kwargs)
    except dash.exceptions.PreventUpdate:
      # Control flow, not a failure. It subclasses Exception, so without this
      # the catch below turns "do nothing" into an error toast.
      raise
    except Exception as e:  # pylint: disable=broad-except
      ref = uuid.uuid4().hex[:6]
      logger.exception(
          "Error in callback %s (ref %s): %s", func.__name__, ref, e
      )
      _notify_failure(func.__name__, ref)
      return _no_update_for_current_outputs()

  return wrapper


def parse_textarea_list(value: str | None) -> list[str]:
  """Parses a newline-separated string into a list of cleaned strings."""
  if not value:
    return []
  return [
      item.strip() for item in value.split("\n") if item and not item.isspace()
  ]


def format_timestamp(dt: datetime.datetime) -> str:
  """Renders a stored timestamp as a labelled UTC clock.

  Timestamps are stored in UTC. This used to be a bare ``astimezone()``, which
  resolves to the server's zone, and on Cloud Run that is UTC. So the promise
  of the reader's local time never landed in production: every time on the page
  was the UTC clock, hours out for most readers, with nothing on screen to say
  so. The local dev server is the only place it looked right.

  The server has no way to know the reader's zone, so the clock stays UTC and
  says which clock it is. A labelled UTC time is an offset the reader can
  apply. An unlabelled one is a time they read as their own.

  Callers decide what a missing timestamp reads as.
  """
  return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def format_duration(duration_ms: int | float | None) -> str:
  """Formats milliseconds into '{minutes}m {seconds}s', matching the run list."""
  if duration_ms is None:
    return "-"
  total_seconds = int(duration_ms) // 1000
  minutes = total_seconds // 60
  seconds = total_seconds % 60
  return f"{minutes}m {seconds}s"


def format_ttfr(ttfr_ms: int | float | None) -> str:
  """Formats TTFR in milliseconds to seconds rounded to nearest tenth of a second."""
  if ttfr_ms is None:
    return "-"
  return f"{ttfr_ms / 1000:.1f}s"


def is_valid_bq_table(path: str) -> bool:
  """Checks if a string is a valid-looking BQ table FQN (proj.ds.tab)."""
  parts = path.split(".")
  return len(parts) == 3 and all(parts)


def is_valid_looker_explore(path: str) -> bool:
  """Checks if a string is a valid-looking Looker explore (model.explore)."""
  parts = path.split(".")
  return len(parts) == 2 and all(parts)


def clean_empty(data: Any) -> Any:
  """Recursively removes None, empty strings, lists, and dicts from data."""
  if isinstance(data, dict):
    return {
        k: v
        for k, v in ((k, clean_empty(v)) for k, v in data.items())
        if v is not None and v != "" and v != [] and v != {}
    }
  elif isinstance(data, list):
    return [
        v
        for v in (clean_empty(x) for x in data)
        if v is not None and v != "" and v != [] and v != {}
    ]
  return data
