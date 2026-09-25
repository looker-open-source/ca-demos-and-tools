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

"""Architecture boundary: prism.common must stay a leaf."""

from tests.conftest import layering_violations


def test_the_common_package_does_not_import_the_other_layers():
  """Everything depends on prism.common, so it may depend on none of them.

  One import from here into prism.server, prism.ui or prism.client makes the
  schemas unusable from the layer they point at, and the cycle only shows up
  as an ImportError in whichever process imports them in the wrong order.
  """
  violations = layering_violations(
      "prism.common", ["prism.server", "prism.ui", "prism.client"]
  )

  assert not violations, (
      "Architecture violation: prism.common must not import any other prism"
      " package.\n"
      + "\n".join(violations)
  )
