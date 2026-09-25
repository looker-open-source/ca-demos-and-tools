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

"""Main Prism Client implementation."""

from prism.client.agent_client import AgentsClient
from prism.client.comparison_client import ComparisonClient
from prism.client.dashboard_client import DashboardClient
from prism.client.playground_client import PlaygroundClient
from prism.client.run_client import RunsClient
from prism.client.suite_client import SuitesClient
from prism.client.system_client import SystemClient


class PrismClient:
  """Main Prism Client combining all sub-clients.

  Everything the UI reads or writes goes through a property here. Importing a
  sub-client directly builds a second one outside get_client()'s singleton.
  """

  def __init__(self):
    self._agents = AgentsClient()
    self._suites = SuitesClient()
    self._runs = RunsClient()
    self._playground = PlaygroundClient()
    self._comparison = ComparisonClient()
    self._dashboard = DashboardClient()
    self._system = SystemClient()
    # Same object as runs. Some call sites still say client.trials.
    self._trials = self._runs

  @property
  def agents(self) -> AgentsClient:
    return self._agents

  @property
  def suites(self) -> SuitesClient:
    return self._suites

  @property
  def runs(self) -> RunsClient:
    return self._runs

  @property
  def trials(self) -> RunsClient:
    return self._trials

  @property
  def playground(self) -> PlaygroundClient:
    return self._playground

  @property
  def comparison(self) -> ComparisonClient:
    return self._comparison

  @property
  def dashboard(self) -> DashboardClient:
    return self._dashboard

  @property
  def system(self) -> SystemClient:
    return self._system
