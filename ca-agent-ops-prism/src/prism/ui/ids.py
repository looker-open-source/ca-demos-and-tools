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


class EvaluationIds:
  """IDs for Evaluation pages."""

  # List Page
  RUN_LIST_CONTAINER = "evaluations-run-list-container"
  FILTER_AGENT = "evaluations-filter-agent"
  FILTER_SUITE = "evaluations-filter-suite"
  FILTER_STATUS = "evaluations-filter-status"

  # Detail Page
  RUN_DETAIL_STATS = "evaluations-run-detail-stats"
  RUN_CONTEXT_TRIGGER = "evaluations-run-context-trigger"
  RUN_CONTEXT_DIFF_BTN = "run-context-diff-btn"
  RUN_CONTEXT_DIFF_MODAL = "run-context-diff-modal"
  RUN_CONTEXT_DIFF_STORE = "run-context-diff-store"
  RUN_CONTEXT_DIFF_CONTENT = "run-context-diff-content"
  RUN_CONTEXT_DIFF_TITLE = "run-context-diff-title"
  RUN_CONTEXT_DIFF_BADGE = "run-context-diff-badge"
  BTN_DOWNLOAD_DIFF = "btn-download-diff"
  DOWNLOAD_DIFF_COMPONENT = "download-diff-component"
  RUN_BREADCRUMBS_CONTAINER = "evaluations-run-breadcrumbs"
  RUN_POLLING_INTERVAL = "run-polling-interval"
  BTN_PAUSE_RUN = "btn-pause-run"
  BTN_RESUME_RUN = "btn-resume-run"
  BTN_CANCEL_RUN_EXEC = "btn-cancel-run-exec"
  BTN_SYNC_BIGQUERY = "btn-sync-bigquery"
  RUN_STATUS_BADGE = "run-status-badge"
  RUN_BIGQUERY_BADGE = "run-bigquery-badge"
  RUN_UPDATE_SIGNAL = "run-update-signal"
  RUN_CHARTS_CONTAINER = "evaluations-run-charts-container"
  RUN_TRIALS_CONTAINER = "evaluations-run-trials-container"
  RUN_DATA_STORE = "evaluations-run-data-store"

  # Trial Page
  TRIAL_TITLE = "evaluations-trial-title"
  TRIAL_DESCRIPTION = "evaluations-trial-description"
  TRIAL_ACTIONS = "evaluations-trial-actions"
  TRIAL_DETAIL_CONTAINER = "evaluations-trial-detail-container"
  # The row of Accuracy, TTFR and Duration cards. "Accuracy" also heads a card
  # in the assertion summary further down the same page, so the row needs a
  # handle of its own for anything picking one of these three out.
  TRIAL_DETAIL_STATS = "evaluations-trial-detail-stats"
  TRIAL_BREADCRUMBS_CONTAINER = "evaluations-trial-breadcrumbs"
  AGENT_TRACE_TITLE = "evaluations-trace-title"
  AGENT_TRACE_STATUS = "evaluations-trace-status"
  AGENT_TRACE_ACTIONS = "evaluations-trace-actions"
  AGENT_TRACE_CONTAINER = "evaluations-agent-trace-container"
  AGENT_TRACE_BREADCRUMBS_CONTAINER = "evaluations-trace-breadcrumbs"
  AGENT_TRACE_VIEW_RAW_BTN = "agent-trace-view-raw-btn"
  AGENT_TRACE_RAW_MODAL = "agent-trace-raw-modal"
  AGENT_TRACE_RAW_STORE = "agent-trace-raw-store"
  AGENT_TRACE_DOWNLOAD_BTN = "agent-trace-download-btn"
  AGENT_TRACE_DOWNLOAD_COMPONENT = "agent-trace-download-component"
  ASSERT_FILTER_CATEGORY = "assert-filter-category"
  ASSERT_FILTER_STATUS = "assert-filter-status"
  ASSERT_FILTER_TYPE = "assert-filter-type"

  # Test Suite View: Run Modal
  MODAL_RUN_EVAL = "modal-run-eval"
  AGENT_SELECT = "eval-agent-select"
  AGENT_DETAILS = "eval-agent-details"
  BTN_START_RUN = "btn-start-eval-run"
  BTN_CANCEL_RUN = "btn-cancel-eval-run"
  BTN_OPEN_RUN_MODAL = "btn-open-run-modal"
  TOGGLE_SUGGESTIONS = "eval-run-toggle-suggestions"
  INPUT_CONCURRENCY = "eval-run-input-concurrency"

  # Global Run Modal (Evaluations Page)
  BTN_NEW_EVAL = "btn-new-eval"
  MODAL_NEW_EVAL = "modal-new-eval"
  NEW_EVAL_SUITE_SELECT = "new-eval-suite-select"
  NEW_EVAL_AGENT_SELECT = "new-eval-agent-select"
  BTN_START_NEW_EVAL = "btn-start-new-eval"
  BTN_CANCEL_NEW_EVAL = "btn-cancel-new-eval"
  NEW_EVAL_INPUT_CONCURRENCY = "new-eval-input-concurrency"

  # Comparison Modal (Runs List)
  BTN_OPEN_COMPARE_MODAL = "btn-open-compare-modal"
  MODAL_COMPARE_RUNS = "modal-compare-runs"
  COMPARE_BASE_SELECT = "compare-base-select"
  COMPARE_CHALLENGE_SELECT = "compare-challenge-select"
  BTN_GO_COMPARE = "btn-go-compare"
  BTN_SWAP_COMPARE_MODAL = "btn-swap-compare-modal"
  BTN_CANCEL_COMPARE = "btn-cancel-compare"

  # The same two attribute names as TestSuiteIds, because both classes are
  # passed to render_suggested_assertion_card as ids_class. The strings have to
  # stay different: the two pattern-matching callbacks behind them are
  # registered app-wide, so a shared type would fire both.
  INLINE_SUG_ADD_BTN = "trial-inline-sug-add-btn"
  INLINE_SUG_REJECT_BTN = "trial-inline-sug-reject-btn"

  TRIAL_SUG_UPDATE_SIGNAL = "trial-sug-update-signal"
  TRIAL_SUG_LOADING_STORE = "trial-sug-loading-store"

  BTN_ARCHIVE = "evaluations-run-detail-btn-archive"
  BTN_RESTORE = "evaluations-run-detail-btn-restore"
  SWITCH_ARCHIVED = "evaluations-run-list-switch-archived"
  TRIAL_SUGGESTIONS_CONTENT = "trial-suggestions-content"
  TRIAL_SUG_POLLING_INTERVAL = "trial-sug-polling-interval"
  SUGGEST_BTN_TYPE = "suggest-suggestions-btn"
  TRIAL_SUG_ACCORDION = "trial-suggestions-accordion"


