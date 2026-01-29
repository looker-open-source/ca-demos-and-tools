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

from prism.server.schemas.execution import RunSchema
import pydantic


class DailyAccuracySchema(pydantic.BaseModel):
  """Daily accuracy score."""

  date: str
  accuracy: float | None


class DailyRunCountSchema(pydantic.BaseModel):
  """Daily evaluation run count."""

  date: str
  count: int


class AgentStatusSchema(pydantic.BaseModel):
  """Agent status information."""

  id: int
  name: str
  status: str  # "Online" | "Offline" | "Training"
  version: str | None = None


class DashboardStats(pydantic.BaseModel):
  """Statistics for the dashboard."""

  total_agents: int
  active_agents_count: int  # Agents evaluated in last 7 days
  active_agents_24h: int  # Agents evaluated in last 24h
  total_runs_7d: int
  avg_accuracy_score: float | None  # Avg of all runs in last 7 days
  accuracy_history: list[DailyAccuracySchema]
  run_volume_history: list[DailyRunCountSchema]
  recent_runs: list[RunSchema]
  agent_statuses: list[AgentStatusSchema]
