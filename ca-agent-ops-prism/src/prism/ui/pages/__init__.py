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

"""UI pages package."""

from prism.ui.pages import agent_add
from prism.ui.pages import agent_detail
from prism.ui.pages import agent_home
from prism.ui.pages import agent_monitor
from prism.ui.pages import agent_trace
from prism.ui.pages import context_prototype
from prism.ui.pages import dataset_home
from prism.ui.pages import dataset_new
from prism.ui.pages import dataset_questions
from prism.ui.pages import dataset_view
from prism.ui.pages import evaluation_detail
from prism.ui.pages import evaluations
from prism.ui.pages import execution_detail
from prism.ui.pages import home
from prism.ui.pages import run_comparison
from prism.ui.pages import trial_detail


def register_all_pages():
  """Explicitly register all Dash pages."""
  agent_add.register_page()
  agent_detail.register_page()
  agent_home.register_page()
  agent_monitor.register_page()
  agent_trace.register_page()
  context_prototype.register_page()
  dataset_home.register_page()
  dataset_new.register_page()
  dataset_questions.register_page()
  dataset_view.register_page()
  evaluation_detail.register_page()
  evaluations.register_page()
  execution_detail.register_page()
  home.register_page()
  run_comparison.register_page()
  trial_detail.register_page()