class ComparisonIds:
  """IDs for Run Comparison Page."""

  # Query string keys, not component ids.
  URL_BASE_RUN_ID = "base_run_id"
  URL_CHALLENGER_RUN_ID = "challenger_run_id"
  URL_SUITE_ID = "suite_id"
  URL_FILTER = "filter"

  SELECT_RUNS_MODAL = "comp-select-runs-modal"
  BTN_OPEN_SELECT_RUNS = "comp-btn-open-select-runs"
  BTN_CLOSE_SELECT_RUNS = "comp-btn-close-select-runs"
  BTN_APPLY_SELECT_RUNS = "comp-btn-apply-select-runs"

  SUITE_SELECT = "comp-suite-select"
  BASE_RUN_SELECT = "comp-base-run-select"
  CHALLENGE_RUN_SELECT = "comp-challenge-run-select"
  BTN_SWAP_RUNS = "comp-btn-swap-runs"

  FILTER_ALL = "comp-filter-all"
  FILTER_REGRESSIONS = "comp-filter-regressions"
  FILTER_IMPROVEMENTS = "comp-filter-improvements"
  FILTER_UNCHANGED = "comp-filter-unchanged"
  # Everything the three named buckets leave out: an errored pair, a case only
  # one of the runs has, a case that never ran.
  FILTER_OTHER = "comp-filter-other"

  COMPARISON_LIST = "comp-comparison-list"
  SUMMARY_SECTION = "comp-summary-section"
  METRICS_CARDS = "comp-metrics-cards"
  PERFORMANCE_DELTA_CHART = "comp-performance-delta-chart"
  ASSERTION_DELTA_CHART = "comp-assertion-delta-chart"
  SUBTITLE_TEXT = "comp-subtitle-text"
  FILTER_BAR = "comp-filter-bar"

  EMPTY_STATE = "comp-empty-state"
  BTN_EMPTY_SELECT_RUNS = "comp-btn-empty-select-runs"

  LOC_URL = "comp-loc-url"

  BASE_RUN_NAV = "comp-base-run-nav"
  CHALLENGE_RUN_NAV = "comp-challenge-run-nav"

  # The diff of the two runs' agent context.
  CONTEXT_DIFF_ACCORDION = "comp-context-diff-accordion"
  CONTEXT_DIFF_CONTENT = "comp-context-diff-content"
  CONTEXT_DIFF_BADGE = "comp-context-diff-badge"

  class TrialDiagnostic:
    """IDs for the per-trial assertion diagnostic panel on a comparison row."""

    ACCORDION = "trial-diagnostic-accordion"


