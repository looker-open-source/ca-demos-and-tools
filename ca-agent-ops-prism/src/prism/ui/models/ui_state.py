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

"""UI State Models."""

from typing import Any
import uuid

from prism.common.schemas import agent
from prism.common.schemas import execution
import pydantic


class AgentCreateForm(pydantic.BaseModel):
  """Form data for creating a new agent."""

  project_id: str
  location: str
  agent_resource_id: str
  name: str


class AssertItem(pydantic.BaseModel):
  """Represents a single assert in the UI builder."""

  id: int | None = None
  type: str
  params: dict[str, Any] | int | str | float | None = None

  model_config = pydantic.ConfigDict(extra="allow")


class TestCaseState(pydantic.BaseModel):
  """Represents a test case in the UI builder."""

  id: int | None = None
  logical_id: str = pydantic.Field(default_factory=lambda: str(uuid.uuid4()))
  question: str
  asserts: list[AssertItem] = []


class TestCaseModalState(pydantic.BaseModel):
  """State for the test case editor modal."""

  mode: str = "add"  # "add" or "edit"
  index: int | None = None
  question_id: int | None = None
  asserts: list[AssertItem] = []


class AssertionMetric(pydantic.BaseModel):
  """Metrics for a group of assertions."""

  total: int
  passed: int
  failed: int
  pass_rate: float | None


class AssertionSummary(pydantic.BaseModel):
  """Summary metrics for all assertions in a trial."""

  overall: AssertionMetric
  accuracy: AssertionMetric
  diagnostic: AssertionMetric


class RunDetailPageState(pydantic.BaseModel):
  """State for the Run Detail page, containing run and trials data."""

  run: execution.RunSchema
  trials: list[execution.Trial]
