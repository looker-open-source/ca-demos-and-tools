#!/usr/bin/env python3
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

"""CLI utility to export or backfill Prism evaluation runs to BigQuery."""

import argparse
import logging
import sys

from prism.server import db
from prism.server.config import settings
from prism.server.models.run import Run
from prism.server.repositories.run_repository import RunRepository
from prism.server.services.bigquery_exporter import BigQueryExporter
from prism.server.services.bigquery_exporter import get_run_export_error

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
logger = logging.getLogger(__name__)


def parse_args():
  parser = argparse.ArgumentParser(
      description="Export Prism evaluation runs to BigQuery."
  )
  parser.add_argument(
      "--run-id",
      type=int,
      help="Specific Run ID to export.",
  )
  parser.add_argument(
      "--agent-id",
      type=int,
      help="Export all completed runs for a specific agent.",
  )
  parser.add_argument(
      "--all",
      action="store_true",
      help="Export all completed runs in the database.",
  )
  parser.add_argument(
      "--project",
      type=str,
      default=settings.bigquery_export_project,
      help=(
          "Target GCP Project for BigQuery (defaults to"
          " BIGQUERY_EXPORT_PROJECT)."
      ),
  )
  parser.add_argument(
      "--dataset",
      type=str,
      default=settings.bigquery_export_dataset,
      help="Target BigQuery Dataset ID (defaults to BIGQUERY_EXPORT_DATASET).",
  )
  parser.add_argument(
      "--location",
      type=str,
      default=settings.bigquery_export_location,
      help=(
          "Target BigQuery Location (defaults to BIGQUERY_EXPORT_LOCATION /"
          " US)."
      ),
  )
  parser.add_argument(
      "--force",
      action="store_true",
      help=(
          "Re-export even if the run is already in BigQuery. This appends"
          " rather than replaces, so past the streaming deduplication window"
          " it leaves a second copy of every row."
      ),
  )
  return parser.parse_args()


def main():
  args = parse_args()

  if not args.run_id and not args.agent_id and not args.all:
    print(
        "Error: Must specify at least one of --run-id, --agent-id, or --all.",
        file=sys.stderr,
    )
    sys.exit(1)

  exporter = BigQueryExporter(
      project_id=args.project,
      dataset_id=args.dataset,
      location=args.location,
  )

  with db.SessionLocal() as session:
    run_repo = RunRepository(session)

    if args.run_id:
      runs_to_export = [run_repo.get_by_id(args.run_id)]
    elif args.agent_id:
      runs = session.query(Run).filter(Run.agent_id == args.agent_id).all()
      runs_to_export = [
          r
          for r in runs
          if getattr(r.status, "name", str(r.status)) == "COMPLETED"
      ]
    elif args.all:
      runs = session.query(Run).all()
      runs_to_export = [
          r
          for r in runs
          if getattr(r.status, "name", str(r.status)) == "COMPLETED"
      ]

    runs_to_export = [r for r in runs_to_export if r is not None]

    if not runs_to_export:
      logger.warning("No eligible runs found for BigQuery export.")
      return

    logger.info(
        "Starting export of %s run(s) to BigQuery dataset '%s'...",
        len(runs_to_export),
        exporter.dataset_id,
    )

    total_stats = {"runs": 0, "trials": 0, "assertions": 0, "traces": 0}
    failed_runs = []
    for run in runs_to_export:
      stats = exporter.export_run(run.id, session, force=args.force)
      for k in total_stats:
        total_stats[k] += stats.get(k, 0)
      # The counts are rows accepted, so a short one is the only sign of a
      # rejection, and nobody knows what the run should have totalled. BigQuery
      # rejects rows one at a time, so without this a batch with a schema drift
      # still printed a total that read as clean.
      if get_run_export_error(run.id):
        failed_runs.append(run.id)

    logger.info(
        "BigQuery export finished. BigQuery accepted %s runs, %s trials, %s"
        " assertions, %s traces.",
        total_stats["runs"],
        total_stats["trials"],
        total_stats["assertions"],
        total_stats["traces"],
    )
    if failed_runs:
      logger.error(
          "%s of %s runs had rows rejected: %s. See the errors above for the"
          " table and the reason.",
          len(failed_runs),
          len(runs_to_export),
          ", ".join(str(r) for r in failed_runs),
      )
      sys.exit(1)


if __name__ == "__main__":
  main()
