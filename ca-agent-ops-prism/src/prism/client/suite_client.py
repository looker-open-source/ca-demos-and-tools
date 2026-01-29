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

"""Suites Client implementation."""

from typing import Any
from typing import Sequence

from fast_depends import Depends
from fast_depends import inject
from prism.client import dependencies
from prism.common.schemas import example as example_schemas
from prism.common.schemas import suite as suite_schemas
from prism.common.schemas.suite import SuiteDetail
from prism.server.services import validation_service
from prism.server.services.suite_service import SuiteService


def _map_suite(model: Any) -> suite_schemas.Suite:
  return suite_schemas.Suite.model_validate(model)


def _map_suite_detail(model: Any) -> SuiteDetail:
  return SuiteDetail.model_validate(model)


class SuitesClient:
  """Suites Client implementation."""

  @inject
  def list_suites(
      self,
      include_archived: bool = False,
      service: SuiteService = Depends(dependencies.get_suite_service),
  ) -> Sequence[suite_schemas.Suite]:

    models = service.list_suites(include_archived=include_archived)
    return [_map_suite(m) for m in models]

  @inject
  def get_suite(
      self,
      suite_id: int,
      service: SuiteService = Depends(dependencies.get_suite_service),
  ) -> SuiteDetail | None:

    model = service.get_suite(suite_id)
    return _map_suite_detail(model) if model else None

  @inject
  def get_suites_with_stats(
      self,
      include_archived: bool = False,
      coverage: str | None = None,
      service: SuiteService = Depends(dependencies.get_suite_service),
  ) -> list[suite_schemas.SuiteWithStats]:
    return service.get_suites_with_stats(
        include_archived=include_archived, coverage=coverage
    )

  @inject
  def create_suite(
      self,
      name: str,
      description: str | None = None,
      service: SuiteService = Depends(dependencies.get_suite_service),
  ) -> suite_schemas.Suite:

    model = service.create_suite(name=name, description=description)
    return _map_suite(model)

  @inject
  def update_suite(
      self,
      suite_id: int,
      name: str | None = None,
      description: str | None = None,
      service: SuiteService = Depends(dependencies.get_suite_service),
  ) -> suite_schemas.Suite:

    model = service.update_suite(
        suite_id=suite_id, name=name, description=description
    )
    return _map_suite(model)

  @inject
  def list_examples(
      self,
      suite_id: int,
      include_archived: bool = False,
      service: SuiteService = Depends(dependencies.get_suite_service),
  ) -> Sequence[example_schemas.Example]:
    models = service.list_examples(
        suite_id=suite_id, include_archived=include_archived
    )
    return [example_schemas.Example.model_validate(m) for m in models]

  @inject
  def sync_suite(
      self,
      suite_id: int,
      questions: list[dict],
      service: SuiteService = Depends(dependencies.get_suite_service),
  ) -> list[dict]:
    return service.sync_suite(suite_id=suite_id, questions=questions)

  @inject
  def add_example(
      self,
      suite_id: int,
      question: str,
      asserts: list[dict[str, Any]] | None = None,
      service: SuiteService = Depends(dependencies.get_suite_service),
  ) -> suite_schemas.Example:
    """Adds a new example to a test suite."""
    example = service.add_example(suite_id, question, asserts or [])
    return suite_schemas.Example.model_validate(example)

  @inject
  def delete_example(
      self,
      example_id: int,
      service: SuiteService = Depends(dependencies.get_suite_service),
  ) -> None:
    """Deletes an example by its ID."""
    service.delete_example(example_id)

  @inject
  def validate_assertion(
      self,
      assertion_data: dict[str, Any],
  ) -> str | None:
    """Validates assertion data against Pydantic schemas."""
    return validation_service.validate_assertion(assertion_data)

  @inject
  def parse_yaml_safely(
      self,
      yaml_str: str,
  ) -> tuple[dict[str, Any] | None, str | None]:
    """Parses YAML string safely."""
    return validation_service.parse_yaml_safely(yaml_str)
