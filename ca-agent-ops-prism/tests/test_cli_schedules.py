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

"""Unit tests for the stateless prism.cli schedule trigger."""

import datetime
from unittest import mock

from prism import cli
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import BigQueryConfig
from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
from prism.server.models.run import Run
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.schedule_repository import ScheduleRepository
from prism.server.repositories.suite_repository import SuiteRepository
import sqlalchemy
from sqlalchemy import orm

_UTC = datetime.timezone.utc


def test_cli_trigger_schedules_claims_due_schedule_and_exits_zero(
    db_session: orm.Session,
):
  """Verifies trigger-schedules claims due schedules and queues PENDING runs."""
  agent = AgentRepository(db_session).create(
      name="CLI Agent",
      config=AgentConfig(
          project_id="cli-proj",
          location="global",
          agent_resource_id="cli-ag",
          datasource=BigQueryConfig(tables=["cli-proj.ds.t"]),
      ),
  )
  suite = SuiteRepository(db_session).create(name="CLI Suite")
  ExampleRepository(db_session).create(suite.id, "Count rows?")

  past = datetime.datetime.now(_UTC) - datetime.timedelta(minutes=5)
  sched = ScheduleRepository(db_session).create(
      name="CLI Due Schedule",
      agent_id=agent.id,
      test_suite_id=suite.id,
      cadence="HOURLY",
      cron_expression="0 * * * *",
      timezone="UTC",
      generate_suggestions=False,
      concurrency=2,
      is_enabled=True,
      next_run_at=past,
  )

  gda_mock = mock.MagicMock(spec=GeminiDataAnalyticsClient)
  gda_mock.__enter__.return_value = gda_mock
  gda_mock.__exit__.return_value = None
  gda_mock.get_datasource_kind.return_value = "bq"
  gda_mock.get_agent_context.return_value = {"system_instruction": "CLI ctx"}

  with (
      mock.patch(
          "prism.server.clients.gemini_data_analytics_client.GeminiDataAnalyticsClient",
          return_value=gda_mock,
      ),
      mock.patch("prism.cli._run_migrations") as mock_migrations,
  ):
    rc = cli.main(["trigger-schedules", "--limit", "5", "--run-migrations"])

  assert rc == 0
  mock_migrations.assert_called_once()

  db_session.expire_all()
  runs = (
      db_session.execute(
          sqlalchemy.select(Run).where(Run.schedule_id == sched.id)
      )
      .scalars()
      .all()
  )
  assert len(runs) == 1


def test_run_migrations_resolves_local_and_fallback_alembic_ini():
  """Verifies _run_migrations locates alembic.ini from cwd or package root."""
  with (
      mock.patch("prism.cli.os.path.exists", return_value=True),
      mock.patch("prism.cli.alembic.config.Config") as mock_cfg,
      mock.patch("prism.cli.alembic.command.upgrade") as mock_upgrade,
  ):
    cli._run_migrations()  # pylint: disable=protected-access
    mock_cfg.assert_called_once_with("alembic.ini")
    mock_upgrade.assert_called_once_with(mock_cfg.return_value, "head")

  with (
      mock.patch("prism.cli.os.path.exists", return_value=False),
      mock.patch("prism.cli.alembic.config.Config") as mock_cfg_fallback,
      mock.patch("prism.cli.alembic.command.upgrade") as mock_upgrade_fallback,
  ):
    cli._run_migrations()  # pylint: disable=protected-access
    passed_path = mock_cfg_fallback.call_args.args[0]
    assert passed_path.endswith("alembic.ini")
    mock_upgrade_fallback.assert_called_once_with(
        mock_cfg_fallback.return_value, "head"
    )
