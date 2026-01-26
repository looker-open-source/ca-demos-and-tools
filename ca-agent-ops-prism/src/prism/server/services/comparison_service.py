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

"""Service for comparing runs."""

from typing import Any

from prism.common.schemas.comparison import ComparisonCase
from prism.common.schemas.comparison import ComparisonDelta
from prism.common.schemas.comparison import ComparisonStatus
from prism.common.schemas.comparison import RunComparison
from prism.common.schemas.comparison import RunComparisonMetadata
from prism.common.schemas.execution import RunSchema
from prism.common.schemas.execution import Trial as TrialSchema
from prism.server.repositories.run_repository import RunRepository
from prism.server.repositories.trial_repository import TrialRepository
from sqlalchemy import orm


class ComparisonService:
  """Service for comparing two evaluation runs."""

  def __init__(
      self,
      session: orm.Session,
      run_repository: RunRepository | None = None,
      trial_repository: TrialRepository | None = None,
  ):
    """Initializes the ComparisonService."""
    self.session = session
    self.run_repository = run_repository or RunRepository(session)
    self.trial_repository = trial_repository or TrialRepository(session)

  def compare_runs(
      self, base_run_id: int, challenger_run_id: int
  ) -> RunComparison:
    """Compares two runs and generates a comparison report.

    Args:
      base_run_id: ID of the baseline run.
      challenger_run_id: ID of the candidate run.

    Returns:
      RunComparison object containing deltas and case-by-case comparison.

    Raises:
      ValueError: If either run is not found.
    """
    base_run = self.run_repository.get_by_id(base_run_id)
    challenger_run = self.run_repository.get_by_id(challenger_run_id)

    if not base_run:
      raise ValueError(f"Base run {base_run_id} not found")
    if not challenger_run:
      raise ValueError(f"Challenger run {challenger_run_id} not found")

    base_trials = self.trial_repository.list_for_run(base_run_id)
    challenger_trials = self.trial_repository.list_for_run(challenger_run_id)

    # Index trials by logical_id (preferred) or question
    base_map = self._map_trials(base_trials)
    challenger_map = self._map_trials(challenger_trials)

    all_keys = set(base_map.keys()) | set(challenger_map.keys())
    cases: list[ComparisonCase] = []

    regressions = 0
    improvements = 0
    same = 0
    errors = 0
    total_duration_delta = 0.0
    total_score_delta = 0.0
    valid_score_comparison_count = 0

    # Determine stable ordering based on TestSuiteSnapshot examples
    # We prefer the Challenger's order, as that's the "new" state.
    # If a case is only in Base, we append it at the end.
    challenger_ordered_keys = [
        ex.logical_id or ex.question
        for ex in challenger_run.snapshot_suite.examples
    ]
    base_ordered_keys = [
        ex.logical_id or ex.question for ex in base_run.snapshot_suite.examples
    ]

    # Combine keys in order: Challenger first, then any Base-only keys
    ordered_keys = []
    seen_keys = set()
    for key in challenger_ordered_keys:
      if key in all_keys and key not in seen_keys:
        ordered_keys.append(key)
        seen_keys.add(key)
    for key in base_ordered_keys:
      if key in all_keys and key not in seen_keys:
        ordered_keys.append(key)
        seen_keys.add(key)

    # Any leftover keys from all_keys (should not happen if snapshots are complete)
    for key in sorted(all_keys - seen_keys):
      ordered_keys.append(key)

    for key in ordered_keys:
      base_trial = base_map.get(key)
      challenger_trial = challenger_map.get(key)

      # Determine Logical ID and Question
      logical_id = key
      question = ""
      if base_trial:
        question = base_trial.example_snapshot.question
        if base_trial.example_snapshot.logical_id:
          logical_id = base_trial.example_snapshot.logical_id
      elif challenger_trial:
        question = challenger_trial.example_snapshot.question
        if challenger_trial.example_snapshot.logical_id:
          logical_id = challenger_trial.example_snapshot.logical_id

      # Convert to Schema for response
      base_schema = self._convert_to_schema(base_trial) if base_trial else None
      challenger_schema = (
          self._convert_to_schema(challenger_trial)
          if challenger_trial
          else None
      )

      # Calculate Deltas
      score_delta = None
      duration_delta = None
      status = ComparisonStatus.STABLE

      if base_trial and challenger_trial:
        # Both exist - Compare
        base_duration = base_trial.duration_ms or 0
        chal_duration = challenger_trial.duration_ms or 0

        base_score = base_trial.score or 0.0
        chal_score = challenger_trial.score or 0.0

        score_delta = chal_score - base_score
        duration_delta = chal_duration - base_duration

        total_score_delta += score_delta
        total_duration_delta += duration_delta
        valid_score_comparison_count += 1

        if challenger_trial.error_message:
          status = ComparisonStatus.ERROR
          errors += 1
        elif score_delta < -0.01:  # Tolerance for float
          status = ComparisonStatus.REGRESSION
          regressions += 1
        elif score_delta > 0.01:
          status = ComparisonStatus.IMPROVED
          improvements += 1
        else:
          status = ComparisonStatus.STABLE
          same += 1

      elif base_trial:
        # Removed in challenger
        status = ComparisonStatus.REMOVED
      elif challenger_trial:
        # New in challenger
        status = ComparisonStatus.NEW
        if challenger_trial.error_message:
          status = ComparisonStatus.ERROR
          errors += 1

      cases.append(
          ComparisonCase(
              logical_id=str(logical_id),
              question=question,
              base_trial=base_schema,
              challenger_trial=challenger_schema,
              score_delta=score_delta,
              duration_delta=duration_delta,
              status=status,
          )
      )

    # Calculate Aggregates
    avg_duration_delta = 0.0
    if valid_score_comparison_count > 0:
      avg_duration_delta = total_duration_delta / valid_score_comparison_count

    # Accuracy Delta: Average score of challenger - Average score of base
    # NOTE: This simple difference of averages (total_score_delta / count) is mathematically equivalent
    # to (Avg Check - Avg Base) ONLY for the intersection.
    # For the top summary, usually we want "Run Level Delta".
    # But let's stick to intersection delta for now or overall delta?
    # Let's use intersection delta for precision on regressions.

    overall_accuracy_delta = 0.0
    if valid_score_comparison_count > 0:
      overall_accuracy_delta = total_score_delta / valid_score_comparison_count

    delta = ComparisonDelta(
        accuracy_delta=overall_accuracy_delta,
        duration_delta_avg=avg_duration_delta,
        regressions_count=regressions,
        improvements_count=improvements,
        same_count=same,
        errors_count=errors,
    )

    metadata = RunComparisonMetadata(
        base_run_id=base_run_id,
        challenger_run_id=challenger_run_id,
        total_cases=len(cases),
    )

    return RunComparison(
        base_run=RunSchema.model_validate(base_run),
        challenger_run=RunSchema.model_validate(challenger_run),
        metadata=metadata,
        delta=delta,
        cases=cases,
    )

  def _map_trials(self, trials: list[Any]) -> dict[str, Any]:
    """Maps trials by logical_id (preferred) or question."""
    mapping = {}
    for trial in trials:
      # Use logical_id from snapshot if available
      key = trial.example_snapshot.logical_id
      if not key:
        # Fallback to question text if logical_id matches are empty (legacy?)
        # Ideally logical_id is always present.
        key = trial.example_snapshot.question

      mapping[key] = trial
    return mapping

  def _convert_to_schema(self, trial: Any) -> TrialSchema:
    """Converts a Trial ORM object to TrialSchema, handling assertion serialization."""
    # Manual conversion to handle nested assertion params
    data = {
        "id": trial.id,
        "run_id": trial.run_id,
        "example_snapshot_id": trial.example_snapshot_id,
        "status": trial.status,
        "output_text": trial.output_text,
        "error_message": trial.error_message,
        "trace_results": trial.trace_results,
        "score": trial.score,
        "created_at": trial.created_at,
        "completed_at": trial.completed_at,
    }

    # Assertion Results
    assertion_results = []
    if trial.assertion_results:
      for ar in trial.assertion_results:
        # ar is AssertionResultSnapshot ORM
        # ar.assertion is AssertionSnapshot ORM
        assertion_data = {
            "id": ar.assertion.id,
            "original_assertion_id": ar.assertion.original_assertion_id,
            "type": ar.assertion.type,
            "weight": ar.assertion.weight,
        }
        if ar.assertion.params:
          assertion_data.update(ar.assertion.params)

        result_data = {
            "assertion": assertion_data,
            "passed": ar.passed,
            "score": ar.score,
            "reasoning": ar.reasoning,
            "error_message": ar.error_message,
        }
        assertion_results.append(result_data)
    data["assertion_results"] = assertion_results

    # Suggested Asserts
    suggested_asserts = []
    if trial.suggested_asserts:
      for sa in trial.suggested_asserts:
        # sa is SuggestedAssertion ORM (AssertionSnapshot-like structure)
        sa_data = {
            "type": sa.type,
            "weight": sa.weight,
        }
        if sa.params:
          sa_data.update(sa.params)
        suggested_asserts.append(sa_data)
    data["suggested_asserts"] = suggested_asserts

    return TrialSchema.model_validate(data)
