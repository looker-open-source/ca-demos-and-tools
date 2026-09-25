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

"""Three answers to "is this run in BigQuery", where there used to be two.

The check was a boolean. A denied credential, a bad dataset id or a BigQuery
outage came back False, which is the same answer as "the run is not there",
and the caller turned that into a failed export on the run page. The export it
was describing was fine, and the one that was actually broken read the same.

is_run_exported keeps the boolean for the callers that only act on a yes, and
it folds unknown into False so those callers stay careful.
tests/services/test_bigquery_export_contract.py covers the memo and the
logging; this file covers the third answer.
"""

from __future__ import annotations

from unittest import mock

from google.api_core import exceptions
from prism.server.services.bigquery_exporter import BigQueryExporter
from prism.server.services.bigquery_exporter import EXPORT_STATE_EXPORTED
from prism.server.services.bigquery_exporter import EXPORT_STATE_NOT_EXPORTED
from prism.server.services.bigquery_exporter import EXPORT_STATE_UNKNOWN
import pytest


def _exporter(answer) -> BigQueryExporter:
  """An exporter whose lookup yields answer, or raises it."""
  client = mock.MagicMock()
  client.project = "test-project"
  if isinstance(answer, Exception):
    client.query.side_effect = answer
  else:
    client.query.return_value.result.return_value = answer
  return BigQueryExporter(
      project_id="test-project", dataset_id="test_dataset", client=client
  )


@pytest.mark.parametrize(
    "answer,expected",
    [
        ([(1,)], EXPORT_STATE_EXPORTED),
        ([], EXPORT_STATE_NOT_EXPORTED),
        (exceptions.NotFound("No such table"), EXPORT_STATE_NOT_EXPORTED),
        (exceptions.Forbidden("denied"), EXPORT_STATE_UNKNOWN),
        (RuntimeError("dataset id is wrong"), EXPORT_STATE_UNKNOWN),
    ],
    ids=["present", "absent", "no-table", "denied", "broken"],
)
def test_a_check_that_could_not_run_is_its_own_answer(answer, expected):
  """A missing table is absence. Nothing else is.

  The table is only created by the first export, so NotFound is the one
  failure that means the run was never exported. A refused credential is not
  evidence about the run at all, and reporting it as absence is what put
  "Failed" on healthy runs.
  """
  assert _exporter(answer).check_run_exported(7) == expected


def test_the_boolean_still_says_no_when_the_answer_is_unknown():
  """export_run reads the boolean before deciding to skip.

  Unknown has to keep reading False there. A True would skip an export that
  may never have happened, and the run would sit unexported with nothing
  recorded against it.
  """
  assert _exporter(exceptions.Forbidden("denied")).is_run_exported(7) is False
