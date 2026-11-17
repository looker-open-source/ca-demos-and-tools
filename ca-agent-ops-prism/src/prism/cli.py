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

"""Stateless CLI entrypoints for operational Prism tasks."""

import argparse
import logging
import os
import sys
from typing import Sequence

import alembic.command
import alembic.config
from prism.server import db
from prism.server.clients import gemini_data_analytics_client
from prism.server.repositories import example_repository
from prism.server.repositories import schedule_repository
from prism.server.repositories import suite_repository
from prism.server.services import execution_service
from prism.server.services import schedule_service
from prism.server.services import snapshot_service

logger = logging.getLogger(__name__)


def _run_migrations() -> None:
  """Upgrades the database schema to head without booting the WSGI server."""
  config_path = "alembic.ini"
  if not os.path.exists(config_path):
    config_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../alembic.ini")
    )
  logger.info("Running migrations using config: %s", config_path)
  alembic.command.upgrade(alembic.config.Config(config_path), "head")


def run_trigger_schedules(
    limit: int = 20,
    run_migrations: bool = False,
) -> int:
  """Claims due schedules and queues evaluation runs once, then exits."""
  if run_migrations:
    _run_migrations()

  with db.SessionLocal() as session:
    with gemini_data_analytics_client.GeminiDataAnalyticsClient(
        project=""
    ) as gda_client:
      suite_repo = suite_repository.SuiteRepository(session)
      example_repo = example_repository.ExampleRepository(session)
      snap_service = snapshot_service.SnapshotService(
          session, suite_repo, example_repo
      )
      exec_service = execution_service.ExecutionService(
          session=session,
          snapshot_service=snap_service,
          client=gda_client,
      )
      sched_repo = schedule_repository.ScheduleRepository(session)
      sched_service = schedule_service.ScheduleService(
          session=session,
          schedule_repository=sched_repo,
          execution_service=exec_service,
      )
      result = sched_service.process_due_schedules(limit=limit)
      logger.info(
          "Completed schedule tick at %s: triggered=%d skipped_overlap=%d"
          " failed=%d",
          result.checked_at.isoformat(),
          len(result.triggered_run_ids),
          len(result.skipped_overlap_schedule_ids),
          len(result.failed_schedule_ids),
      )
      return 0


def build_parser() -> argparse.ArgumentParser:
  """Builds the argument parser for `python -m prism.cli`."""
  parser = argparse.ArgumentParser(
      prog="prism.cli",
      description="Prism operational CLI.",
  )
  subparsers = parser.add_subparsers(dest="command", required=True)

  trigger = subparsers.add_parser(
      "trigger-schedules",
      help="Claim due evaluation schedules and queue PENDING runs.",
  )
  trigger.add_argument(
      "--limit",
      type=int,
      default=20,
      help="Maximum number of due schedules to process in one invocation.",
  )
  trigger.add_argument(
      "--run-migrations",
      action="store_true",
      help="Run Alembic migrations to head before checking schedules.",
  )
  return parser


def main(argv: Sequence[str] | None = None) -> int:
  """CLI entrypoint."""
  logging.basicConfig(
      level=logging.INFO,
      format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
      handlers=[logging.StreamHandler(sys.stdout)],
  )
  args = build_parser().parse_args(argv)
  if args.command == "trigger-schedules":
    return run_trigger_schedules(
        limit=args.limit,
        run_migrations=args.run_migrations,
    )
  return 1


if __name__ == "__main__":
  sys.exit(main())