class TestSuiteIds:
  """Component IDs for the Test Suite workflow (New, View, Edit)."""

  NAME = "test-suite-name"
  DESC = "test-suite-description"
  SAVE_NEW_BTN = "test-suite-save-new-btn"
  CANCEL_NEW_BTN = "test-suite-cancel-new-btn"

  TEST_CASE_LIST = "test-suite-test-case-list"

  STORE_BUILDER = "suite-builder-state"

  MODAL_DELETE = "delete-confirm-modal"
  MODAL_DELETE_BODY = "delete-confirm-modal-body"
  MODAL_DELETE_CANCEL_BTN = "confirm-delete-cancel-btn"
  MODAL_CONFIRM_REMOVE_BTN = "confirm-delete-btn"

  TC_BULK_ADD_BTN = "tc-bulk-add-btn"
  MODAL_BULK_ADD = "bulk-add-modal"
  INPUT_BULK_TEXT = "bulk-add-text-input"
  PREVIEW_BULK_ADD = "bulk-add-preview"
  BTN_BULK_ADD_CONFIRM = "bulk-add-confirm-btn"
  BTN_BULK_ADD_CANCEL = "bulk-add-cancel-btn"
  BTN_BULK_FIX_AI = "bulk-fix-ai-btn"
  TC_BULK_MODE = "bulk-add-mode-toggle"
  BULK_ADD_INPUT_TITLE = "bulk-add-input-title"
  # The wrapper div, not the guide it holds. Simple mode hides it by style,
  # and the guide inside is rebuilt from scratch on every render.
  BULK_ADD_GUIDE_WRAPPER = "bulk-add-guide-wrapper"

  BTN_CONFIG_EDIT = "test-suite-config-edit-btn"
  MODAL_CONFIG_EDIT = "test-suite-config-edit-modal"

  # Distinct IDs for the modal buttons, to avoid collision with the page ones.
  MODAL_CONFIG_SAVE_BTN = "test-suite-config-save-btn"
  MODAL_CONFIG_CANCEL_BTN = "test-suite-config-cancel-btn"
  MODAL_CONFIG_CLOSE_BTN_X = "test-suite-config-close-btn-x"

  # The TC_ ids below are the questions page, where a test case is edited and
  # tried against an agent.
  TC_LIST = "tc-playground-list"
  TC_LIST_ITEM = "tc-playground-list-item"  # For pattern matching
  TC_PLAYGROUND_ADD_BTN = "tc-playground-add-btn"

  TC_EDITOR_CONTAINER = "tc-editor-container"
  TC_EDITOR_EMPTY = "tc-editor-empty"

  TC_INPUT_TEST_CASE = "tc-input-test-case"

  TC_ASSERT_LIST = "tc-assert-list"
  TC_ASSERT_TYPE = "tc-assert-type"
  TC_ASSERT_VALUE = "tc-assert-value"
  TC_ASSERT_YAML = "tc-assert-yaml"
  TC_ASSERT_MODE = "tc-assert-mode"
  TC_ASSERT_WEIGHT = "tc-assert-weight"
  TC_ASSERT_COUNT = "tc-assert-count"

  TC_SAVE_BTN = "tc-save-btn"
  TC_REVERT_BTN = "tc-revert-btn"
  TC_CHANGE_ACTIONS_GROUP = "tc-change-actions-group"
  TC_REMOVE_TEST_CASE_BTN = "tc-remove-test-case-btn"
  STORE_DELETE_TEST_CASE_INDEX = "store-delete-test-case-index"

  # Assertion Modal
  ASSERT_MODAL = "assert-modal"
  ASSERT_MODAL_OPEN_BTN = "assert-modal-open-btn"
  ASSERT_MODAL_DELETE_BTN = "assert-modal-delete-btn"
  ASSERT_MODAL_CONFIRM_BTN = "assert-modal-confirm-btn"
  ASSERT_MODAL_CANCEL_BTN_FOOTER = "modal-cancel-btn-footer"
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

  TC_AGENT_SELECT = "tc-playground-agent-select"
  TC_RUN_BTN = "tc-run-btn"
  TC_RESULT_CONTAINER = "tc-result-container"

  TC_HISTORY_SUGGESTIONS_BTN = "tc-history-suggestions-btn"
  TC_SUGGEST_LOADING = "tc-suggest-loading"
  SUGGESTION_MODAL = "suggestion-modal"
  SUGGESTION_LIST = "suggestion-list"
  SUGGESTION_ADD_BTN = "suggestion-add-btn"
  VAL_MSG = "val-msg"
  INLINE_SUG_ADD_BTN = "inline-sug-add-btn"
  INLINE_SUG_REJECT_BTN = "inline-sug-reject-btn"
  ASSERT_VAL_MSG = "assert-validation-msg"

  SIM_CONTEXT_CONTAINER = "sim-context-container"
  SUG_ACCORDION = "sug-accordion"
  SUG_ACCORDION_HEADER = "sug-accordion-header"
  SUG_LIST = "sug-list"

  STORE_PLAYGROUND_RESULT = "store-playground-result"
  # What the last ad-hoc run proposed, read by the inline accordion.
  STORE_SUGGESTIONS = "store-suggestions"
  # What the Suggestions modal pulled out of recent runs. Separate, because one
  # store held both and the two panels overwrote each other.
  STORE_HISTORY_SUGGESTIONS = "store-history-suggestions"
  STORE_START_RUN = "store-start-run"
  STORE_SELECTED_INDEX = "selected-test-case-index"
  TC_BREADCRUMB_SUITE_NAME = "tc-breadcrumb-suite-name"

  BTN_ARCHIVE = "test-suite-detail-btn-archive"
  BTN_RESTORE = "test-suite-detail-btn-restore"


class TestSuiteHomeIds:
  """Component IDs for the Test Suites Home page."""

  TEST_SUITES_LIST = "test-suites-grid"
  LOADING = "test-suites-loading-overlay"
  FILTER_COVERAGE = "test-suites-filter-coverage"
  SWITCH_ARCHIVED = "test-suites-switch-archived"


class ShellIds:
  """IDs for the app shell, which every page renders inside."""

  NAV_OVERVIEW = "nav-overview"
  NAV_AGENTS = "nav-agents"
  NAV_EVALUATIONS = "nav-evaluations"
  NAV_TEST_SUITES = "nav-test-suites"
  NAV_COMPARISON = "nav-comparison"
