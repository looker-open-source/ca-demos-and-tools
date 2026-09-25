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

"""Unit tests for SuiteRepository."""

from prism.server.repositories.suite_repository import SuiteRepository
from sqlalchemy.orm import Session


def test_create_suite(db_session: Session):
  repo = SuiteRepository(db_session)
  suite = repo.create(name="My Suite", description="Desc")

  assert suite.id is not None
  assert suite.name == "My Suite"
  assert suite.description == "Desc"
  assert not suite.is_archived


def test_update_suite(db_session: Session):
  repo = SuiteRepository(db_session)
  suite = repo.create(name="Suite 1")

  updated = repo.update(suite.id, name="Suite 2", tags={"a": "b"})
  assert updated.name == "Suite 2"
  assert updated.tags == {"a": "b"}


def test_archive_suite(db_session: Session):
  """Archiving and unarchiving are a round trip."""
  repo = SuiteRepository(db_session)
  suite = repo.create(name="To Archive")

  repo.archive(suite.id)
  assert suite.is_archived

  repo.unarchive(suite.id)
  assert not suite.is_archived
