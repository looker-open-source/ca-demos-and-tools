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

"""Unit tests for the schedule dispatcher thread in WorkerProcessManager."""

import threading
from unittest import mock

from prism.server.services.worker import WorkerProcessManager


def _bare_manager() -> WorkerProcessManager:
  """A manager without the singleton or a database behind it."""
  manager = object.__new__(WorkerProcessManager)
  manager.stop_event = threading.Event()
  manager._thread = None  # pylint: disable=protected-access
  manager._schedule_thread = None  # pylint: disable=protected-access
  manager._running = False  # pylint: disable=protected-access
  return manager


def test_schedule_loop_dispatches_until_stopped():
  """The dispatcher loop runs a dispatch pass and exits on stop."""
  manager = _bare_manager()
  calls = []

  def dispatch_once():
    calls.append(1)
    manager.stop_event.set()

  # pylint: disable=protected-access
  with mock.patch.object(
      manager, "_process_due_schedules", side_effect=dispatch_once
  ):
    manager._schedule_loop()
  assert calls == [1]


def test_start_runs_dispatch_off_the_management_thread_and_stop_joins_both():
  """start() runs dispatch on its own named thread and stop() joins both."""
  manager = _bare_manager()
  seen = {}

  def record(name):
    def body():
      seen[name] = threading.current_thread().name
      manager.stop_event.wait(5)

    return body

  # pylint: disable=protected-access
  with mock.patch.object(
      manager, "_management_loop", side_effect=record("management")
  ), mock.patch.object(
      manager, "_schedule_loop", side_effect=record("schedule")
  ):
    manager.start()
    assert manager._schedule_thread is not None
    manager._schedule_thread.join(timeout=0.2)
    manager.stop(timeout=5)

  assert seen == {
      "management": "WorkerManager",
      "schedule": "ScheduleDispatcher",
  }
  assert manager._thread is None
  assert manager._schedule_thread is None
