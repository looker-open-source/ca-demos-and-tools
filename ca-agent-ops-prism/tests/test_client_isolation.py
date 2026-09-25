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

"""Architecture boundary: prism.client must not import prism.ui."""

from tests.conftest import layering_violations


def test_the_client_does_not_import_the_ui():
  """The client sits under the UI, so it cannot reach back up into it.

  Only the prism.ui ban is enforced. prism.server and prism.common are both
  allowed: the client is what the UI calls the server through.
  """
  violations = layering_violations("prism.client", ["prism.ui"])

  assert not violations, (
      "Architecture violation: prism.client must not import prism.ui.\n"
      + "\n".join(violations)
  )
