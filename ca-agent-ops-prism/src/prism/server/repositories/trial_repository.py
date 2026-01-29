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

"""Repository for managing Trials."""

import datetime
from typing import Any, Sequence

from prism.common.schemas.execution import RunStatus
from prism.server.models.assertion import AssertionResult
from prism.server.models.assertion import SuggestedAssertion
from prism.server.models.run import Run
from prism.server.models.run import Trial
import sqlalchemy
from sqlalchemy import orm


class TrialRepository:
  """Repository for Trial entities."""

  def __init__(self, session: orm.Session):
    self.session = session

  def eager_options(self):
    """Common eager loading options for Trial details."""

    return [
        orm.joinedload(Trial.example_snapshot),
        orm.joinedload(Trial.run).joinedload(Run.agent),
        orm.selectinload(Trial.assertion_results).joinedload(
            AssertionResult.assertion_snapshot
        ),
        orm.selectinload(Trial.suggested_asserts),
    ]

  def create(
      self,
      run_id: int,
      example_snapshot_id: int,
  ) -> Trial:
    """Creates a new Trial."""
    trial = Trial(
        run_id=run_id,
        example_snapshot_id=example_snapshot_id,
        status=RunStatus.PENDING,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    self.session.add(trial)
    self.session.commit()
    return trial

  def list_for_run(self, run_id: int) -> Sequence[Trial]:
    """Lists all trials for a run."""
    stmt = (
        sqlalchemy.select(Trial)
        .options(*self.eager_options())
        .where(Trial.run_id == run_id)
        .order_by(Trial.id.asc())
    )
    return self.session.scalars(stmt).unique().all()

  def list_by_status(self, statuses: list[RunStatus]) -> Sequence[Trial]:
    """Lists trials with any of the given statuses."""
    stmt = (
        sqlalchemy.select(Trial)
        .options(*self.eager_options())
        .where(Trial.status.in_(statuses))
        .order_by(Trial.id.asc())
    )
    return self.session.scalars(stmt).unique().all()

  def get_trial(self, trial_id: int) -> Trial | None:
    """Gets a trial by ID."""
    stmt = (
        sqlalchemy.select(Trial)
        .options(*self.eager_options())
        .where(Trial.id == trial_id)
    )
    return self.session.scalars(stmt).unique().first()

  def pick_next_pending_trial(self) -> Trial | None:
    """Atomically picks and claims the next pending trial from an active run.

    Returns:
      The claimed Trial object, or None if no trials are available.
    """

    # Subquery: Find the ID of the next pending trial from a RUNNING run
    # Use order_by(Trial.id) or created_at for FIFO
    subq = (
        sqlalchemy.select(Trial.id)
        .join(Run, Trial.run_id == Run.id)
        .where(Trial.status == RunStatus.PENDING)
        .where(Run.status.in_([RunStatus.PENDING, RunStatus.RUNNING]))
        .order_by(Trial.id.asc())
        .limit(1)
        .scalar_subquery()
    )

    # Atomic Update
    stmt = (
        sqlalchemy.update(Trial)
        .where(Trial.id == subq)
        .values(
            status=RunStatus.RUNNING,
            started_at=datetime.datetime.now(datetime.timezone.utc),
        )
        .returning(Trial)
    )

    trial = self.session.scalars(stmt).first()
    if trial:
      # If the run was PENDING, mark it as RUNNING
      if trial.run.status == RunStatus.PENDING:
        trial.run.status = RunStatus.RUNNING
        trial.run.started_at = datetime.datetime.now(datetime.timezone.utc)

      self.session.commit()
      # Re-fetch with eager options or just return it? returning usually gives
      # us the object.
      # To get full relations, we might need a refresh or another fetch.
      return self.get_trial(trial.id)

    return None

  def update_result(
      self,
      trial_id: int,
      output_text: str | None = None,
      error_message: str | None = None,
      error_traceback: str | None = None,
      failed_stage: str | None = None,
      trace_results: list[dict[str, Any]] | None = None,
      status: RunStatus = RunStatus.COMPLETED,
  ) -> Trial:
    """Updates the result of a trial."""
    trial = self.session.get(Trial, trial_id)
    if not trial:
      raise ValueError(f"Trial with id {trial_id} not found")

    if output_text is not None:
      trial.output_text = output_text
    if error_message is not None:
      trial.error_message = error_message
    if error_traceback is not None:
      trial.error_traceback = error_traceback
    if failed_stage is not None:
      trial.failed_stage = failed_stage
    if trace_results is not None:
      trial.trace_results = trace_results

    trial.status = status
    trial.completed_at = datetime.datetime.now(datetime.timezone.utc)

    self.session.commit()
    return trial

  def list_trials_with_suggestions(
      self, original_example_id: int
  ) -> list[Trial]:
    """Lists recent trials for a question that have suggestions."""
    # We want to find trials where suggested_asserts is not empty/null
    # and joined with Run -> Agent
    # and Match ExampleSnapshot.original_example_id
    stmt = (
        sqlalchemy.select(Trial)
        .join(Trial.run)
        .join(Trial.example_snapshot)
        .where(
            Trial.example_snapshot.has(original_example_id=original_example_id)
        )
        .where(Trial.suggested_asserts.is_not(None))
        # .where(func.json_array_length(Trial.suggested_asserts) > 0)
        # SQLite/PG specific?
        # Just filter in logic if needed, or check validity
        .order_by(Trial.created_at.desc())
        .limit(20)  # Cap at 20 recent trials
    )
    trials = self.session.execute(stmt).scalars().all()
    # Filter empty ones in python to be safe for all DBs
    return [t for t in trials if t.suggested_asserts]

  def update_suggestion(
      self, trial_id: int, suggestion_index: int, new_suggestion: dict[str, Any]
  ) -> Trial:
    """Updates a specific suggestion in a trial."""
    trial = self.get_trial(trial_id)
    if not trial:
      raise ValueError(f"Trial {trial_id} not found")

    # Access relationship
    suggestions = trial.suggested_asserts
    if suggestion_index < 0 or suggestion_index >= len(suggestions):
      raise IndexError(f"Suggestion index {suggestion_index} out of bounds")

    # Update object fields
    suggestion = suggestions[suggestion_index]
    # new_suggestion is a dict with keys like 'type', 'weight', 'params',
    # 'reasoning'
    if "type" in new_suggestion:
      suggestion.type = new_suggestion["type"]
    if "weight" in new_suggestion:
      suggestion.weight = new_suggestion["weight"]
    if "params" in new_suggestion:
      suggestion.params = new_suggestion["params"]
    if "reasoning" in new_suggestion:
      suggestion.reasoning = new_suggestion["reasoning"]

    self.session.commit()
    self.session.refresh(trial)
    return trial

  def delete_suggestion(self, suggestion_id: int) -> None:
    """Deletes a suggested assertion."""
    suggestion = self.session.get(SuggestedAssertion, suggestion_id)
    if suggestion:
      self.session.delete(suggestion)
      self.session.commit()
