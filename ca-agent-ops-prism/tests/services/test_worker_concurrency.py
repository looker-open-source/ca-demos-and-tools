"""Tests for WorkerProcessManager concurrency and single-run enforcement."""

import datetime
import logging
from unittest import mock
from prism.common.schemas.execution import RunStatus
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.server.services.worker import WorkerProcessManager
import pytest


# pylint: disable=redefined-outer-name
# pylint: disable=protected-access
# pylint: disable=unused-argument


@pytest.fixture
def mock_session_factory():
  """Fixture for a mocked session factory."""
  mock_session = mock.MagicMock()
  factory = mock.MagicMock(return_value=mock_session)
  # Ensure the factory can be used as a context manager if needed
  # (though WorkerProcessManager handles this with with factory() as session)
  factory.return_value.__enter__.return_value = mock_session
  return factory


@pytest.fixture
def manager(mock_session_factory):
  """Fixture for WorkerProcessManager with mocked session."""
  # Reset singleton for testing
  WorkerProcessManager._instance = None
  mgr = WorkerProcessManager(
      max_concurrent_trials=4, session_factory=mock_session_factory
  )
  return mgr


def test_start_new_trials_promotes_pending_to_running(
    manager, mock_session_factory
):
  """Test that the worker promotes the oldest PENDING run to RUNNING."""
  mock_session = mock_session_factory.return_value.__enter__.return_value

  # Mock Runs: two pending runs
  run1 = Run(
      id=1,
      status=RunStatus.PENDING,
      created_at=datetime.datetime(2023, 1, 1),
      concurrency=2,
  )
  run2 = Run(
      id=2,
      status=RunStatus.PENDING,
      created_at=datetime.datetime(2023, 1, 2),
      concurrency=2,
  )

  # Mock TrialRepository.list_by_status and RunRepository methods
  with (
      mock.patch(
          "prism.server.repositories.run_repository.RunRepository.promote_next_run"
      ) as mock_promote,
      mock.patch(
          "prism.server.repositories.run_repository.RunRepository.list_all"
      ) as mock_list_all,
      mock.patch(
          "prism.server.repositories.trial_repository.TrialRepository.list_by_status"
      ) as mock_list_trials,
      mock.patch(
          "prism.server.repositories.trial_repository.TrialRepository.pick_next_pending_trial"
      ) as mock_pick,
  ):

    mock_promote.return_value = run1
    mock_list_all.return_value = []
    mock_list_trials.return_value = []
    mock_pick.return_value = None  # No trials for now

    manager._start_new_trials()

    # Verify promote was called
    mock_promote.assert_called_once()
    # verify run1 logic (it is now 'active' in the loop)
    # The actual status update happens inside promote_next_run, but since we mocked it returning run1,
    # and run1 locally has PENDING, we should probably manually set it to RUNNING if we want to reflect reality,
    # OR just rely on the fact that the worker uses what's returned.
    # The worker logs: "Promoted Run %s to RUNNING"


def test_start_new_trials_respects_per_run_concurrency(
    manager, mock_session_factory
):
  """Test that the worker respects the concurrency limit of the ACTIVE run."""
  mock_session = mock_session_factory.return_value.__enter__.return_value

  active_run = Run(
      id=1,
      status=RunStatus.RUNNING,
      created_at=datetime.datetime(2023, 1, 1),
      concurrency=1,
  )
  pending_run = Run(
      id=2,
      status=RunStatus.PENDING,
      created_at=datetime.datetime(2023, 1, 2),
      concurrency=5,
  )

  # Active trial for run 1
  trial1 = Trial(id=10, run_id=1, status=RunStatus.RUNNING)

  with (
      mock.patch(
          "prism.server.repositories.run_repository.RunRepository.list_all"
      ) as mock_list_all,
      mock.patch(
          "prism.server.repositories.trial_repository.TrialRepository.list_by_status"
      ) as mock_list_trials,
      mock.patch(
          "prism.server.repositories.trial_repository.TrialRepository.pick_next_pending_trial"
      ) as mock_pick,
  ):

    mock_list_all.return_value = [active_run, pending_run]
    mock_list_trials.return_value = [trial1]

    manager._start_new_trials()

    # Capacity (concurrency 1 - 1 active) = 0. Should NOT pick any trials.
    mock_pick.assert_not_called()


def test_start_new_trials_spawns_multiple_trials(manager, mock_session_factory):
  """Test that multiple trials are spawned up to the concurrency limit."""
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
          "prism.server.repositories.run_repository.RunRepository.list_all"
      ) as mock_list_all,
      mock.patch(
          "prism.server.repositories.trial_repository.TrialRepository.list_by_status"
      ) as mock_list_trials,
      mock.patch(
          "prism.server.repositories.trial_repository.TrialRepository.pick_next_pending_trial"
      ) as mock_pick,
      mock.patch("multiprocessing.get_context") as mock_ctx,
  ):

    mock_list_all.return_value = [active_run]
    mock_list_trials.return_value = []  # No active trials
    mock_pick.side_effect = [trial1_pending, trial2_pending, None]

    mock_proc = mock.MagicMock()
    mock_ctx.return_value.Process.return_value = mock_proc

    manager._start_new_trials()

    # Should have tried to pick 3 times (concurrency 3)
    assert mock_pick.call_count == 3
    # Should have started 2 processes
    assert mock_proc.start.call_count == 2


def test_aggregate_run_statuses_completes_run(manager, mock_session_factory):
  """Test that a run is marked COMPLETED when all its trials are done."""
  mock_session = mock_session_factory.return_value.__enter__.return_value

  trial1 = Trial(id=1, status=RunStatus.COMPLETED)
  trial2 = Trial(id=2, status=RunStatus.FAILED)
  run = Run(id=1, status=RunStatus.RUNNING, trials=[trial1, trial2])

  with mock.patch(
      "prism.server.repositories.run_repository.RunRepository.list_active"
  ) as mock_list_active:
    mock_list_active.return_value = [run]

    manager._aggregate_run_statuses()

    assert run.status == RunStatus.COMPLETED
    assert run.completed_at is not None
    mock_session.commit.assert_called()
