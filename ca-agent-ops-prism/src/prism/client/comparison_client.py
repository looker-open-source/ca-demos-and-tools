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

"""Client for comparing evaluation runs."""

from fast_depends import Depends
from fast_depends import inject
from prism.client import dependencies
from prism.common.schemas import comparison as comparison_schemas
from prism.server.services.comparison_service import ComparisonService


class ComparisonClient:
  """Comparison Client implementation."""

  @inject
  def compare_runs(
      self,
      base_run_id: int,
      challenger_run_id: int,
      service: ComparisonService = Depends(dependencies.get_comparison_service),
  ) -> comparison_schemas.RunComparison:
    """Compares two runs and generates a comparison report."""
    return service.compare_runs(base_run_id, challenger_run_id)
