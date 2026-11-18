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

"""Every page layout has to accept the query string it is loaded with.

Dash pages calls ``layout(**path_variables, **query_parameters)``, so loading
``/test_suites?archived=true`` passes ``archived="true"`` to the layout. A
layout without ``**kwargs`` raised TypeError there, and the page came up blank
behind a 500.
"""

from __future__ import annotations

import re

import dash

# Importing the app registers every page.
from prism.ui.app import app  # pylint: disable=unused-import
import pytest

_PAGES = sorted(
    dash.page_registry.values(),
    key=lambda page: page.get("path_template") or page["path"],
)


@pytest.mark.parametrize(
    "page", _PAGES, ids=[p.get("path_template") or p["path"] for p in _PAGES]
)
def test_layout_accepts_query_parameters(page, session_factory):
  # Some layouts read the database, so the schema has to exist.
  del session_factory
  path_variables = {
      name: "1"
      for name in re.findall(r"<(\w+)>", page.get("path_template") or "")
  }

  page["layout"](**path_variables, archived="true", utm="1")
