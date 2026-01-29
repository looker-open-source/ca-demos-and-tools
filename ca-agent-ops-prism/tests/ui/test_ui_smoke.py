"""Smoke test for the Prism UI.

This test ensures that the Dash application and all its components (pages,
callbacks) can be imported without syntax or import errors.
"""

from prism.ui.app import app
# Import a representative set of pages and callbacks to ensure syntax check
# Most callbacks are already imported in prism.ui.app

# pylint: disable=unused-import
from prism.ui.pages import agent_add
from prism.ui.pages import agent_detail
from prism.ui.pages import agent_home
from prism.ui.pages import agent_monitor
from prism.ui.pages import agent_trace
from prism.ui import ids
from prism.ui.pages import test_suite_home
from prism.ui.pages import test_suite_new
from prism.ui.pages import test_suite_questions
from prism.ui.pages import test_suite_view
from prism.ui.pages import evaluation_detail
from prism.ui.pages import evaluations
from prism.ui.pages import home
from prism.ui.pages import run_comparison
from prism.ui.pages import trial_detail
# pylint: enable=unused-import


def test_ui_imports():
  """Verifies that the main app and key pages can be imported."""
  assert app is not None
  assert home.layout is not None
  assert evaluations.layout is not None
  assert test_suite_questions.layout is not None


def test_app_configured():
  """Verifies basic Dash app configuration."""
  assert app.config.title == "Prism"
  assert app.config.suppress_callback_exceptions is True
