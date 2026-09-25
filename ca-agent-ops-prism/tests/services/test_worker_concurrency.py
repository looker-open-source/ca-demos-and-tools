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

"""Tests for WorkerProcessManager concurrency and single-run enforcement."""

import datetime
from unittest import mock
from prism.common.schemas.execution import RunStatus
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.server.services import worker
from prism.server.services.worker import WorkerProcessManager
import pytest

# pylint: disable=redefined-outer-name
# pylint: disable=protected-access
# pylint: disable=unused-argument

# The PID the fake spawn reports. An integer, because the manager hands it to
# psutil.Process, and psutil compares it against 0 before anything else. A bare
# MagicMock as the pid raised TypeError there, _process_started_at catches only
# NoSuchProcess, and both tests below ran the rollback path instead of the
# spawn path they are about.
_PID = 4242

# What psutil reports for that PID, and what the manager records beside it.
_PID_STARTED_AT = 1758000000.25


def _spawned_process():
  """The process object the patched multiprocessing context hands back."""
  proc = mock.MagicMock()
  proc.pid = _PID
  return proc


def _psutil_process():
  """The psutil.Process stand-in _process_started_at reads the time off."""
  proc = mock.MagicMock()
  proc.create_time.return_value = _PID_STARTED_AT
  return proc


@pytest.fixture
def mock_session_factory():
  mock_session = mock.MagicMock()
  factory = mock.MagicMock(return_value=mock_session)
  # WorkerProcessManager opens the factory with "with", so __enter__ has to
  # hand back the same session.
  factory.return_value.__enter__.return_value = mock_session
  return factory


@pytest.fixture
def manager(mock_session_factory):
  # The manager is a singleton, so a leftover from an earlier test is what the
  # constructor below hands back, session factory and all. Clear it on the way
  # out too: without that these tests decide what the next module's manager is
  # wired to, and the suite only passes in the order it happens to run in.
  WorkerProcessManager._instance = None
  mgr = WorkerProcessManager(session_factory=mock_session_factory)
  yield mgr
  WorkerProcessManager._instance = None


def test_the_promoted_run_is_the_one_new_trials_are_picked_for(
    manager, mock_session_factory
):
  """Promoting a run and then working on another leaves it at zero trials.

  There is no manager-wide trial limit. Capacity is read off whichever run is
  current, so the promotion has to replace the (empty) list of RUNNING runs
  before the pick, not just happen beside it.
  """
  run1 = Run(
      id=1,
      status=RunStatus.PENDING,
      created_at=datetime.datetime(2023, 1, 1),
      concurrency=2,
  )

  with (
      mock.patch(
          "prism.server.repositories.run_repository.RunRepository.promote_next_run"
      ) as mock_promote,
      mock.patch(
          "prism.server.repositories.run_repository.RunRepository.get_oldest_running"
      ) as mock_oldest,
      mock.patch(
          "prism.server.repositories.trial_repository.TrialRepository.list_by_status"
      ) as mock_list_trials,
      mock.patch(
          "prism.server.repositories.trial_repository.TrialRepository.pick_next_pending_trial"
      ) as mock_pick,
      mock.patch("multiprocessing.get_context") as mock_ctx,
      mock.patch.object(
          worker.psutil, "Process", return_value=_psutil_process()
      ),
  ):

    mock_promote.return_value = run1
    mock_oldest.return_value = None  # Nothing RUNNING, so promotion is needed.
    mock_list_trials.return_value = []
    mock_pick.side_effect = [
        Trial(id=101, run_id=1, status=RunStatus.PENDING),
        Trial(id=102, run_id=1, status=RunStatus.PENDING),
    ]
    mock_proc = _spawned_process()
    mock_ctx.return_value.Process.return_value = mock_proc

    manager._start_new_trials()

    # Promotion itself belongs to RunRepository and is covered against the
    # database in test_worker_paused_runs.py. What is checked here is that the
    # manager then spends the promoted run's concurrency on the promoted run.
    assert mock_pick.call_args_list == [mock.call(run_id=1)] * 2
    assert mock_proc.start.call_count == 2
    # The rollback after a spawn terminates the process it started, so this is
    # what says the two spawns stood rather than being undone.
    assert not mock_proc.terminate.called


def test_start_new_trials_respects_per_run_concurrency(
    manager, mock_session_factory
):
  """A run at its concurrency gets no more trials, and nor does the queue."""

  active_run = Run(
      id=1,
      status=RunStatus.RUNNING,
      created_at=datetime.datetime(2023, 1, 1),
      concurrency=1,
  )

  # The one trial that spends run 1's concurrency of 1.
  trial1 = Trial(id=10, run_id=1, status=RunStatus.RUNNING)

  with (
      mock.patch(
          "prism.server.repositories.run_repository.RunRepository.get_oldest_running"
      ) as mock_oldest,
      mock.patch(
          "prism.server.repositories.run_repository.RunRepository.promote_next_run"
      ) as mock_promote,
      mock.patch(
          "prism.server.repositories.trial_repository.TrialRepository.list_by_status"
      ) as mock_list_trials,
      mock.patch(
          "prism.server.repositories.trial_repository.TrialRepository.pick_next_pending_trial"
      ) as mock_pick,
  ):

    mock_oldest.return_value = active_run
    mock_list_trials.return_value = [trial1]

    manager._start_new_trials()

    # Capacity is concurrency minus active, so zero.
    mock_pick.assert_not_called()
    # And a full run does not hand the pass on to the next one in the queue.
    # Promoting here would put two runs against the agent API at once.
    mock_promote.assert_not_called()


def test_start_new_trials_spawns_multiple_trials(manager, mock_session_factory):
  """Spawning stops at the run's concurrency limit."""
  active_run = Run(
      id=1,
      status=RunStatus.RUNNING,
      created_at=datetime.datetime(2023, 1, 1),
      concurrency=3,
  )

  trial1_pending = Trial(id=101, run_id=1, status=RunStatus.PENDING)
  trial2_pending = Trial(id=102, run_id=1, status=RunStatus.PENDING)

  with (
      mock.patch(
          "prism.server.repositories.run_repository.RunRepository.get_oldest_running"
      ) as mock_oldest,
      mock.patch(
          "prism.server.repositories.trial_repository.TrialRepository.list_by_status"
      ) as mock_list_trials,
      mock.patch(
          "prism.server.repositories.trial_repository.TrialRepository.pick_next_pending_trial"
      ) as mock_pick,
      mock.patch("multiprocessing.get_context") as mock_ctx,
      mock.patch.object(
          worker.psutil, "Process", return_value=_psutil_process()
      ),
  ):

    mock_oldest.return_value = active_run
    mock_list_trials.return_value = []  # Nothing active, so all 3 slots free.
    mock_pick.side_effect = [trial1_pending, trial2_pending, None]

    mock_proc = _spawned_process()
    mock_ctx.return_value.Process.return_value = mock_proc

    manager._start_new_trials()

    # It asks once per slot, and stops spawning when the third ask comes back
    # empty.
    assert mock_pick.call_count == 3
    assert mock_proc.start.call_count == 2
    assert not mock_proc.terminate.called


# The aggregator used to assign COMPLETED onto the Run object, which a mocked
# session could watch. It issues a conditional UPDATE now, so the only honest
# place to check it is against a database. See
# tests/services/test_worker_cancelled_run.py.
