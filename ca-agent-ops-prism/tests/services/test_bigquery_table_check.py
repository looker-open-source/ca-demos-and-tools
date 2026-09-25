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

"""Checking an agent's BigQuery tables against BigQuery.

The form only ever checked that a path had three dotted parts. A typo in the
dataset, or a table the service account cannot read, passed that check and
first showed up as a run where every trial failed. These tests pin the two
things that make the check worth having: it asks BigQuery, and it says which
of the two went wrong.
"""

from unittest import mock

from google.api_core import exceptions as gcp_exceptions
from prism.server.repositories import agent_repository
from prism.server.services import agent_service
import pytest
from sqlalchemy.orm import Session


@pytest.fixture(name="service")
def _service(db_session: Session) -> agent_service.AgentService:
  repo = agent_repository.AgentRepository(db_session)
  return agent_service.AgentService(db_session, repo)


@pytest.fixture(name="bq")
def _bq():
  """The BigQuery client the service builds, with get_table stubbed."""
  with mock.patch.object(agent_service, "bigquery") as bigquery:
    yield bigquery.Client.return_value


def test_a_readable_table_passes(service, bq):
  bq.get_table.return_value = mock.Mock()

  results = service.check_bigquery_tables(["proj.ds.tab"])

  assert results == [
      {"table": "proj.ds.tab", "status": "ok", "message": "Found."}
  ]
  bq.get_table.assert_called_once_with("proj.ds.tab")


def test_a_missing_table_is_not_a_permissions_problem(service, bq):
  """The two failures need different fixes, so they cannot read the same."""
  bq.get_table.side_effect = gcp_exceptions.NotFound("nope")

  [result] = service.check_bigquery_tables(["proj.ds.typo"])

  assert result["status"] == "not_found"
  assert "permission" not in result["message"].lower()


def test_a_table_the_caller_cannot_read_says_so(service, bq):
  """The path is right and the grant is missing. Name the grant."""
  bq.get_table.side_effect = gcp_exceptions.Forbidden("denied")

  [result] = service.check_bigquery_tables(["proj.ds.tab"])

  assert result["status"] == "denied"
  assert "bigquery.tables.get" in result["message"]


def test_a_malformed_path_never_reaches_bigquery(service, bq):
  """Two dotted parts is not a table, and BigQuery would only say so slower."""
  results = service.check_bigquery_tables(["proj.ds"])

  assert results[0]["status"] == "invalid"
  bq.get_table.assert_not_called()


@pytest.mark.parametrize("path", ["", ".", "proj..tab", "a.b.c.d"])
def test_every_shape_that_is_not_a_table_path_is_rejected(service, bq, path):
  assert service.check_bigquery_tables([path])[0]["status"] == "invalid"
  bq.get_table.assert_not_called()


def test_one_bad_table_does_not_hide_the_rest(service, bq):
  """The whole list is checked, so one round trip fixes every path at once."""
  bq.get_table.side_effect = [
      mock.Mock(),
      gcp_exceptions.NotFound("nope"),
      mock.Mock(),
  ]

  results = service.check_bigquery_tables(["p.d.a", "p.d.b", "p.d.c"])

  assert [r["status"] for r in results] == ["ok", "not_found", "ok"]


def test_results_come_back_in_the_order_they_were_given(service, bq):
  """The UI badges them against the textarea, line for line."""
  bq.get_table.return_value = mock.Mock()

  results = service.check_bigquery_tables(["p.d.c", "p.d.a", "p.d.b"])

  assert [r["table"] for r in results] == ["p.d.c", "p.d.a", "p.d.b"]


def test_an_unusable_client_still_reports_every_table(service):
  """The caller counts the entries against the tables it passed.

  Returning a single entry for the whole list read as "1 of 1 tables could not
  be read" over three unchecked tables, and left the other two badges with no
  line beside them. The client is still only built once.
  """
  with mock.patch.object(agent_service, "bigquery") as bigquery:
    bigquery.Client.side_effect = RuntimeError("no credentials")

    results = service.check_bigquery_tables(["p.d.a", "p.d.b", "p.d.c"])

  assert [r["table"] for r in results] == ["p.d.a", "p.d.b", "p.d.c"]
  assert {r["status"] for r in results} == {"error"}
  bigquery.Client.assert_called_once()


def test_the_client_is_built_against_a_project_that_exists(service):
  """A BigQuery client needs a project even to read metadata.

  Taking it off the first table means the check works with no default project
  configured, which the server running under a bare service account has.
  """
  with mock.patch.object(agent_service, "bigquery") as bigquery:
    service.check_bigquery_tables(["other.ds.tab"])

  bigquery.Client.assert_called_once_with(project="other")


def test_a_malformed_first_line_does_not_pick_the_project(service):
  """The invalid line is skipped before a client exists."""
  with mock.patch.object(agent_service, "bigquery") as bigquery:
    service.check_bigquery_tables(["nope", "other.ds.tab"])

  bigquery.Client.assert_called_once_with(project="other")


def test_one_client_serves_the_whole_list(service):
  """Building a client per table pays for credentials discovery per table."""
  with mock.patch.object(agent_service, "bigquery") as bigquery:
    service.check_bigquery_tables(["p.d.a", "p.d.b", "p.d.c"])

  bigquery.Client.assert_called_once()


def test_an_unexpected_failure_is_not_reported_as_a_missing_table(service, bq):
  """A timeout is not a typo, and telling the user to fix the path is wrong."""
  bq.get_table.side_effect = gcp_exceptions.ServiceUnavailable("try later")

  [result] = service.check_bigquery_tables(["p.d.a"])

  assert result["status"] == "error"


def test_checking_nothing_asks_bigquery_nothing(service):
  with mock.patch.object(agent_service, "bigquery") as bigquery:
    assert service.check_bigquery_tables([]) == []

  bigquery.Client.assert_not_called()
