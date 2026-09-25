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

"""The contract check_bigquery_tables gives its caller, and what it may say.

Two things. The caller badges the results against the textarea line for line
and prints "n of len(results) tables could not be read", so there has to be
one entry per table however the check fails. Stopping at the first failure
read as "1 of 1 tables could not be read" over five unchecked tables.

And the entries are rendered verbatim on a page prism does not authenticate.
A BigQuery exception names the dataset, the table and the service account, so
the unexpected arms say what happened and leave the exception in the log.
tests/services/test_bigquery_table_check.py covers the classification of the
failures that are expected.
"""

from __future__ import annotations

from unittest import mock

from prism.server.repositories import agent_repository
from prism.server.services import agent_service
import pytest
from sqlalchemy.orm import Session


@pytest.fixture(name="service")
def _service(db_session: Session) -> agent_service.AgentService:
  return agent_service.AgentService(
      db_session, agent_repository.AgentRepository(db_session)
  )


def test_a_server_with_no_credentials_still_answers_for_every_table(
    service: agent_service.AgentService,
):
  """The client is built once, and failing to build it checked nothing.

  The caller counts the entries against the paths it passed, so one entry for
  the whole list makes four of the five tables silently disappear from the
  report.
  """
  with mock.patch.object(agent_service, "bigquery") as bigquery:
    bigquery.Client.side_effect = RuntimeError(
        "Could not automatically determine credentials for prism-runner@"
        "secret-project.iam.gserviceaccount.com"
    )

    results = service.check_bigquery_tables(
        ["p.d.a", "p.d.b", "p.d.c", "p.d.d", "p.d.e"]
    )

  assert [r["table"] for r in results] == [
      "p.d.a",
      "p.d.b",
      "p.d.c",
      "p.d.d",
      "p.d.e",
  ]
  assert [r["status"] for r in results] == ["error"] * 5
  # One attempt, not one per table. Credentials discovery is the expensive
  # part and it fails the same way every time.
  assert bigquery.Client.call_count == 1


def test_a_path_that_is_not_a_table_is_still_reported_as_such(
    service: agent_service.AgentService,
):
  """A malformed line never needed BigQuery, so it keeps its own verdict.

  Reporting it as unreachable would send the user off to check credentials
  over a typo they can see.
  """
  with mock.patch.object(agent_service, "bigquery") as bigquery:
    bigquery.Client.side_effect = RuntimeError("no credentials")

    results = service.check_bigquery_tables(["p.d.a", "nope", "p.d.b"])

  assert [r["status"] for r in results] == ["error", "invalid", "error"]


def test_an_unexpected_get_table_failure_keeps_its_exception_in_the_log(
    service: agent_service.AgentService, caplog: pytest.LogCaptureFixture
):
  """Not found and denied are handled by name. Everything else lands here.

  A malformed dataset id comes back as a BadRequest whose text quotes the
  project and the dataset, and it went onto the page as the table's message.
  """
  with mock.patch.object(agent_service, "bigquery") as bigquery:
    bigquery.Client.return_value.get_table.side_effect = RuntimeError(
        "400 Invalid dataset ID secret-project:internal_finance"
    )

    [result] = service.check_bigquery_tables(["p.d.a"])

  assert result["status"] == "error"
  assert "internal_finance" not in result["message"]
  assert "server log" in result["message"]
  assert "internal_finance" in caplog.text
