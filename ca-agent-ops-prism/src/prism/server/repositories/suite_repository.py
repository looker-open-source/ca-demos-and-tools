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

import logging

from prism.server.models.suite import TestSuite
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class SuiteRepository:
  """Repository for TestSuite operations."""

  def __init__(self, session: Session):
    self.session = session

  def create(
      self,
      name: str,
      description: str | None = None,
      tags: dict[str, str] | None = None,
  ) -> TestSuite:
    """Creates a new test suite."""
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
    """Retrieves a suite by ID."""
    return self.session.get(TestSuite, suite_id)

  def list_all(self, include_archived: bool = False) -> list[TestSuite]:
    """Lists all suites."""
    query = self.session.query(TestSuite)
    if not include_archived:
      query = query.filter(TestSuite.is_archived == False)  # pylint: disable=singleton-comparison
    return query.all()

  def update(
      self,
      suite_id: int,
      name: str | None = None,
      description: str | None = None,
      tags: dict[str, str] | None = None,
  ) -> TestSuite:
    """Updates a test suite."""
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
    """Archives a test suite."""
    suite = self.get_by_id(suite_id)
    if not suite:
      raise ValueError(f"TestSuite with id {suite_id} not found")

    suite.is_archived = True
    self.session.flush()
    self.session.refresh(suite)
    return suite

  def unarchive(self, suite_id: int) -> TestSuite:
    """Unarchives a test suite."""
    suite = self.get_by_id(suite_id)
    if not suite:
      raise ValueError(f"TestSuite with id {suite_id} not found")

    suite.is_archived = False
    self.session.flush()
    self.session.refresh(suite)
    return suite
