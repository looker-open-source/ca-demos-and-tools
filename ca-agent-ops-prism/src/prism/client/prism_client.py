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
from prism.client.playground_client import PlaygroundClient
from prism.client.run_client import RunsClient
from prism.client.suggestion_client import SuggestionClient
from prism.client.suite_client import SuitesClient
from prism.client.system_client import SystemClient


class PrismClient:
  """Main Prism Client combining all sub-clients."""

  def __init__(self):
    self._agents = AgentsClient()
    self._suites = SuitesClient()
    self._runs = RunsClient()
    self._playground = PlaygroundClient()
    self._suggestion = SuggestionClient()
    self._comparison = ComparisonClient()
    self._system = SystemClient()
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
  def suggestion(self) -> SuggestionClient:
    return self._suggestion

  @property
  def comparison(self) -> ComparisonClient:
    return self._comparison

  @property
  def system(self) -> SystemClient:
    return self._system
