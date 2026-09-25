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
  """Trial queries, including the claim the worker uses to pick one up."""

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
    """Inserts a PENDING trial and commits, so a worker can claim it."""
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
    """Reads one trial with eager_options applied. None if there is no row."""
    stmt = (
        sqlalchemy.select(Trial)
        .options(*self.eager_options())
        .where(Trial.id == trial_id)
    )
    return self.session.scalars(stmt).unique().first()

  def pick_next_pending_trial(self, run_id: int | None = None) -> Trial | None:
    """Atomically picks and claims the next pending trial from an active run.

    Args:
      run_id: Optional ID of a specific run to pick trials from.

    Returns:
      The claimed Trial object, or None if no trials are available.
    """

    # The run filter applies whether or not a run was named. Naming one used to
    # replace it, and the worker reads its run once at the top of a pass and
    # then claims trials in a loop. A Pause or a Cancel that landed mid loop was
    # not seen, so the rest of the run's capacity was spawned anyway and the
    # user watched trials keep starting after pressing the button.
    subq_stmt = (
        sqlalchemy.select(Trial.id)
        .join(Run, Trial.run_id == Run.id)
        .where(Trial.status == RunStatus.PENDING)
        .where(Run.status.in_([RunStatus.PENDING, RunStatus.RUNNING]))
    )

    if run_id is not None:
      subq_stmt = subq_stmt.where(Trial.run_id == run_id)

    subq = (
        subq_stmt.where(Run.is_archived.is_not(True))
        .order_by(Trial.id.asc())
        .limit(1)
        # Locks the candidate row, and hands the next one to a worker that
        # finds it already locked instead of making it queue behind the
        # winner. OF Trial because locking the joined run row as well would
        # serialise every worker on the run.
        .with_for_update(skip_locked=True, of=Trial)
        .scalar_subquery()
    )

    # The status test in the outer WHERE is what makes this a claim. Under READ
    # COMMITTED the loser of a race re-evaluates its WHERE against the row the
    # winner just committed, so matching on the id alone matched a second time:
    # both workers got the row back from RETURNING, both ran the trial, both
    # billed the agent API and both wrote assertion results.
    stmt = (
        sqlalchemy.update(Trial)
        .where(Trial.id == subq)
        .where(Trial.status == RunStatus.PENDING)
        .values(
            status=RunStatus.RUNNING,
            started_at=datetime.datetime.now(datetime.timezone.utc),
        )
        .returning(Trial)
    )

    trial = self.session.scalars(stmt).first()
    if trial:

      if trial.run.status == RunStatus.PENDING:
        # Conditional, the same way promote_next_run is. The read above and
        # this write are two statements, and cancel arrives on the web request
        # thread in between. The plain assignment wrote RUNNING over the cancel
        # and the run came back with every one of its trials CANCELLED.
        self.session.execute(
            sqlalchemy.update(Run)
            .where(Run.id == trial.run_id)
            .where(Run.status == RunStatus.PENDING)
            .values(
                status=RunStatus.RUNNING,
                started_at=datetime.datetime.now(datetime.timezone.utc),
            )
        )

      self.session.commit()
      # RETURNING gives us the row but not the eager loaded relations, so
      # re-fetch.
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
    """Writes whatever the caller passed and stamps completed_at.

    Raises:
      ValueError: If there is no trial with that id.
    """
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
    stmt = (
        sqlalchemy.select(Trial)
        .join(Trial.run)
        .join(Trial.example_snapshot)
        .where(
            Trial.example_snapshot.has(original_example_id=original_example_id)
        )
        .where(Run.is_archived.is_not(True))
        # .any(), not .is_not(None). suggested_asserts is a one-to-many
        # relationship and a relationship has no IS NOT NULL, so this raised
        # NotImplementedError on every call. That is why the "Suggestions from
        # recent runs" modal 500'd instead of listing anything.
        .where(Trial.suggested_asserts.any())
        .order_by(Trial.created_at.desc())
        .limit(20)
    )
    return list(self.session.execute(stmt).scalars().all())

  def update_suggestion(
      self, trial_id: int, suggestion_index: int, new_suggestion: dict[str, Any]
  ) -> Trial:
    """Updates a specific suggestion in a trial."""
    trial = self.get_trial(trial_id)
    if not trial:
      raise ValueError(f"Trial {trial_id} not found")

    suggestions = trial.suggested_asserts
    if suggestion_index < 0 or suggestion_index >= len(suggestions):
      raise IndexError(f"Suggestion index {suggestion_index} out of bounds")

    suggestion = suggestions[suggestion_index]
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
