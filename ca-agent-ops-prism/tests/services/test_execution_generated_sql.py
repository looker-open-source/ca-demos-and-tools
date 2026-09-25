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

"""The playground reads the SQL the agent ran off the trace.

execute_ephemeral_test tested for it with hasattr. These are proto-plus
messages, and reading an unset singular message field returns a default
submessage, so the test never failed and the assignment ran for every system
message. In a real trace the SQL is followed by the rows, the chart and the
final answer, and each one wrote "" over it, so the SQL panel was always blank.

tests/services/test_playground_service.py cannot catch this. It replaces
ExecutionService with a mock, so nothing there parses a trace.
"""

from typing import Any
from unittest import mock

from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import BigQueryConfig
from prism.common.schemas.trace import AskQuestionResponse
from prism.common.schemas.trace import DurationMetrics
from prism.server.models.agent import Agent
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.execution_service import ExecutionService
from prism.server.services.snapshot_service import SnapshotService
import pytest
from sqlalchemy.orm import Session

_QUESTION = "How many orders were there?"
_ANSWER = "There were 128 orders."
_SQL = "SELECT COUNT(*) AS order_count FROM `demo.orders`"


def _trace(with_sql: bool = True) -> list[dict[str, Any]]:
  """The messages the service streams back, in the order it sends them.

  The SQL comes before the rows, the chart and the answer, which is what made
  the bug show up on every trace that had any SQL in it. generated_sql and
  result share a oneof, so the rows message is a data message with no SQL.
  """
  messages: list[dict[str, Any]] = []
  if with_sql:
    messages.append({"system_message": {"data": {"generated_sql": _SQL}}})
  messages.append({
      "system_message": {"data": {"result": {"data": [{"order_count": "128"}]}}}
  })
  messages.append({
      "system_message": {
          "chart": {"result": {"vega_config": {"mark": {"type": "bar"}}}}
      }
  })
  messages.append({
      "system_message": {
          "text": {"text_type": "FINAL_RESPONSE", "parts": [_ANSWER]}
      }
  })
  return messages


@pytest.fixture(name="agent")
def _agent(db_session: Session) -> Agent:
  return AgentRepository(db_session).create(
      name="SQL Bot",
      config=AgentConfig(
          project_id="p",
          location="l",
          agent_resource_id="r",
          datasource=BigQueryConfig(tables=["t1"]),
      ),
  )


def _service(
    db_session: Session, trace: list[dict[str, Any]]
) -> ExecutionService:
  """The real service over a canned trace, with the remote call stubbed."""
  client = mock.MagicMock()
  client.get_datasource_kind.return_value = "bigquery"
  client.ask_question.return_value = AskQuestionResponse(
      response=trace, duration=DurationMetrics(total_duration=42)
  )
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)
  return ExecutionService(db_session, snapshot_service, client)


def test_the_sql_survives_the_messages_that_follow_it(
    db_session: Session, agent: Agent
):
  """Three system messages arrive after the SQL and none of them carries any.

  Each one used to overwrite generated_sql with the empty default, so the
  playground reported no SQL for a query it had just run.
  """
  service = _service(db_session, _trace())

  result = service.execute_ephemeral_test(agent.id, _QUESTION, [])

  assert result.generated_sql == _SQL
  assert result.response_text == _ANSWER


def test_a_trace_with_no_sql_in_it_reports_no_sql(
    db_session: Session, agent: Agent
):
  """Guards the check above.

  A test that reads the last data message would pass either way, so the no-SQL
  case has to stay empty.
  """
  service = _service(db_session, _trace(with_sql=False))

  result = service.execute_ephemeral_test(agent.id, _QUESTION, [])

  assert result.generated_sql == ""
  assert result.response_text == _ANSWER
