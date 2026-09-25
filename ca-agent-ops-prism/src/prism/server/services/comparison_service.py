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
from prism.common.schemas.execution import RunStatus
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
      ValueError: If either run is not found, or the two ran different suites.
    """
    base_run = self.run_repository.get_by_id(base_run_id)
    challenger_run = self.run_repository.get_by_id(challenger_run_id)

    if not base_run:
      raise ValueError(f"Base run {base_run_id} not found")
    if not challenger_run:
      raise ValueError(f"Challenger run {challenger_run_id} not found")

    # The Compare modal on the Evaluations page header lists every run, so two
    # runs of different suites reached this. No logical_id is on both sides,
    # every case is NEW or REMOVED, and the report read "0.0% change, 0
    # regressions" over a set where nothing had been compared.
    #
    # A null original_suite_id is a snapshot nothing can be traced back to,
    # and None != None is False, so two runs of two such suites walked
    # straight through the guard and produced that same empty report.
    base_suite_id = base_run.snapshot_suite.original_suite_id
    challenger_suite_id = challenger_run.snapshot_suite.original_suite_id
    if (
        base_suite_id is None
        or challenger_suite_id is None
        or base_suite_id != challenger_suite_id
    ):
      raise ValueError(
          "Runs of different suites cannot be compared: run"
          f" {base_run_id} ran {base_run.snapshot_suite.name} and run"
          f" {challenger_run_id} ran {challenger_run.snapshot_suite.name}."
      )

    base_trials = self.trial_repository.list_for_run(base_run_id)
    challenger_trials = self.trial_repository.list_for_run(challenger_run_id)

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
    scored_case_count = 0
    timed_case_count = 0

    # The report reads in the challenger's snapshot order, that being the new
    # state, with the base-only cases after it. Numbered the same way the
    # trials are, so a duplicated key orders as many rows as it maps trials.
    challenger_counts: dict[tuple[str, str], int] = {}
    challenger_ordered_keys = [
        self._case_key(ex.logical_id, ex.question, challenger_counts)
        for ex in challenger_run.snapshot_suite.examples
    ]
    base_counts: dict[tuple[str, str], int] = {}
    base_ordered_keys = [
        self._case_key(ex.logical_id, ex.question, base_counts)
        for ex in base_run.snapshot_suite.examples
    ]

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

    # Both maps are keyed off the same snapshot rows, and a snapshot is
    # written once and never updated, so nothing is normally left here.
    # Appending rather than dropping keeps a trial that falls outside its
    # run's snapshot in the report. Sorted, so that tail has a stable order.
    for key in sorted(all_keys - seen_keys):
      ordered_keys.append(key)

    for key in ordered_keys:
      base_trial = base_map.get(key)
      challenger_trial = challenger_map.get(key)

      logical_id = key[1]
      question = ""
      if base_trial:
        question = base_trial.example_snapshot.question
        if base_trial.example_snapshot.logical_id:
          logical_id = base_trial.example_snapshot.logical_id
      elif challenger_trial:
        question = challenger_trial.example_snapshot.question
        if challenger_trial.example_snapshot.logical_id:
          logical_id = challenger_trial.example_snapshot.logical_id

      base_schema = self._convert_to_schema(base_trial) if base_trial else None
      challenger_schema = (
          self._convert_to_schema(challenger_trial)
          if challenger_trial
          else None
      )

      score_delta = None
      duration_delta = None
      status = ComparisonStatus.STABLE

      if (
          base_trial
          and challenger_trial
          and (self._never_ran(base_trial) or self._never_ran(challenger_trial))
      ):
        # One side has no result, so there is nothing to difference. The score
        # of a trial that never ran is None, and reading that as 0.0 scored the
        # case against the baseline: comparing against a run that was still
        # going, or one that was cancelled, reported every unfinished case as a
        # regression. Left out of the deltas, the way a case that exists on one
        # side only is. score_delta and duration_delta stay None, and it
        # counts towards none of the summary totals.
        status = ComparisonStatus.NOT_RUN

      elif base_trial and challenger_trial:
        base_score = self._comparable_score(base_trial)
        chal_score = self._comparable_score(challenger_trial)

        if base_score is None or chal_score is None:
          # A COMPLETED trial carrying no assertion of weight above zero has
          # no score, and Run.accuracy drops it from the denominator. Reading
          # the missing score as 0.0 had the compare page call a regression on
          # a trial the run detail page had excluded. Treated as NOT_RUN, the
          # same as a trial with no result: no deltas, in no total.
          status = ComparisonStatus.NOT_RUN
        else:
          base_duration = base_trial.duration_ms or 0
          chal_duration = challenger_trial.duration_ms or 0

          score_delta = chal_score - base_score
          duration_delta = chal_duration - base_duration

          total_score_delta += score_delta
          scored_case_count += 1

          if base_trial.error_message or challenger_trial.error_message:
            # A FAILED trial scores 0.0 and Run.accuracy counts that zero, so
            # the score delta above has to carry it. Dropping it reported
            # "+0.0%, 0 regressions" on a challenger whose twenty trials had
            # all failed, under twenty rows each reading -100%.
            #
            # The case lands in this bucket and no other. Counted by score as
            # well, it left the Regressions card reading 1 over a Regressed
            # chip reading 0: the chip counts rows by status, and the status
            # here is ERROR. The four counts also summed past total_cases,
            # which is the number the All chip shows.
            #
            # Its duration stays out of the average below. A trial that died
            # on its first event is quick for a reason that is not a speed-up.
            status = ComparisonStatus.ERROR
            errors += 1
          else:
            if score_delta < -0.01:  # Tolerance for float
              status = ComparisonStatus.REGRESSION
              regressions += 1
            elif score_delta > 0.01:
              status = ComparisonStatus.IMPROVED
              improvements += 1
            else:
              status = ComparisonStatus.STABLE
              same += 1

            total_duration_delta += duration_delta
            timed_case_count += 1

      elif base_trial:
        status = ComparisonStatus.REMOVED
      elif challenger_trial:
        # NEW even when the trial errored, and counted in no total: a case
        # with no base score to difference against stays out of the deltas.
        # errors_count is the pairs the latency average dropped, which is what
        # the note under the header says it is. Counting an added question
        # there fired that note over a case that had never been in the
        # average, while the mirror, a REMOVED case whose base trial errored,
        # counted nothing. The two agree now.
        status = ComparisonStatus.NEW

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

    avg_duration_delta = 0.0
    if timed_case_count > 0:
      avg_duration_delta = total_duration_delta / timed_case_count

    # Accuracy delta is the mean per-case score delta over the cases that ran
    # in both runs. A difference of the two run averages would only agree with
    # this on the intersection, so cases on one side only are left out to keep
    # the regression count exact.

    overall_accuracy_delta = 0.0
    if scored_case_count > 0:
      overall_accuracy_delta = total_score_delta / scored_case_count

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

  def _comparable_score(self, trial: Any) -> float | None:
    """The score to difference, or None when the trial has none to give.

    A FAILED trial is scored 0.0: it ran, it returned nothing usable, and
    Run.accuracy counts it as a zero. Anywhere else a None score means the
    trial was never scored at all, which is not the same number.
    """
    if trial.status == RunStatus.FAILED:
      return trial.score or 0.0
    return trial.score

  def _never_ran(self, trial: Any) -> bool:
    """True when the trial holds no result, so it cannot be compared.

    Anything other than COMPLETED and FAILED is queued, still going, or
    cancelled. Run.accuracy draws the same line: those trials are the ones it
    leaves out of the average.
    """
    return trial.status not in (RunStatus.COMPLETED, RunStatus.FAILED)

  def _case_key(
      self,
      logical_id: str | None,
      question: str | None,
      counts: dict[tuple[str, str], int],
  ) -> tuple[str, str, int]:
    """The key one case is matched on, numbered within its run.

    counts carries the occurrences already keyed for this run and is updated
    in place. Nothing stops a suite holding two questions with one logical_id,
    or two with none and the same text, and keying on that alone had the
    second trial overwrite the first: one case where there were two, and a
    total_cases that did not match the run. The occurrence number keeps them
    apart, and the nth duplicate on one side still lines up with the nth on
    the other because both are numbered in snapshot order.
    """
    if logical_id:
      base = ("logical_id", str(logical_id))
    else:
      # logical_id is non-null in the schema, so this only fires on an empty
      # value. Key those cases by question text instead.
      base = ("question", str(question or ""))

    counts[base] = counts.get(base, 0) + 1
    return base + (counts[base],)

  def _map_trials(self, trials: list[Any]) -> dict[tuple[str, str, int], Any]:
    """Maps trials by logical_id (preferred) or question."""
    mapping = {}
    counts: dict[tuple[str, str], int] = {}
    for trial in trials:
      key = self._case_key(
          trial.example_snapshot.logical_id,
          trial.example_snapshot.question,
          counts,
      )
      mapping[key] = trial
    return mapping

  def _convert_to_schema(self, trial: Any) -> TrialSchema:
    """Converts a Trial ORM object to TrialSchema, assertions included.

    Only the fields the compare page reads. agent_name, question, duration_ms,
    ttfr_ms, error_traceback, failed_stage, tool_timings and started_at are
    left at their defaults: the page takes the question and both deltas off
    the case, and the trial only for its id, status, score and assertions.
    Anything that wants the whole row wants run_client._map_trial.
    """
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

    assertion_results = []
    if trial.assertion_results:
      for ar in trial.assertion_results:
        # ar.assertion is the snapshot the run was executed against, not the
        # live assertion row.
        #
        # Columns last. params is a dump of the whole assertion schema, so it
        # carries the live row's original_assertion_id, which is always None.
        # Applying params last overwrote the real one, and the comparison then
        # could not tell two assertions of the same type apart.
        assertion_data = dict(ar.assertion.params or {})
        assertion_data.update({
            "id": ar.assertion.id,
            "original_assertion_id": ar.assertion.original_assertion_id,
            "type": ar.assertion.type,
            "weight": ar.assertion.weight,
        })

        result_data = {
            "assertion": assertion_data,
            "passed": ar.passed,
            "score": ar.score,
            "reasoning": ar.reasoning,
            "error_message": ar.error_message,
        }
        assertion_results.append(result_data)
    data["assertion_results"] = assertion_results

    suggested_asserts = []
    if trial.suggested_asserts:
      for sa in trial.suggested_asserts:
        sa_data = dict(sa.params or {})
        sa_data.update({"type": sa.type, "weight": sa.weight})
        suggested_asserts.append(sa_data)
    data["suggested_asserts"] = suggested_asserts

    return TrialSchema.model_validate(data)
