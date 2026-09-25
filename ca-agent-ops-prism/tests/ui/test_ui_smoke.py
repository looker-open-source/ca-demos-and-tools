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

"""Smoke test for the Prism UI.

Importing the app pulls in every page and callback, so a syntax or import
error anywhere in the UI fails here.
"""

import inspect

import dash
from prism.ui import pages
from prism.ui.app import app


def test_every_page_module_is_registered():
  """A page module left out of register_all_pages gets no coverage at all.

  Registration is a hand-written list, not a scan of the package, so a new
  page can be imported by prism.ui.pages and never reach dash.page_registry.
  Nothing downstream notices. test_callback_dispatch.py and the page-layout
  contract in test_callback_contracts.py both parametrize over the registry,
  so the missing page drops out of those runs and they stay green.
  """
  registered = {page["module"] for page in dash.page_registry.values()}
  # A module carrying register_page is a page. The *_ids modules beside them
  # are not.
  declared = {
      module.__name__
      for module in vars(pages).values()
      if inspect.ismodule(module) and hasattr(module, "register_page")
  }

  assert declared, "prism.ui.pages exposed no page modules"
  assert declared - registered == set(), (
      "page modules that never call register_page(): "
      f"{sorted(declared - registered)}"
  )


def test_app_configured():
  """suppress_callback_exceptions is what test_callback_contracts.py covers for.

  With it on, Dash prunes callbacks whose components are missing instead of
  raising, so the contract tests are the only thing that notices.

  The title is checked here too. Every page overrides it with "Prism | X", so
  the app-level one only shows before a page resolves, and nothing else would
  catch it changing.
  """
  assert app.config.title == "Prism"
  assert app.config.suppress_callback_exceptions is True
