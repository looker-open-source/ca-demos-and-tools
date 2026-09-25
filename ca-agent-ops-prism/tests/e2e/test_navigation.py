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

"""Every registered route loads in a browser without a console error.

Dash runs with ``suppress_callback_exceptions=True``, so a page whose layout
raises still serves HTML and only the browser sees the failure. Walking every
route with the console-error gate turned on is what makes that visible.
"""

import dash
from playwright.sync_api import expect
from playwright.sync_api import Page

# Imported for the side effect. Importing the app populates dash.page_registry,
# which the parametrization below is built from.
from prism.ui import app as prism_app  # pylint: disable=unused-import
import pytest

pytestmark = pytest.mark.e2e


def _static_routes() -> list[str]:
  """Registered routes that need no path parameters."""
  routes = []
  for page in dash.page_registry.values():
    if page.get("path_template"):
      continue
    path = page.get("path")
    if path:
      routes.append(path)
  return sorted(set(routes))


ROUTES = _static_routes()


def test_routes_were_discovered():
  """Guards the parametrization. An empty registry would vacuously pass."""
  assert len(ROUTES) >= 5, ROUTES


@pytest.mark.parametrize("route", ROUTES)
def test_route_loads(page: Page, base_url: str, route: str):
  """Each route renders and reaches an idle network with no browser error."""
  response = page.goto(f"{base_url}{route}")

  assert response is not None, route
  assert response.status < 400, f"{route} -> HTTP {response.status}"

  page.wait_for_load_state("networkidle")
  expect(page.locator("#react-entry-point")).not_to_be_empty()


def test_unknown_route_shows_the_404_page(page: Page, base_url: str):
  """An unrouted URL is a normal page, not a stack trace.

  Dash serves its own ``404 - Page not found`` heading because no page module
  is named ``not_found_404``. Asserting the heading rather than a non-empty
  root, which a redirect, a spinner or a traceback all satisfy too.
  """
  page.goto(f"{base_url}/definitely-not-a-page")
  page.wait_for_load_state("networkidle")

  expect(
      page.get_by_role("heading", name="404 - Page not found")
  ).to_be_visible()
  # The shell stays up, so there is a way back out.
  expect(page.locator("#react-entry-point")).not_to_be_empty()
