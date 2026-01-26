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

"""Component IDs for the Datasets UI."""


class DatasetIds:
  """Component IDs for the Dataset workflow (New, View, Edit)."""

  # Suggestion Edit Modal
  SUG_EDIT_MODAL = "sug-edit-modal"
  SUG_EDIT_TYPE = "sug-edit-assert-type"
  SUG_EDIT_VALUE = "sug-edit-assert-value"
  SUG_EDIT_YAML = "sug-edit-assert-yaml"
  SUG_EDIT_WEIGHT = "sug-edit-assert-weight"
  SUG_EDIT_GUIDE_CONTAINER = "sug-edit-guide-container"
  SUG_EDIT_GUIDE_TITLE = "sug-edit-guide-title"
  SUG_EDIT_GUIDE_DESC = "sug-edit-guide-desc"
  SUG_EDIT_EXAMPLE_CONTAINER = "sug-edit-assert-example-container"
  SUG_EDIT_EXAMPLE_VALUE = "sug-edit-assert-example-value"
  SUG_EDIT_EXAMPLE_YAML = "sug-edit-assert-example-yaml"
  SUG_EDIT_SAVE_BTN = "sug-edit-save-btn"
  SUGGESTION_EDIT_BTN = "suggestion-edit-btn"

  NAME = "dataset-name"
  DESC = "dataset-description"
  SAVE_NEW_BTN = "dataset-save-new-btn"
  SAVE_EDIT_BTN = "dataset-save-edit-btn"
  CANCEL_NEW_BTN = "dataset-cancel-new-btn"
  CANCEL_EDIT_BTN = "dataset-cancel-edit-btn"
  BUILDER_CONTAINER = "dataset-builder-container"
  BULK_ADD_BTN = "dataset-bulk-add-btn"
  PLACEHOLDER_SAVE_BTN = "dataset-placeholder-save-btn"

  # Datasource IDs
  AGENT_SELECT = "dataset-agent-select"

  # Builder IDs (Internal)
  ADD_QUESTION_BTN = "dataset-add-question-btn"
  QUESTION_LIST = "dataset-question-list"

  # Store IDs
  STORE_BUILDER = "suite-builder-state"
  STORE_MODAL = "modal-store"

  # Question Modal Internal IDs
  MODAL_QUESTION = "question-modal"
  MODAL_QUESTION_TEXT = "modal-question-text"
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
  Q_BULK_ADD_BTN = "q-bulk-add-btn"
  MODAL_BULK_ADD = "bulk-add-modal"
  INPUT_BULK_TEXT = "bulk-add-text-input"
  PREVIEW_BULK_ADD = "bulk-add-preview"
  BTN_BULK_ADD_CONFIRM = "bulk-add-confirm-btn"
  BTN_BULK_ADD_CANCEL = "bulk-add-cancel-btn"

  # Edit Config Modal
  BTN_CONFIG_EDIT = "dataset-config-edit-btn"
  MODAL_CONFIG_EDIT = "dataset-config-edit-modal"

  # Distinct IDs for Modal Inputs to avoid collision with Page Inputs
  EDIT_NAME = "dataset-edit-name"
  EDIT_DESC = "dataset-edit-desc"

  MODAL_CONFIG_SAVE_BTN = "dataset-config-save-btn"
  MODAL_CONFIG_CANCEL_BTN = "dataset-config-cancel-btn"
  MODAL_CONFIG_CLOSE_BTN_X = "dataset-config-close-btn-x"

  # Question Playground IDs
  Q_LIST = "q-playground-list"
  Q_LIST_ITEM = "q-playground-list-item"  # For pattern matching
  Q_ADD_BTN = "q-playground-add-btn"
  Q_PLAYGROUND_ADD_BTN = "q-playground-add-btn"  # Alias for updated usage

  # Editor Section
  Q_EDITOR_TITLE = "q-editor-title"
  Q_EDITOR_CONTAINER = "q-editor-container"
  Q_EDITOR_EMPTY = "q-editor-empty"

  # Inputs
  Q_INPUT_QUESTION = "q-input-question"
  Q_INPUT_TAGS = "q-input-tags"
  # Q_INPUT_ASSERTS = "q-input-asserts"  # Deprecated/Removed

  # Assertion Builder Inputs
  Q_ASSERT_LIST = "q-assert-list"
  Q_ASSERT_TYPE = "q-assert-type"
  Q_ASSERT_DESC = "q-assert-desc"
  Q_ASSERT_VALUE = "q-assert-value"
  Q_ASSERT_YAML = "q-assert-yaml"
  Q_ASSERT_EXAMPLE_CONTAINER = "q-assert-example-container"
  Q_ASSERT_EXAMPLE_VALUE = "q-assert-example-value"
  Q_ASSERT_EXAMPLE_YAML = "q-assert-example-yaml"
  Q_ASSERT_WEIGHT = "q-assert-weight"
  Q_ASSERT_COUNT = "q-assert-count"
  Q_ASSERT_WEIGHT_TOGGLE = "q-assert-weight-toggle"  # Pattern ID
  Q_ASSERT_ADD_BTN = "q-assert-add-btn"

  # Actions
  Q_SAVE_BTN = "q-save-btn"
  Q_REVERT_BTN = "q-revert-btn"
  Q_CHANGE_ACTIONS_GROUP = "q-change-actions-group"
  Q_REMOVE_ASSERTION_BTN = "q-remove-assertion-btn"
  Q_REMOVE_QUESTION_BTN = "q-remove-question-btn"
  STORE_DELETE_QUESTION_INDEX = "store-delete-question-index"

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

  # Execution / Playground
  Q_AGENT_SELECT = "q-playground-agent-select"
  Q_RUN_BTN = "q-run-btn"
  Q_SPINNER = "q-spinner"
  Q_RESULT_CONTAINER = "q-result-container"

  # Suggestion
  Q_SUGGEST_BTN = "q-suggest-asserts-btn"
  Q_HISTORY_SUGGESTIONS_BTN = "q-history-suggestions-btn"
  Q_SUGGEST_LOADING = "q-suggest-loading"
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
  STORE_SELECTED_INDEX = "selected-question-index"
  Q_BREADCRUMB_ID = "q-breadcrumb-id"
  Q_BREADCRUMB_SUITE_NAME = "q-breadcrumb-suite-name"


class DatasetHomeIds:
  """Component IDs for the Datasets Home page."""

  DATASETS_LIST = "datasets-grid"
  CREATE_BTN = "create-dataset-btn"
  LOADING = "datasets-loading-overlay"
  FILTER_COVERAGE = "datasets-filter-coverage"
