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

"""UI callbacks package."""

# Imported for the side effect: a module registers its callbacks with Dash at
# import time, so the import is the registration. Nothing below is referenced
# by name. alembic/env.py imports prism.server.models the same way.
# pylint: disable=unused-import

from prism.ui.callbacks import agent_add_callbacks  # noqa: F401
from prism.ui.callbacks import agent_callbacks  # noqa: F401
from prism.ui.callbacks import agent_detail_callbacks  # noqa: F401
from prism.ui.callbacks import agent_monitor_callbacks  # noqa: F401
from prism.ui.callbacks import agent_trace_callbacks  # noqa: F401
from prism.ui.callbacks import evaluation_callbacks  # noqa: F401
from prism.ui.callbacks import home_callbacks  # noqa: F401
from prism.ui.callbacks import run_comparison_callbacks  # noqa: F401
from prism.ui.callbacks import shell_callbacks  # noqa: F401
from prism.ui.callbacks import test_suite_callbacks  # noqa: F401
from prism.ui.callbacks import test_suite_questions_callbacks  # noqa: F401


def register_all_callbacks():
  """Does nothing. Importing this package is what registers the callbacks.

  It exists so app.py has a call to make, which keeps the imports above from
  reading as unused.
  """
