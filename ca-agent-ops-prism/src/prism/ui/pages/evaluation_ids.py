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

"""Definitions of UI component IDs for the Prism evaluation pages."""


class EvaluationIds:
  """IDs for Evaluation pages."""

  # List Page
  RUN_LIST_CONTAINER = "evaluations-run-list-container"
  FILTER_AGENT = "evaluations-filter-agent"
  FILTER_DATASET = "evaluations-filter-dataset"
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

  # Dataset View - Run Modal
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
  NEW_EVAL_DATASET_SELECT = "new-eval-dataset-select"
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

  # Suggestions Drawer
