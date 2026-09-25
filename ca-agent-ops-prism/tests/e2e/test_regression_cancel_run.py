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

"""Regression: cancelling a run left its trials running.

``RunClient.cancel_run`` built a ``sqlalchemy.update(Trial)`` statement setting
every PENDING trial to CANCELLED, then never executed it. Only the run row
changed. The worker pool selects trials by status, so it went on picking the
pending ones up, and a cancelled run kept calling a paid API until the last
trial had run.

Expensive, and invisible from the UI: the page shows CANCELLED the moment the
button is clicked. Only the database disagrees, so that is what these specs
read.

Cancel is two mechanisms, and there is one spec for each. ``cancel_run`` writes
the PENDING trials itself. The trial already in flight belongs to a subprocess,
so ``cancel_run`` leaves it alone and the worker pool stops it on its next pass.
"""

from __future__ import annotations

import subprocess
import sys
import time
from typing import Iterator

from playwright.sync_api import expect
from playwright.sync_api import Page
from prism.common.schemas.execution import RunStatus
from prism.server.models.run import Trial
from prism.ui.ids import EvaluationIds
import psutil
import pytest
import sqlalchemy

pytestmark = pytest.mark.e2e

# How long to give the worker pool to notice the cancelled run. Its loop sleeps
# two seconds a pass, and a pass has to read the trial, kill the process and
# re-read the row under a lock.
WORKER_PASS_TIMEOUT_S = 30


@pytest.fixture
def sleeper() -> Iterator[psutil.Process]:
  """A live process for a trial to claim, harmless when the server kills it.

  Seeding ``os.getpid()`` would be the easy way to give a trial a live PID, and
  it is a trap: ``_kill_trial_process`` reaches ``p.kill()`` and takes the
  pytest process with it. This one exists to be killed.

  It is spawned through a throwaway parent so that it is orphaned, not a child
  of pytest. The server kills it from another process, so ``p.wait()`` there
  cannot reap it and just polls for the PID to go. A child of pytest stays a
  zombie on that PID until pytest reaps it, which it has no reason to do while
  the test is still waiting, so every kill timed out. Init reaps an orphan.
  """
  # The sleeper gets no handle on the pipe its PID is reported over. Inheriting
  # it holds the pipe open for the sleeper's whole ten minutes, and the read
  # below waits for the end of a file nobody is going to close.
  spawn = (
      "import subprocess, sys;"
      "print(subprocess.Popen("
      "[sys.executable, '-c', 'import time; time.sleep(600)'],"
      " stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).pid)"
  )
  started = subprocess.run(
      [sys.executable, "-c", spawn], capture_output=True, text=True, check=True
  )
  process = psutil.Process(int(started.stdout))
  try:
    yield process
  finally:
    if process.is_running():
      process.kill()


def test_cancelling_a_run_cancels_its_pending_trials(
    page: Page, base_url: str, seed, db
):
  """Clicking Cancel leaves no PENDING trial for a worker to pick up."""
  agent = seed.agent()
  suite = seed.suite()
  for question in (
      "How many orders were there?",
      "How many customers were there?",
      "How many refunds were there?",
  ):
    seed.example(suite, question=question)
  snapshot = seed.snapshot(suite)
  # PAUSED, not RUNNING. The live worker pool claims pending trials of a RUNNING
  # run within its poll interval, which would race the click and make the spec
  # flaky. It leaves a paused run alone. Cancel is offered for both and
  # cancel_run treats them the same, and pause-then-cancel is an ordinary way to
  # reach this code.
  run = seed.run(agent, snapshot, status=RunStatus.PAUSED)

  _cancel_from_the_page(page, base_url, run.id)

  statuses = _trial_statuses(db, run.id)
  for trial_id, status in statuses.items():
    assert status == RunStatus.CANCELLED, (
        f"Trial {trial_id} is still {status}. The worker pool selects by "
        "status, so it will execute this trial and bill for it even though "
        "the run was cancelled."
    )


def test_cancelling_a_run_stops_the_trial_already_in_flight(
    page: Page, base_url: str, seed, db, sleeper: subprocess.Popen[bytes]
):
  """Cancel kills the running trial's process and marks the trial CANCELLED.

  ``cancel_run`` only writes the PENDING trials, so for a while the trial in
  flight went on talking to the agent, billed for it, and wrote its answer into
  a run nobody was going to look at. The worker pool now stops it.
  """
  agent = seed.agent()
  suite = seed.suite()
  seed.example(suite)
  snapshot = seed.snapshot(suite)
  run = seed.run(agent, snapshot, status=RunStatus.PAUSED)

  # Both columns, and both off the same live process. The PID alone is not
  # identity: with trial_pid_started_at unset the pool falls back to comparing
  # the parent PID, decides the process is not its own child, and leaves the
  # trial where it is. Then this spec would pass without the kill ever
  # happening.
  (trial,) = run.trials
  trial.status = RunStatus.RUNNING
  trial.trial_pid = sleeper.pid
  trial.trial_pid_started_at = sleeper.create_time()
  db.commit()

  _cancel_from_the_page(page, base_url, run.id)

  status = _await_trial_status(db, trial.id, RunStatus.CANCELLED)
  assert status == RunStatus.CANCELLED, (
      f"Trial {trial.id} is still {status} {WORKER_PASS_TIMEOUT_S}s after the "
      "run was cancelled. Its process is still running against the agent."
  )
  assert not sleeper.is_running(), (
      "The trial reached CANCELLED with its process still alive. The row is "
      "free for a second worker while the first one is still writing to it."
  )


def _cancel_from_the_page(page: Page, base_url: str, run_id: int) -> None:
  """Clicks Cancel on a run's detail page and waits for the badge to agree."""
  page.goto(f"{base_url}/evaluations/runs/{run_id}")
  page.wait_for_load_state("networkidle")

  cancel = page.locator(f"#{EvaluationIds.BTN_CANCEL_RUN_EXEC}")
  expect(cancel).to_be_visible()
  cancel.click()

  expect(page.locator(f"#{EvaluationIds.RUN_STATUS_BADGE}")).to_contain_text(
      "CANCELLED", ignore_case=True
  )


def _await_trial_status(session, trial_id: int, wanted: RunStatus) -> RunStatus:
  """Polls one trial until it reaches ``wanted``, and returns what it found.

  Returns the last status seen rather than failing, so the caller's assertion
  message can say what the trial was stuck on.
  """
  deadline = time.monotonic() + WORKER_PASS_TIMEOUT_S
  status = None
  while time.monotonic() < deadline:
    session.expire_all()
    status = session.execute(
        sqlalchemy.select(Trial.status).where(Trial.id == trial_id)
    ).scalar_one()
    if status == wanted:
      return status
    time.sleep(0.25)
  return status


def _trial_statuses(session, run_id: int) -> dict[int, RunStatus]:
  """Reads trial statuses straight from the database.

  Bypasses the ORM identity map. The objects the seeder handed back are stale
  by now, so reading them would assert against what this process believes
  instead of what the server wrote.
  """
  session.expire_all()
  rows = session.execute(
      sqlalchemy.select(Trial.id, Trial.status).where(Trial.run_id == run_id)
  ).all()
  return {row.id: row.status for row in rows}
