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

"""Dashboard Client implementation."""

from fast_depends import Depends
from fast_depends import inject
from prism.client import dependencies
from prism.common.schemas import dashboard as dashboard_schemas
from prism.server.services.dashboard_service import DashboardService


class DashboardClient:
  """Dashboard Client implementation."""

  @inject
  def get_dashboard_stats(
      self,
      service: DashboardService = Depends(dependencies.get_dashboard_service),
  ) -> dashboard_schemas.DashboardStats:
    """Calculates and returns dashboard statistics."""
    return service.get_dashboard_stats()
