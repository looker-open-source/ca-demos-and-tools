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

"""Definitions of UI component IDs for the Prism application."""

from typing import Any


class EvaluationIds:
  """IDs for Evaluation pages."""

  # List Page
  RUN_LIST_CONTAINER = "evaluations-run-list-container"
  FILTER_AGENT = "evaluations-filter-agent"
  FILTER_SUITE = "evaluations-filter-suite"
  FILTER_STATUS = "evaluations-filter-status"

  # Detail Page
  RUN_DETAIL_CONTAINER = "evaluations-run-detail-container"
  RUN_DETAIL_STATS = "evaluations-run-detail-stats"
  RUN_CONTEXT_BANNER = "evaluations-run-context-banner"
  RUN_CONTEXT_INSTRUCTION = "evaluations-run-context-instruction"
  RUN_CONTEXT_TRIGGER = "evaluations-run-context-trigger"
  RUN_CONTEXT_DIFF_BTN = "run-context-diff-btn"
  RUN_CONTEXT_DIFF_MODAL = "run-context-diff-modal"
  RUN_CONTEXT_DIFF_STORE = "run-context-diff-store"
  RUN_CONTEXT_DIFF_CONTENT = "run-context-diff-content"
  RUN_CONTEXT_DIFF_TITLE = "run-context-diff-title"
  BTN_DOWNLOAD_DIFF = "btn-download-diff"
  DOWNLOAD_DIFF_COMPONENT = "download-diff-component"
  RUN_BREADCRUMBS_CONTAINER = "evaluations-run-breadcrumbs"
  RUN_POLLING_INTERVAL = "run-polling-interval"
  BTN_PAUSE_RUN = "btn-pause-run"
  BTN_RESUME_RUN = "btn-resume-run"
  BTN_CANCEL_RUN_EXEC = "btn-cancel-run-exec"
  RUN_STATUS_BADGE = "run-status-badge"
  RUN_UPDATE_SIGNAL = "run-update-signal"
  RUN_CHARTS_CONTAINER = "evaluations-run-charts-container"
  RUN_TRIALS_CONTAINER = "evaluations-run-trials-container"
  RUN_DATA_STORE = "evaluations-run-data-store"
  EXECUTION_DETAIL_CONTAINER = "evaluations-execution-detail-container"
  EXECUTION_BREADCRUMBS_CONTAINER = "evaluations-execution-breadcrumbs"

  # Trial Page
  TRIAL_TITLE = "evaluations-trial-title"
  TRIAL_DESCRIPTION = "evaluations-trial-description"
  TRIAL_ACTIONS = "evaluations-trial-actions"
  TRIAL_DETAIL_CONTAINER = "evaluations-trial-detail-container"
  TRIAL_BREADCRUMBS_CONTAINER = "evaluations-trial-breadcrumbs"
  AGENT_TRACE_TITLE = "evaluations-trace-title"
  AGENT_TRACE_STATUS = "evaluations-trace-status"
  AGENT_TRACE_ACTIONS = "evaluations-trace-actions"
  AGENT_TRACE_CONTAINER = "evaluations-agent-trace-container"
  AGENT_TRACE_BREADCRUMBS_CONTAINER = "evaluations-trace-breadcrumbs"
  AGENT_TRACE_COPY_BTN = "agent-trace-copy-btn"
  AGENT_TRACE_VIEW_RAW_BTN = "agent-trace-view-raw-btn"
  AGENT_TRACE_RAW_MODAL = "agent-trace-raw-modal"
  AGENT_TRACE_RAW_STORE = "agent-trace-raw-store"
  AGENT_TRACE_DOWNLOAD_BTN = "agent-trace-download-btn"
  AGENT_TRACE_DOWNLOAD_COMPONENT = "agent-trace-download-component"
  ASSERT_FILTER_CATEGORY = "assert-filter-category"
  ASSERT_FILTER_STATUS = "assert-filter-status"
  ASSERT_FILTER_TYPE = "assert-filter-type"

  # URL
  URL = "url"  # Shared configured in app.py

  # Test Suite View - Run Modal
  MODAL_RUN_EVAL = "modal-run-eval"
  MODAL_RUN_EVAL_INNER = "modal-run-eval-inner"
  AGENT_SELECT = "eval-agent-select"
  AGENT_DETAILS = "eval-agent-details"
  BTN_START_RUN = "btn-start-eval-run"
  BTN_CANCEL_RUN = "btn-cancel-eval-run"
  BTN_OPEN_RUN_MODAL = "btn-open-run-modal"

  # Global Run Modal (Evaluations Page)
  BTN_NEW_EVAL = "btn-new-eval"
  MODAL_NEW_EVAL = "modal-new-eval"
  NEW_EVAL_SUITE_SELECT = "new-eval-suite-select"
  NEW_EVAL_AGENT_SELECT = "new-eval-agent-select"
  BTN_START_NEW_EVAL = "btn-start-new-eval"
  BTN_CANCEL_NEW_EVAL = "btn-cancel-new-eval"

  # Comparison Modal (Runs List)
  BTN_OPEN_COMPARE_MODAL = "btn-open-compare-modal"
  MODAL_COMPARE_RUNS = "modal-compare-runs"
  COMPARE_BASE_SELECT = "compare-base-select"
  COMPARE_CHALLENGE_SELECT = "compare-challenge-select"
  BTN_GO_COMPARE = "btn-go-compare"
  BTN_SWAP_COMPARE_MODAL = "btn-swap-compare-modal"
  BTN_CANCEL_COMPARE = "btn-cancel-compare"
  # Suggestions
  INLINE_SUG_ADD_BTN = "btn-accept-suggestion"
  INLINE_SUG_REJECT_BTN = "btn-reject-suggestion"
  ASSERT_EDIT_BTN = "btn-edit-suggestion"

  # Trial Suggestion Edit Modal
  TRIAL_SUG_EDIT_MODAL = "trial-sug-edit-modal"
  TRIAL_SUG_EDIT_SAVE_BTN = "trial-sug-edit-save-btn"
  TRIAL_SUG_EDIT_TYPE = "trial-sug-edit-type"
  TRIAL_SUG_EDIT_WEIGHT = "trial-sug-edit-weight"
  TRIAL_SUG_EDIT_VALUE = "trial-sug-edit-value"
  TRIAL_SUG_EDIT_YAML = "trial-sug-edit-yaml"
  TRIAL_SUG_EDIT_CHART_TYPE = "trial-sug-edit-assert-chart-type"
  TRIAL_SUG_EDIT_EXAMPLE_CONTAINER = "trial-sug-edit-example-container"
  TRIAL_SUG_EDIT_EXAMPLE_VALUE = "trial-sug-edit-example-value"
  TRIAL_SUG_EDIT_EXAMPLE_YAML = "trial-sug-edit-example-yaml"
  TRIAL_SUG_EDIT_CONTEXT = "trial-sug-edit-context"
  TRIAL_SUG_UPDATE_SIGNAL = "trial-sug-update-signal"
  TRIAL_SUG_LOADING_STORE = "trial-sug-loading-store"
  TRIAL_SUG_EDIT_GUIDE_CONTAINER = "trial-sug-edit-guide-container"
  TRIAL_SUG_EDIT_GUIDE_TITLE = "trial-sug-edit-guide-title"
  TRIAL_SUG_EDIT_GUIDE_DESC = "trial-sug-edit-guide-desc"
  TRIAL_SUGGESTIONS_CONTENT = "trial-suggestions-content"
  TRIAL_SUG_VAL_MSG = "trial-sug-val-msg"
  TRIAL_SUG_POLLING_INTERVAL = "trial-sug-polling-interval"
  TRIAL_ASSERT_LIST = "trial-assert-list"
  SUGGEST_BTN_TYPE = "suggest-suggestions-btn"
  TRIAL_SUG_ACCORDION = "trial-suggestions-accordion"

  # Execution Page
  EXECUTION_SUG_EDIT_MODAL = "execution-sug-edit-modal"
  EXECUTION_SUG_EDIT_SAVE_BTN = "execution-sug-edit-save-btn"
  EXECUTION_SUG_EDIT_TYPE = "execution-sug-edit-type"
  EXECUTION_SUG_EDIT_WEIGHT = "execution-sug-edit-weight"
  EXECUTION_SUG_EDIT_VALUE = "execution-sug-edit-value"
  EXECUTION_SUG_EDIT_YAML = "execution-sug-edit-yaml"
  EXECUTION_SUG_EDIT_CHART_TYPE = "execution-sug-edit-assert-chart-type"
  EXECUTION_SUG_EDIT_EXAMPLE_CONTAINER = "execution-sug-edit-example-container"
  EXECUTION_SUG_EDIT_EXAMPLE_VALUE = "execution-sug-edit-example-value"
  EXECUTION_SUG_EDIT_EXAMPLE_YAML = "execution-sug-edit-example-yaml"
  EXECUTION_SUG_EDIT_CONTEXT = "execution-sug-edit-context"
  EXECUTION_SUG_UPDATE_SIGNAL = "execution-sug-update-signal"
  EXECUTION_SUG_LOADING_STORE = "execution-sug-loading-store"
  EXECUTION_SUG_EDIT_GUIDE_CONTAINER = "execution-sug-edit-guide-container"
  EXECUTION_SUG_EDIT_GUIDE_TITLE = "execution-sug-edit-guide-title"
  EXECUTION_SUG_EDIT_GUIDE_DESC = "execution-sug-edit-guide-desc"
  EXECUTION_SUG_VAL_MSG = "execution-sug-val-msg"


