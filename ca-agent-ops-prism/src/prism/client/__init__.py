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

"""Prism API Client."""

from prism.client.agent_client import AgentsClient
from prism.client.prism_client import PrismClient
from prism.client.run_client import RunsClient
from prism.client.suite_client import SuitesClient


__all__ = [
    "PrismClient",
    "AgentsClient",
    "SuitesClient",
    "RunsClient",
    "get_client",
]


_CLIENT: PrismClient | None = None


def get_client() -> PrismClient:
  """Factory to get the configured Prism Client."""
  global _CLIENT
  if _CLIENT is None:
    _CLIENT = PrismClient()
  return _CLIENT
