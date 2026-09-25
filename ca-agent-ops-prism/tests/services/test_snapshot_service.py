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

"""Unit tests for SnapshotService."""

from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.snapshot_service import SnapshotService
from sqlalchemy.orm import Session


def test_create_snapshot(db_session: Session):
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  service = SnapshotService(db_session, suite_repo, example_repo)

  suite = suite_repo.create(name="Live Suite", tags={"env": "prod"})
  example_repo.create(suite.id, "Q1")

  snapshot = service.create_snapshot(suite.id)

  assert snapshot.original_suite_id == suite.id
  assert snapshot.name == "Live Suite"
  assert snapshot.tags == {"env": "prod"}
  assert len(snapshot.examples) == 1
  assert snapshot.examples[0].question == "Q1"
