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

"""Architecture boundary: prism.ui must not import prism.server."""

from tests.conftest import layering_violations


def test_the_ui_does_not_import_the_server():
  """The UI reaches the server through prism.client, and nothing else.

  Only the prism.server ban is enforced. prism.client and prism.common are
  both allowed, and prism.client is trusted not to re-export server internals:
  src/prism/client/dependencies.py imports the whole server tree, so ``from
  prism.client import dependencies`` is one permitted import statement that
  hands the UI everything this rule exists to keep out. See
  layering_violations for the rest of what the check cannot see.
  """
  violations = layering_violations("prism.ui", ["prism.server"])

  assert not violations, (
      "Architecture violation: prism.ui must not import prism.server. The UI"
      " depends on prism.client and prism.common.schemas only.\n"
      + "\n".join(violations)
  )
