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

"""Service for exporting evaluation runs and telemetry to BigQuery."""

import datetime
import json
import logging
import threading
from typing import Any, Callable

from google.api_core import exceptions
from google.cloud import bigquery
from prism.common.schemas.execution import RunStatus
from prism.server import db
from prism.server.config import settings
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.server.repositories.run_repository import RunRepository
from sqlalchemy import orm

logger = logging.getLogger(__name__)

# The three answers to "is this run in BigQuery". Unknown is the one the old
# boolean could not give: a denied credential or a BigQuery outage is not
# evidence that the run is absent, and reporting it as absent painted a
# healthy export as a failed one.
EXPORT_STATE_EXPORTED = "exported"
EXPORT_STATE_NOT_EXPORTED = "not_exported"
EXPORT_STATE_UNKNOWN = "unknown"

# Streaming insert limits. insert_rows_json is one HTTP POST and BigQuery caps
# it at 10 MB, so a 40-trial run with a large result payload in one event built
# a request that was rejected whole. Both limits are below the documented ones,
# because the row count and the JSON size are what we can measure here and the
# request carries more than the rows.
_MAX_ROWS_PER_INSERT = 500
_MAX_BYTES_PER_INSERT = 5 * 1024 * 1024


def _displayable_error(e: Exception) -> str:
  """What a failed export may say on the run page.

  The stored text is read back and rendered as "Export failed: ...", and
  prism has no authentication of its own. A BigQuery error names the
  destination project, the dataset, the table and the service account that
  was refused, all of which used to go on the page, so only the status of the
  failure is kept and the rest stays in the server log.
  """
  if isinstance(e, exceptions.GoogleAPICallError):
    return (
        f"BigQuery rejected the export ({e.code}). The details are in the"
        " server log."
    )
  return (
      f"The export failed with {type(e).__name__}. The details are in the"
      " server log."
  )


def _format_timestamp(dt: datetime.datetime | None) -> str | None:
  """Formats a datetime object into an ISO 8601 UTC string for BigQuery."""
  if not dt:
    return None
  if dt.tzinfo is None:
    dt = dt.replace(tzinfo=datetime.timezone.utc)
  return dt.isoformat()


_export_lock = threading.Lock()
_active_exports: set[int] = set()
# Runs this process has confirmed are in BigQuery. Export is append-only and a
# run is immutable once complete, so "exported" never goes back to false and is
# worth remembering. Without it, every is_run_exported call pays for a query job
# to re-learn something that cannot change.
_exported_runs: set[int] = set()


def is_run_syncing(run_id: int) -> bool:
  """Returns True if an export for run_id is currently in flight."""
  with _export_lock:
    return run_id in _active_exports


def get_run_export_error(run_id: int) -> str | None:
  """Returns the last export failure recorded on run_id, if any.

  Read off the run row, not a process global. A failure kept in memory was
  gone after a restart, so a half-written export read as clean, and a second
  server process never saw it at all.
  """
  with db.SessionLocal() as session:
    run = session.get(Run, run_id)
    return run.bigquery_export_error if run else None


def record_run_export_error(
    session: orm.Session, run_id: int, error: str | None
) -> None:
  """Writes the export outcome onto the run, clearing it on a clean export."""
  run = session.get(Run, run_id)
  if not run:
    return
  run.bigquery_export_error = error
  session.commit()


def reset_export_state() -> None:
  """Clears the process-local export bookkeeping. For tests."""
  with _export_lock:
    _active_exports.clear()
    _exported_runs.clear()


