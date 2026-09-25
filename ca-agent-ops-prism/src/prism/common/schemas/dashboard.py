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

"""Schemas for Dashboard."""

from prism.common.schemas.execution import RunSchema
import pydantic


class DailyAccuracySchema(pydantic.BaseModel):
  """Daily accuracy score."""

  date: str
  accuracy: float | None


class DailyRunCountSchema(pydantic.BaseModel):
  """Daily evaluation run count."""

  date: str
  count: int


class DashboardStats(pydantic.BaseModel):
  """Statistics for the dashboard."""

  accuracy_history: list[DailyAccuracySchema]
  run_volume_history: list[DailyRunCountSchema]
  recent_runs: list[RunSchema]
