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

from prism.ui.callbacks import agent_add_callbacks
from prism.ui.callbacks import agent_callbacks
from prism.ui.callbacks import agent_context_test_callbacks
from prism.ui.callbacks import agent_detail_callbacks
from prism.ui.callbacks import agent_monitor_callbacks
from prism.ui.callbacks import agent_trace_callbacks
from prism.ui.callbacks import dataset_callbacks
from prism.ui.callbacks import dataset_questions_callbacks
from prism.ui.callbacks import evaluation_callbacks
from prism.ui.callbacks import home_callbacks
from prism.ui.callbacks import run_comparison_callbacks
from prism.ui.callbacks import shell_callbacks


def register_all_callbacks():
  """No-op to register all callbacks.

  Callbacks are already registered by above imports.
  """