class BigQueryExporter:
  """Exports completed Prism evaluation runs and traces to Google BigQuery."""

  def __init__(
      self,
      project_id: str | None = None,
      dataset_id: str | None = None,
      location: str | None = None,
      client: bigquery.Client | None = None,
  ):
    self.project_id = project_id or settings.bigquery_export_project
    self.dataset_id = dataset_id or settings.bigquery_export_dataset
    self.location = location or settings.bigquery_export_location
    self._client = client

  @property
  def client(self) -> bigquery.Client:
    """Lazily initializes the BigQuery client."""
    if self._client is None:
      self._client = bigquery.Client(
          project=self.project_id, location=self.location
      )
    return self._client

  def ensure_dataset_and_tables(self) -> None:
    """Ensures that the BigQuery dataset and evaluation tables exist."""
    dataset_ref = bigquery.DatasetReference(
        self.client.project, self.dataset_id
    )
    dataset = bigquery.Dataset(dataset_ref)
    dataset.location = self.location
    self.client.create_dataset(dataset, exists_ok=True)

    table_schemas = {
        "prism_eval_runs": [
            bigquery.SchemaField("run_id", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("agent_id", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("agent_name", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("suite_name", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("accuracy", "FLOAT64", mode="NULLABLE"),
            bigquery.SchemaField("duration_ms", "INT64", mode="NULLABLE"),
            bigquery.SchemaField("total_trials", "INT64", mode="NULLABLE"),
            bigquery.SchemaField("scored_trials", "INT64", mode="NULLABLE"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("completed_at", "TIMESTAMP", mode="NULLABLE"),
            bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
            bigquery.SchemaField(
                "agent_context_snapshot", "JSON", mode="NULLABLE"
            ),
        ],
        "prism_eval_trials": [
            bigquery.SchemaField("trial_id", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("run_id", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("question", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("output_text", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("score", "FLOAT64", mode="NULLABLE"),
            bigquery.SchemaField("duration_ms", "INT64", mode="NULLABLE"),
            bigquery.SchemaField("ttfr_ms", "INT64", mode="NULLABLE"),
            bigquery.SchemaField("failed_stage", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("retry_count", "INT64", mode="NULLABLE"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("started_at", "TIMESTAMP", mode="NULLABLE"),
            bigquery.SchemaField("completed_at", "TIMESTAMP", mode="NULLABLE"),
            bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("error_message", "STRING", mode="NULLABLE"),
        ],
        "prism_eval_assertion_results": [
            bigquery.SchemaField("id", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("trial_id", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("run_id", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("assertion_type", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("passed", "BOOLEAN", mode="REQUIRED"),
            bigquery.SchemaField("score", "FLOAT64", mode="NULLABLE"),
            bigquery.SchemaField("weight", "FLOAT64", mode="NULLABLE"),
            bigquery.SchemaField("reasoning", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("error_message", "STRING", mode="NULLABLE"),
        ],
        "prism_eval_traces": [
            bigquery.SchemaField("trial_id", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("run_id", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("step_index", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("event_type", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("timestamp", "TIMESTAMP", mode="NULLABLE"),
            bigquery.SchemaField("payload", "JSON", mode="NULLABLE"),
        ],
    }

    for table_name, schema in table_schemas.items():
      table_ref = dataset_ref.table(table_name)
      table = bigquery.Table(table_ref, schema=schema)
      table.time_partitioning = bigquery.TimePartitioning(
          type_=bigquery.TimePartitioningType.DAY,
          field="created_at"
          if "created_at" in [f.name for f in schema]
          else None,
      )
      self.client.create_table(table, exists_ok=True)

  def serialize_run(self, run: Run) -> dict[str, Any]:
    """Transforms a Run ORM entity into a BigQuery record dictionary."""
    agent_name = run.agent.name if run.agent else None
    suite_name = run.snapshot_suite.name if run.snapshot_suite else None

    # The population Run.accuracy averages over, which is not total_trials. A
    # COMPLETED trial whose example has no weighted assertion scores None and
    # is left out, so a 40 trial run can be scored over 32. The two numbers
    # went into the same row with no record of the second, and a reader
    # multiplying accuracy by total_trials counted correct answers over a
    # population that was never scored. Mirrors the rule in Run.accuracy.
    scored_trials = sum(
        1
        for t in run.trials
        if t.status == RunStatus.FAILED
        or (t.status == RunStatus.COMPLETED and t.score is not None)
    )

    return {
        "run_id": run.id,
        "agent_id": run.agent_id,
        "agent_name": agent_name,
        "suite_name": suite_name,
        # Run.accuracy, not a local mean, so the warehouse agrees with the UI.
        #
        # The local version this replaces averaged over `t.score is not None`,
        # which drops FAILED trials: they never produce assertion results, so
        # their score is None. A run where half the trials crashed exported as
        # 100% accurate.
        "accuracy": run.accuracy,
        "duration_ms": run.duration_ms,
        "total_trials": len(run.trials),
        "scored_trials": scored_trials,
        "created_at": _format_timestamp(run.created_at),
        "completed_at": _format_timestamp(run.completed_at),
        "status": (
            run.status.value
            if hasattr(run.status, "value")
            else str(run.status)
        ),
        "agent_context_snapshot": (
            json.dumps(run.agent_context_snapshot)
            if run.agent_context_snapshot
            else None
        ),
    }

  def serialize_trial(self, trial: Trial) -> dict[str, Any]:
    """Transforms a Trial ORM entity into a BigQuery record dictionary."""
    question = (
        trial.example_snapshot.question if trial.example_snapshot else None
    )
    return {
        "trial_id": trial.id,
        "run_id": trial.run_id,
        "question": question,
        "output_text": trial.output_text,
        "score": trial.score,
        "duration_ms": trial.duration_ms,
        "ttfr_ms": trial.ttfr_ms,
        "failed_stage": trial.failed_stage,
        "retry_count": trial.retry_count,
        "created_at": _format_timestamp(trial.created_at),
        "started_at": _format_timestamp(trial.started_at),
        "completed_at": _format_timestamp(trial.completed_at),
        "status": (
            trial.status.value
            if hasattr(trial.status, "value")
            else str(trial.status)
        ),
        "error_message": trial.error_message,
    }

  def is_run_exported(self, run_id: int) -> bool:
    """Whether a Run is in BigQuery, with unknown folded into False.

    For callers that only act on a yes. A caller that shows the answer to a
    user wants check_run_exported instead, because "we could not tell" and
    "it is not there" are different things to say.
    """
    return self.check_run_exported(run_id) == EXPORT_STATE_EXPORTED

  def check_run_exported(self, run_id: int) -> str:
    """Whether a Run has been exported to BigQuery, or unknown.

    Returns one of EXPORT_STATE_EXPORTED, EXPORT_STATE_NOT_EXPORTED or
    EXPORT_STATE_UNKNOWN.

    Answers from the process-local memo when it can. Every miss costs a query
    job, so callers on a render path should not ask about runs that cannot be
    there yet. RunsClient.get_bigquery_export_status takes a check_exported
    argument for that, which the run detail page turns off for a run that has
    not completed.
    """
    with _export_lock:
      if run_id in _exported_runs:
        return EXPORT_STATE_EXPORTED

    # The table name is interpolated, not a parameter. A BigQuery query
    # parameter can only stand where a value goes, never where an identifier
    # does. The project and the dataset come from settings; run_id comes from
    # the caller, so it is bound.
    query = f"""
        SELECT 1
        FROM `{self.client.project}.{self.dataset_id}.prism_eval_runs`
        WHERE run_id = @run_id
        LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("run_id", "INT64", run_id),
        ]
    )
    try:
      query_job = self.client.query(query, job_config=job_config)
      results = list(query_job.result())
    except exceptions.NotFound:
      # Nothing has ever been exported, so the table doesn't exist yet. The one
      # expected failure here, and the only one that means "not exported".
      return EXPORT_STATE_NOT_EXPORTED
    except Exception:  # pylint: disable=broad-exception-caught
      # Anything else (denied credentials, a bad dataset id, BigQuery down) is
      # not evidence of absence, so it is its own answer. Logged as well, or a
      # misconfigured export looks like a permanently pending one with no
      # trace of why.
      logger.exception(
          "Could not determine BigQuery export state for run %s in %s.%s",
          run_id,
          self.client.project,
          self.dataset_id,
      )
      return EXPORT_STATE_UNKNOWN

    if results:
      with _export_lock:
        _exported_runs.add(run_id)
      return EXPORT_STATE_EXPORTED
    return EXPORT_STATE_NOT_EXPORTED

  def _insert_chunked(
      self,
      table: bigquery.TableReference,
      rows: list[dict[str, Any]],
      row_ids: list[str],
  ) -> list[Any]:
    """Streams rows into one table in requests BigQuery will take.

    One call per chunk of _MAX_ROWS_PER_INSERT rows or _MAX_BYTES_PER_INSERT
    of JSON, whichever comes first. The traces of a 40-trial run with a large
    result payload in one event went over the 10 MB request cap and were
    rejected whole.

    A row bigger than a whole request is skipped and reported, because there
    is no chunking that makes it fit. Sending it alone only moved the
    rejection into BigQuery, where it took the rest of its chunk with it.

    Returns the row errors from every chunk, gathered. Their "index" is
    relative to the chunk they came from, not to rows. A skipped row's entry
    indexes into rows, since it never reached a chunk.

    A request that fails outright raises, and that is on purpose. The run row
    is written last, so the raise leaves the run reading as un-exported and
    Sync can be pressed again. Reporting it as row errors instead would write
    the run row on top of missing children, and is_run_exported would then
    skip the retry forever.
    """
    all_errors = []
    chunk: list[dict[str, Any]] = []
    chunk_ids: list[str] = []
    chunk_bytes = 0

    def flush():
      errors = self.client.insert_rows_json(table, chunk, row_ids=chunk_ids)
      if errors:
        all_errors.extend(errors)

    for index, (row, row_id) in enumerate(zip(rows, row_ids)):
      row_bytes = len(json.dumps(row))
      if row_bytes > _MAX_BYTES_PER_INSERT:
        logger.error(
            "Skipping %s row %s: %d bytes, over the %d byte request cap",
            table.table_id,
            row_id,
            row_bytes,
            _MAX_BYTES_PER_INSERT,
        )
        all_errors.append({
            "index": index,
            "errors": [{
                "reason": "rowTooLarge",
                "message": (
                    f"Row is {row_bytes} bytes, over the"
                    f" {_MAX_BYTES_PER_INSERT} byte request limit."
                ),
            }],
        })
        continue
      if chunk and (
          len(chunk) >= _MAX_ROWS_PER_INSERT
          or chunk_bytes + row_bytes > _MAX_BYTES_PER_INSERT
      ):
        flush()
        chunk = []
        chunk_ids = []
        chunk_bytes = 0
      chunk.append(row)
      chunk_ids.append(row_id)
      chunk_bytes += row_bytes

    if chunk:
      flush()
    return all_errors

  def export_run(
      self,
      run_id: int,
      session: orm.Session,
      force: bool = False,
  ) -> dict[str, int]:
    """Exports one run with its trials, assertions and traces.

    Exporting a run twice is a no-op. Rows carry deterministic row ids, so a
    retry within BigQuery's streaming deduplication window collapses into the
    first insert.

    force skips the already-exported check, and is the one way to get
    duplicates: the deduplication window is about a minute, so forcing a
    re-export later appends a second copy of every row rather than replacing
    the first.

    A partial failure still writes the run row, so the rows that did land are
    joinable and the run stops reading as never exported. The rejected rows are
    recorded on the run, which is where the caller reads the outcome from:
    get_run_export_error.

    Returns the number of rows each table took, which on a partial failure is
    fewer than the number offered.
    """
    run_repo = RunRepository(session)
    run = run_repo.get_by_id(run_id)
    if not run:
      logger.warning("BigQueryExporter: Run %s not found for export", run_id)
      return {"runs": 0, "trials": 0, "assertions": 0, "traces": 0}

    # Before the tables are built, so a run that is already there costs one
    # query instead of a dataset create and four table creates as well.
    if not force and self.is_run_exported(run_id):
      logger.info(
          "BigQueryExporter: Run %s is already exported. Skipping.", run_id
      )
      return {"runs": 0, "trials": 0, "assertions": 0, "traces": 0}

    self.ensure_dataset_and_tables()

    run_row = self.serialize_run(run)

    trial_rows = []
    trial_row_ids = []
    assertion_rows = []
    assertion_row_ids = []
    trace_rows = []
    trace_row_ids = []

    for trial in run.trials:
      trial_rows.append(self.serialize_trial(trial))
      trial_row_ids.append(f"trial-{trial.id}")

      for ar in trial.assertion_results:
        assertion_rows.append({
            "id": ar.id,
            "trial_id": ar.trial_id,
            "run_id": run.id,
            "assertion_type": (
                ar.assertion_snapshot.type.value
                if ar.assertion_snapshot
                and hasattr(ar.assertion_snapshot.type, "value")
                else (
                    str(ar.assertion_snapshot.type)
                    if ar.assertion_snapshot
                    else None
                )
            ),
            "passed": bool(ar.passed),
            "score": ar.score,
            "weight": (
                ar.assertion_snapshot.weight if ar.assertion_snapshot else 1.0
            ),
            "reasoning": ar.reasoning,
            "error_message": ar.error_message,
        })
        assertion_row_ids.append(f"ar-{ar.id}")

      if trial.trace_results:
        for idx, event in enumerate(trial.trace_results):
          event_ts = None
          if isinstance(event, dict) and "timestamp" in event:
            raw_ts = event["timestamp"]
            if isinstance(raw_ts, str):
              try:
                event_ts = datetime.datetime.fromisoformat(
                    raw_ts.replace("Z", "+00:00")
                ).isoformat()
              except (ValueError, TypeError, AttributeError):
                event_ts = None
            elif isinstance(raw_ts, (int, float)):
              try:
                event_ts = datetime.datetime.fromtimestamp(
                    raw_ts, tz=datetime.timezone.utc
                ).isoformat()
              except (ValueError, TypeError, OSError):
                event_ts = None

          trace_rows.append({
              "trial_id": trial.id,
              "run_id": run.id,
              "step_index": idx,
              "event_type": (
                  event.get("type") if isinstance(event, dict) else None
              ),
              "timestamp": event_ts,
              "payload": json.dumps(event) if isinstance(event, dict) else None,
          })
          trace_row_ids.append(f"trace-{trial.id}-{idx}")

    dataset_ref = bigquery.DatasetReference(
        self.client.project, self.dataset_id
    )

    # The run row goes last, after the three tables that hang off it, but it
    # goes whatever those three did. Holding it back on a rejected row left the
    # trial, assertion and trace rows in BigQuery with no run to join to, and
    # nothing anywhere recording that the export had happened at all. The run
    # then read as never exported, so the run page kept offering Sync to
    # BigQuery and every press appended another full copy of the children. A
    # trace event too large for one request is rejected every time, so that
    # loop never ended.
    #
    # Deleting the old children before a forced re-export is the other way to
    # make the button safe, and it does not work here: insert_rows_json is the
    # streaming insertAll API, and rows in the streaming buffer cannot be
    # deleted for some time after they land, so the DML would fail or silently
    # miss the copies it was meant to remove.
    #
    # The partial failure is still recorded on the run below, which is what the
    # badge and the CLI exit code read.
    errors = {}
    accepted = {"runs": 0, "trials": 0, "assertions": 0, "traces": 0}

    if trial_rows:
      err = self._insert_chunked(
          dataset_ref.table("prism_eval_trials"), trial_rows, trial_row_ids
      )
      if err:
        errors["trials"] = err
      accepted["trials"] = len(trial_rows) - len(err)

    if assertion_rows:
      err = self._insert_chunked(
          dataset_ref.table("prism_eval_assertion_results"),
          assertion_rows,
          assertion_row_ids,
      )
      if err:
        errors["assertions"] = err
      accepted["assertions"] = len(assertion_rows) - len(err)

    if trace_rows:
      err = self._insert_chunked(
          dataset_ref.table("prism_eval_traces"), trace_rows, trace_row_ids
      )
      if err:
        errors["traces"] = err
      accepted["traces"] = len(trace_rows) - len(err)

    err = self._insert_chunked(
        dataset_ref.table("prism_eval_runs"), [run_row], [f"run-{run.id}"]
    )
    if err:
      errors["runs"] = err
    accepted["runs"] = 1 - len(err)
    if accepted["runs"]:
      # The run row is in BigQuery, which is the question check_run_exported
      # asks, so the memo can answer it. Whether the export was complete is a
      # separate answer and lives in bigquery_export_error.
      with _export_lock:
        _exported_runs.add(run.id)

    if errors:
      # Counts, not the row error dicts. Each one carries reason, location,
      # debugInfo and message, and this text is stored and rendered verbatim
      # in the run page tooltip. See _displayable_error.
      rejected = ", ".join(
          f"{table}: {len(row_errors)}" for table, row_errors in errors.items()
      )
      err_msg = (
          f"BigQuery rejected rows from the export ({rejected}). The details"
          " are in the server log."
      )
      logger.error("BigQuery export encountered errors: %s", errors)
      record_run_export_error(session, run.id, err_msg)
    else:
      logger.info(
          "Successfully exported Run %s to BigQuery (%s trials, %s assertions,"
          " %s traces)",
          run.id,
          accepted["trials"],
          accepted["assertions"],
          accepted["traces"],
      )
      record_run_export_error(session, run.id, None)

    # Rows accepted, not rows offered. The CLI sums these and signs off with
    # "Total: N trials", which read as a clean export over rows BigQuery had
    # rejected.
    return accepted

  def export_run_async(
      self,
      run_id: int,
      session_factory: Callable[[], orm.Session],
      force: bool = False,
  ) -> threading.Thread | None:
    """Runs export_run in a background daemon thread.

    Returns None without starting a thread when an export for this run is
    already in flight.
    """
    with _export_lock:
      if run_id in _active_exports:
        logger.info(
            "BigQueryExporter: Run %s export is already in flight. Skipping"
            " duplicate trigger.",
            run_id,
        )
        return None
      _active_exports.add(run_id)

    def _target():
      try:
        with session_factory() as session:
          self.export_run(run_id, session, force=force)
      except Exception as e:  # pylint: disable=broad-exception-caught
        logger.exception("Failed background BigQuery export for run %s", run_id)
        # A fresh session: whatever raised may have left the other one unusable.
        with session_factory() as session:
          record_run_export_error(session, run_id, _displayable_error(e))
      finally:
        with _export_lock:
          _active_exports.discard(run_id)

    thread = threading.Thread(
        target=_target, name=f"bq-export-run-{run_id}", daemon=True
    )
    thread.start()
    return thread
