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

"""IDs for Run Comparison Page."""


class ComparisonIds:
  """IDs for Run Comparison Page."""

  # URL Params
  URL = "url"
  URL_BASE_RUN_ID = "base_run_id"
  URL_CHALLENGER_RUN_ID = "challenger_run_id"
  URL_DATASET_ID = "dataset_id"
  URL_FILTER = "filter"
  URL_SEARCH = "search"
  URL_SHOW_DIFFS = "show_diffs"

  # Modal
  SELECT_RUNS_MODAL = "comp-select-runs-modal"
  BTN_OPEN_SELECT_RUNS = "comp-btn-open-select-runs"
  BTN_CLOSE_SELECT_RUNS = "comp-btn-close-select-runs"
  BTN_APPLY_SELECT_RUNS = "comp-btn-apply-select-runs"

  # Page Components
  PAGE_CONTAINER = "run-comparison-container"

  # Selectors
  DATASET_SELECT = "comp-dataset-select"
  BASE_RUN_SELECT = "comp-base-run-select"
  CHALLENGE_RUN_SELECT = "comp-challenge-run-select"
  BTN_SWAP_RUNS = "comp-btn-swap-runs"

  # Filters
  FILTER_ALL = "comp-filter-all"
  FILTER_REGRESSIONS = "comp-filter-regressions"
  FILTER_IMPROVEMENTS = "comp-filter-improvements"
  FILTER_ERRORS = "comp-filter-errors"
  FILTER_REMOVED = "comp-filter-removed"
  FILTER_ADDED = "comp-filter-added"
  FILTER_UNCHANGED = "comp-filter-unchanged"

  # Content
  COMPARISON_LIST = "comp-comparison-list"
  SUMMARY_SECTION = "comp-summary-section"
  METRICS_CARDS = "comp-metrics-cards"
  PERFORMANCE_DELTA_CHART = "comp-performance-delta-chart"
  ASSERTION_DELTA_CHART = "comp-assertion-delta-chart"
  SUBTITLE_TEXT = "comp-subtitle-text"
  FILTER_BAR = "comp-filter-bar"

  # Empty State
  EMPTY_STATE = "comp-empty-state"
  BTN_EMPTY_SELECT_RUNS = "comp-btn-empty-select-runs"

  # Local URL
  LOC_URL = "comp-loc-url"

  # Nav Containers
  BASE_RUN_NAV = "comp-base-run-nav"
  CHALLENGE_RUN_NAV = "comp-challenge-run-nav"

  # Agent Context Comparison
  CONTEXT_DIFF_ACCORDION = "comp-context-diff-accordion"
  CONTEXT_DIFF_CONTENT = "comp-context-diff-content"
  CONTEXT_DIFF_BADGE = "comp-context-diff-badge"

  class TrialDiagnostic:
    ACCORDION = "trial-diagnostic-accordion"
