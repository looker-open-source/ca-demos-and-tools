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

"""Unit tests for SchedulesClient and RunsClient schedule_id filtering."""

import datetime
from unittest import mock

import fast_depends
from prism.client import dependencies
from prism.client import get_client
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import BigQueryConfig
from prism.common.schemas.schedule import ScheduleCadence
from prism.common.schemas.schedule import ScheduleCreate
from prism.common.schemas.schedule import ScheduleUpdate
from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
from sqlalchemy import orm

_UTC = datetime.timezone.utc


def test_schedules_client_end_to_end_facade(db_session: orm.Session):
  """Exercises SchedulesClient CRUD, preview, trigger, and schedule filters."""
  del db_session  # Ensures schema exists on test DB.
  client = get_client()

  gda_mock = mock.MagicMock(spec=GeminiDataAnalyticsClient)
  gda_mock.get_datasource_kind.return_value = "bq"
  gda_mock.get_agent_context.return_value = {"system_instruction": "Facade ctx"}

  with fast_depends.dependency_provider.scope(
      dependencies.get_gda_client, lambda: gda_mock
  ):
    agent = client.agents.onboard_gcp_agent(
        name="Facade Agent",
        config=AgentConfig(
            project_id="p1",
            location="global",
            agent_resource_id="a1",
            datasource=BigQueryConfig(tables=["p1.d.t"]),
        ),
    )
    suite = client.suites.create_suite(name="Facade Suite")
    client.suites.add_example(suite.id, question="Total sales?")

    preview = client.schedules.preview_next_runs(
        "0 9 * * *",
        timezone="UTC",
        count=3,
        after=datetime.datetime(2026, 10, 30, 8, 0, tzinfo=_UTC),
    )
    assert len(preview) == 3

    created = client.schedules.create_schedule(
        ScheduleCreate(
            name="Facade Daily",
            agent_id=agent.id,
            test_suite_id=suite.id,
            cadence=ScheduleCadence.DAILY,
            cron_expression="0 9 * * *",
            timezone="UTC",
            concurrency=2,
            generate_suggestions=False,
            is_enabled=True,
        )
    )
    assert created.agent_name == "Facade Agent"
    assert created.suite_name == "Facade Suite"

    fetched = client.schedules.get_schedule(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert client.schedules.get_schedule(999999) is None

    updated = client.schedules.update_schedule(
        created.id, ScheduleUpdate(name="Facade Hourly", concurrency=4)
    )
    assert updated.name == "Facade Hourly"
    assert updated.concurrency == 4

    paused = client.schedules.pause_schedule(created.id)
    assert not paused.is_enabled
    resumed = client.schedules.resume_schedule(created.id)
    assert resumed.is_enabled

    triggered_run = client.schedules.trigger_schedule_now(created.id)
    assert triggered_run.schedule_id == created.id
    assert triggered_run.schedule_name == "Facade Hourly"

    # Unscheduled sibling run to verify schedule_id filter on RunsClient.
    unscheduled_run = client.runs.create_run(
        agent_id=agent.id, test_suite_id=suite.id
    )
    assert unscheduled_run.schedule_id is None

    filtered_runs = client.runs.list_runs(schedule_id=created.id)
    assert [r.id for r in filtered_runs] == [triggered_run.id]

    # create_schedule computes next_run_at from the wall clock, so the tick has
    # to be relative to it. A fixed date stopped being due once it passed.
    assert created.next_run_at is not None
    tick = client.schedules.process_due_schedules(
        now=created.next_run_at + datetime.timedelta(hours=1)
    )
    assert tick.skipped_overlap_schedule_ids == [created.id]

    archived = client.schedules.archive_schedule(created.id)
    assert archived.is_archived
    assert not client.schedules.list_schedules(include_archived=False)
    assert len(client.schedules.list_schedules(include_archived=True)) == 1

    restored = client.schedules.unarchive_schedule(created.id)
    assert not restored.is_archived
    assert not restored.is_enabled
