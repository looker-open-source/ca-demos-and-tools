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

"""Every client method that calls out has to be recordable."""

import inspect

from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
from prism.server.clients.gen_ai_client import GenAIClient
import pytest

# The ways each client gets at a transport. A method that names one is a method
# that reaches the service. _transport_for_location is a third way to get one
# and it names neither attribute, so a method written against it was exempt
# from everything below.
_TRANSPORTS = {
    GeminiDataAnalyticsClient: (
        "chat_client",
        "agent_client",
        "_transport_for_location",
    ),
    GenAIClient: ("client",),
}


def _outward_methods(client: type) -> list[tuple[str, object]]:
  """Public methods whose body names one of the client's transports."""
  transports = _TRANSPORTS[client]
  found = []
  for name, member in inspect.getmembers(client, inspect.isfunction):
    if name.startswith("_"):
      continue
    source = inspect.getsource(member)
    if any(transport in source for transport in transports):
      found.append((name, member))
  return found


@pytest.mark.parametrize("client", list(_TRANSPORTS))
def test_every_outward_method_is_routed_through_a_cassette(client):
  """A method without @cassette cannot be replayed, and crashes instead.

  Both constructors leave their transport None in replay mode, so an
  undecorated method dies on None rather than missing a cassette. The browser
  suite is what finds that otherwise, and only if a spec happens to call the
  method. get_datasource_kind shipped without a decorator and nothing said so
  until a run start failed with "'NoneType' object has no attribute
  'get_data_agent'".
  """
  methods = _outward_methods(client)
  # Guards the filter above. If the transport names are ever changed this
  # matches nothing and the assertion below passes on an empty list.
  assert methods, f"no outward methods found on {client.__name__}"

  missing = [
      name
      for name, member in methods
      if not hasattr(member, "cassette_signature")
  ]

  assert not missing, (
      f"{client.__name__} methods reach the service with no cassette:"
      f" {missing}. Add @recording.cassette() with a codec that matches the"
      " return type."
  )
