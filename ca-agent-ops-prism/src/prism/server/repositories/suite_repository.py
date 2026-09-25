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

"""Repository for managing TestSuite entities."""

from prism.server.models.suite import TestSuite
from sqlalchemy.orm import Session


class SuiteRepository:
  """CRUD for test suites. Suites are archived, never deleted."""

  def __init__(self, session: Session):
    self.session = session

  def create(
      self,
      name: str,
      description: str | None = None,
      tags: dict[str, str] | None = None,
  ) -> TestSuite:
    """Inserts a suite.

    Flushes rather than commits, so the caller can roll back.
    """
    suite = TestSuite(
        name=name,
        description=description,
        tags=tags or {},
    )
    self.session.add(suite)
    self.session.flush()
    self.session.refresh(suite)
    return suite

  def get_by_id(self, suite_id: int) -> TestSuite | None:
    """Reads one suite, archived or not. None if there is no such row."""
    return self.session.get(TestSuite, suite_id)

  def list_all(self, include_archived: bool = False) -> list[TestSuite]:
    """Lists suites, archived ones only when asked for."""
    query = self.session.query(TestSuite)
    if not include_archived:
      query = query.filter(
          TestSuite.is_archived == False  # pylint: disable=singleton-comparison
      )
    return query.all()

  def update(
      self,
      suite_id: int,
      name: str | None = None,
      description: str | None = None,
      tags: dict[str, str] | None = None,
  ) -> TestSuite:
    """Applies the fields the caller passed. Absent means keep, not clear.

    Raises:
      ValueError: If there is no suite with that id.
    """
    suite = self.get_by_id(suite_id)
    if not suite:
      raise ValueError(f"TestSuite with id {suite_id} not found")

    if name is not None:
      suite.name = name
    if description is not None:
      suite.description = description
    if tags is not None:
      suite.tags = tags

    self.session.flush()
    self.session.refresh(suite)
    return suite

  def archive(self, suite_id: int) -> TestSuite:
    """Hides a suite from list_all. Raises ValueError if there is no row."""
    suite = self.get_by_id(suite_id)
    if not suite:
      raise ValueError(f"TestSuite with id {suite_id} not found")

    suite.is_archived = True
    self.session.flush()
    self.session.refresh(suite)
    return suite

  def unarchive(self, suite_id: int) -> TestSuite:
    """Puts a suite back in list_all. Raises ValueError if there is no row."""
    suite = self.get_by_id(suite_id)
    if not suite:
      raise ValueError(f"TestSuite with id {suite_id} not found")

    suite.is_archived = False
    self.session.flush()
    self.session.refresh(suite)
    return suite