class ComparisonIds:
  """IDs for Run Comparison Page."""

  # URL Params
  URL = "url"
  URL_BASE_RUN_ID = "base_run_id"
  URL_CHALLENGER_RUN_ID = "challenger_run_id"
  URL_SUITE_ID = "suite_id"
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
  SUITE_SELECT = "comp-suite-select"
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


class TestSuiteIds:
  """Component IDs for the Test Suite workflow (New, View, Edit)."""

  # Suggestion Edit Modal
  SUG_EDIT_MODAL = "sug-edit-modal"
  SUG_EDIT_TYPE = "sug-edit-assert-type"
  SUG_EDIT_VALUE = "sug-edit-assert-value"
  SUG_EDIT_YAML = "sug-edit-assert-yaml"
  SUG_EDIT_CHART_TYPE = "sug-edit-assert-chart-type"
  SUG_EDIT_WEIGHT = "sug-edit-assert-weight"
  SUG_EDIT_GUIDE_CONTAINER = "sug-edit-guide-container"
  SUG_EDIT_GUIDE_TITLE = "sug-edit-guide-title"
  SUG_EDIT_GUIDE_DESC = "sug-edit-guide-desc"
  SUG_EDIT_EXAMPLE_CONTAINER = "sug-edit-assert-example-container"
  SUG_EDIT_EXAMPLE_VALUE = "sug-edit-assert-example-value"
  SUG_EDIT_EXAMPLE_YAML = "sug-edit-assert-example-yaml"
  SUG_EDIT_SAVE_BTN = "sug-edit-save-btn"
  SUGGESTION_EDIT_BTN = "suggestion-edit-btn"

  NAME = "test-suite-name"
  DESC = "test-suite-description"
  SAVE_NEW_BTN = "test-suite-save-new-btn"
  SAVE_EDIT_BTN = "test-suite-save-edit-btn"
  CANCEL_NEW_BTN = "test-suite-cancel-new-btn"
  CANCEL_EDIT_BTN = "test-suite-cancel-edit-btn"
  BUILDER_CONTAINER = "test-suite-builder-container"
  BULK_ADD_BTN = "test-suite-bulk-add-btn"
  PLACEHOLDER_SAVE_BTN = "test-suite-placeholder-save-btn"

  # Datasource IDs
  AGENT_SELECT = "test-suite-agent-select"

  # Builder IDs (Internal)
  ADD_TEST_CASE_BTN = "test-suite-add-test-case-btn"
  TEST_CASE_LIST = "test-suite-test-case-list"

  # Store IDs
  STORE_BUILDER = "suite-builder-state"
  STORE_MODAL = "modal-store"

  # Question Modal Internal IDs
  MODAL_TEST_CASE = "test-case-modal"
  MODAL_TEST_CASE_TEXT = "modal-test-case-text"
  MODAL_SAVE_BTN = "modal-save-btn"
  MODAL_CANCEL_BTN = "modal-cancel-btn"
  MODAL_ASSERT_LIST = "modal-assertions-list"
  MODAL_ASSERT_TYPE = "modal-new-assert-type"
  MODAL_ASSERT_VALUE = "modal-new-assert-value"
  MODAL_ASSERT_YAML = "modal-new-assert-yaml"
  MODAL_ACE_CONTAINER = "modal-ace-container"
  MODAL_ADD_ASSERT_BTN = "modal-add-assert-btn"

  # Bulk Add Modal Internal IDs
  MODAL_BULK = "bulk-add-modal"
  MODAL_BULK_TEXT = "bulk-add-text"
  MODAL_BULK_SAVE_BTN = "bulk-add-confirm-btn"
  MODAL_BULK_CANCEL_BTN = "bulk-add-cancel-btn"

  # Delete Confirm Modal
  MODAL_DELETE = "delete-confirm-modal"
  MODAL_DELETE_BODY = "delete-confirm-modal-body"
  MODAL_DELETE_CANCEL_BTN = "confirm-delete-cancel-btn"
  MODAL_CONFIRM_REMOVE_BTN = "confirm-delete-btn"

  # Bulk Add Modal
  TC_BULK_ADD_BTN = "tc-bulk-add-btn"
  MODAL_BULK_ADD = "bulk-add-modal"
  INPUT_BULK_TEXT = "bulk-add-text-input"
  PREVIEW_BULK_ADD = "bulk-add-preview"
  BTN_BULK_ADD_CONFIRM = "bulk-add-confirm-btn"
  BTN_BULK_ADD_CANCEL = "bulk-add-cancel-btn"

  # Edit Config Modal
  BTN_CONFIG_EDIT = "test-suite-config-edit-btn"
  MODAL_CONFIG_EDIT = "test-suite-config-edit-modal"

  # Distinct IDs for Modal Inputs to avoid collision with Page Inputs
  EDIT_NAME = "test-suite-edit-name"
  EDIT_DESC = "test-suite-edit-desc"

  MODAL_CONFIG_SAVE_BTN = "test-suite-config-save-btn"
  MODAL_CONFIG_CANCEL_BTN = "test-suite-config-cancel-btn"
  MODAL_CONFIG_CLOSE_BTN_X = "test-suite-config-close-btn-x"

  # Question Playground IDs
  TC_LIST = "tc-playground-list"
  TC_LIST_ITEM = "tc-playground-list-item"  # For pattern matching
  TC_ADD_BTN = "tc-playground-add-btn"
  TC_PLAYGROUND_ADD_BTN = "tc-playground-add-btn"  # Alias for updated usage

  # Editor Section
  TC_EDITOR_TITLE = "tc-editor-title"
  TC_EDITOR_CONTAINER = "tc-editor-container"
  TC_EDITOR_EMPTY = "tc-editor-empty"

  # Inputs
  TC_INPUT_TEST_CASE = "tc-input-test-case"
  TC_INPUT_TAGS = "tc-input-tags"
  # TC_INPUT_ASSERTS = "tc-input-asserts"  # Deprecated/Removed

  # Assertion Builder Inputs
  TC_ASSERT_LIST = "tc-assert-list"
  TC_ASSERT_TYPE = "tc-assert-type"
  TC_ASSERT_DESC = "tc-assert-desc"
  TC_ASSERT_VALUE = "tc-assert-value"
  TC_ASSERT_YAML = "tc-assert-yaml"
  TC_ASSERT_EXAMPLE_CONTAINER = "tc-assert-example-container"
  TC_ASSERT_EXAMPLE_VALUE = "tc-assert-example-value"
  TC_ASSERT_EXAMPLE_YAML = "tc-assert-example-yaml"
  TC_ASSERT_WEIGHT = "tc-assert-weight"
  TC_ASSERT_COUNT = "tc-assert-count"
  TC_ASSERT_WEIGHT_TOGGLE = "tc-assert-weight-toggle"  # Pattern ID
  TC_ASSERT_ADD_BTN = "tc-assert-add-btn"

  # Actions
  TC_SAVE_BTN = "tc-save-btn"
  TC_REVERT_BTN = "tc-revert-btn"
  TC_CHANGE_ACTIONS_GROUP = "tc-change-actions-group"
  TC_REMOVE_ASSERTION_BTN = "tc-remove-assertion-btn"
  TC_REMOVE_TEST_CASE_BTN = "tc-remove-test-case-btn"
  STORE_DELETE_TEST_CASE_INDEX = "store-delete-test-case-index"

  # Assertion Modal
  ASSERT_MODAL = "assert-modal"
  ASSERT_MODAL_OPEN_BTN = "assert-modal-open-btn"
  ASSERT_MODAL_DELETE_BTN = "assert-modal-delete-btn"
  ASSERT_MODAL_CONFIRM_BTN = "assert-modal-confirm-btn"
  ASSERT_MODAL_TITLE_TEXT = "assert-modal-title-text"
  ASSERT_EDIT_BTN = "assert-edit-btn"
  STORE_ASSERT_EDIT_INDEX = "store-assert-edit-index"
  STORE_DELETE_ASSERTION_INDEX = "store-delete-assertion-index"
  ASSERT_TOGGLE_ACCURACY = "assert-toggle-accuracy"
  ASSERT_GUIDE_CONTAINER = "assert-guide-container"
  ASSERT_GUIDE_TITLE = "assert-guide-title"
  ASSERT_GUIDE_DESC = "assert-guide-desc"
  ASSERT_EXAMPLE_CONTAINER = "assert-example-container"
  ASSERT_EXAMPLE_VALUE = "assert-example-value"
  ASSERT_EXAMPLE_YAML = "assert-example-yaml"
  ASSERT_CHART_TYPE = "assert-chart-type"

  # Execution / Playground
  TC_AGENT_SELECT = "tc-playground-agent-select"
  TC_RUN_BTN = "tc-run-btn"
  TC_SPINNER = "tc-spinner"
  TC_RESULT_CONTAINER = "tc-result-container"

  # Suggestion
  TC_SUGGEST_BTN = "tc-suggest-asserts-btn"
  TC_HISTORY_SUGGESTIONS_BTN = "tc-history-suggestions-btn"
  TC_SUGGEST_LOADING = "tc-suggest-loading"
  SUGGESTION_MODAL = "suggestion-modal"
  SUGGESTION_LIST = "suggestion-list"
  SUGGESTION_ADD_BTN = "suggestion-add-btn"
  VAL_MSG = "val-msg"
  INLINE_SUG_ADD_BTN = "inline-sug-add-btn"
  INLINE_SUG_REJECT_BTN = "inline-sug-reject-btn"
  ASSERT_VAL_MSG = "assert-validation-msg"

  # Simulation Redesign IDs
  SIM_CONTEXT_CONTAINER = "sim-context-container"
  SUG_ACCORDION = "sug-accordion"
  SUG_ACCORDION_HEADER = "sug-accordion-header"
  SUG_LIST = "sug-list"
  SUG_LIST_SKELETON = "sug-list-skeleton"

  # Stores
  STORE_PLAYGROUND_RESULT = "store-playground-result"
  STORE_SUGGESTIONS = "store-suggestions"
  STORE_SUG_EDIT_CONTEXT = "store-sug-edit-context"
  STORE_START_RUN = "store-start-run"
  STORE_SELECTED_INDEX = "selected-test-case-index"
  TC_BREADCRUMB_ID = "tc-breadcrumb-id"
  TC_BREADCRUMB_SUITE_NAME = "tc-breadcrumb-suite-name"


class TestSuiteHomeIds:
  """Component IDs for the Test Suites Home page."""

  TEST_SUITES_LIST = "test-suites-grid"
  CREATE_BTN = "create-test-suite-btn"
  LOADING = "test-suites-loading-overlay"
  FILTER_COVERAGE = "test-suites-filter-coverage"
