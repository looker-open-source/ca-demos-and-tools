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

"""IDs for Agent Management Pages."""

import dash


def agent_monitor_btn_add_id(index: str):
  return {"type": "agent-monitor-btn-add", "index": index}


class AgentIds:
  """Namespace for Agent Page IDs."""

  class Home:
    """IDs for Agent Home Page."""

    BTN_MONITOR = "agent-home-btn-monitor"
    CARD_GRID = "agent-home-card-grid"
    SWITCH_ARCHIVED = "agent-home-switch-archived"

    class ChoiceModal:
      ROOT = "agent-choice-modal-root"
      BTN_CREATE = "agent-choice-btn-create"
      BTN_EXISTING = "agent-choice-btn-existing"
      BTN_CANCEL = "agent-choice-btn-cancel"

  class Add:
    BTN_SUBMIT = "agent-add-btn-submit"
    BTN_CANCEL = "agent-add-btn-cancel"
    REDIRECT = "agent-add-redirect"

  class Monitor:
    INPUT_PROJECT = "agent-monitor-input-project"
    INPUT_LOCATION = "agent-monitor-input-location"
    BTN_FETCH = "agent-monitor-btn-fetch"
    TABLE_ROOT = "agent-monitor-table-root"
    REDIRECT = "agent-monitor-redirect"
    SELECT_ENV = "agent-monitor-select-env"
    PREVIEW = "agent-monitor-preview"
    STORE_FETCH_TRIGGER = "agent-monitor-store-fetch-trigger"

    BTN_ADD = {
        "type": "agent-monitor-btn-add",
        "index": dash.dependencies.MATCH,
    }

  class Form:
    """IDs for Agent form fields."""

    INPUT_NAME = "agent-form-input-name"
    INPUT_PROJECT = "agent-form-input-project"
    INPUT_LOCATION = "agent-form-input-location"
    INPUT_RESOURCE_ID = "agent-form-input-resource-id"
    SELECT_ENV = "agent-form-select-env"
    TEXTAREA_INSTRUCTION = "agent-form-textarea-instruction"
    PREVIEW = "agent-form-preview"
    SELECT_DATASOURCE_TYPE = "agent-form-select-datasource-type"
    INPUT_BQ_TABLES = "agent-form-input-bq-tables"
    INPUT_BQ_TABLES_PREVIEW = "agent-form-input-bq-tables-preview"
    INPUT_LOOKER_URI = "agent-form-input-looker-uri"
    INPUT_LOOKER_EXPLORES = "agent-form-input-looker-explores"
    INPUT_LOOKER_EXPLORES_PREVIEW = "agent-form-input-looker-explores-preview"
    INPUT_LOOKER_CLIENT_ID = "agent-form-input-looker-client-id"
    INPUT_LOOKER_CLIENT_SECRET = "agent-form-input-looker-client-secret"
    BTN_TEST_LOOKER = "agent-form-btn-test-looker"
    ALERT_LOOKER_TEST = "agent-form-alert-looker-test"

  class Detail:
    """IDs for Agent Detail Page."""

    ROOT = "agent-detail-root"
    BREADCRUMBS = "agent-detail-breadcrumbs"
    TITLE = "agent-detail-title"
    DESCRIPTION = "agent-detail-description"
    ACTIONS = "agent-detail-actions"
    HEADER_CONTAINER = "agent-detail-header-container"
    CONTENT = "agent-detail-content"
    INSTRUCTION = "agent-detail-instruction"
    STORE_GCP_CONFIG = "agent-detail-store-gcp-config"

    # Edit Modal
    BTN_EDIT = "agent-detail-btn-edit"
    BTN_RUN_EVAL = "agent-detail-btn-run-eval"
    MODAL_EDIT = "agent-detail-modal-edit"
    INPUT_EDIT_NAME = "agent-detail-input-edit-name"
    TEXTAREA_EDIT_INSTRUCTION = "agent-detail-textarea-edit-instruction"
    BTN_EDIT_SUBMIT = "agent-detail-btn-edit-submit"
    EDIT_LOADING_OVERLAY = "agent-detail-edit-loading-overlay"
    INPUT_EDIT_LOOKER_CLIENT_ID = "agent-detail-input-edit-looker-client-id"
    INPUT_EDIT_LOOKER_CLIENT_SECRET = (
        "agent-detail-input-edit-looker-client-secret"
    )
    INPUT_EDIT_PROJECT = "agent-detail-input-edit-project"
    INPUT_EDIT_RESOURCE_ID = "agent-detail-input-edit-resource-id"
    INPUT_EDIT_LOCATION = "agent-detail-input-edit-location"
    INPUT_EDIT_ENV = "agent-detail-input-edit-env"
    CONTAINER_EDIT_LOOKER_CONFIG = "agent-detail-container-edit-looker-config"
    CONTAINER_EDIT_BQ_CONFIG = "agent-detail-container-edit-bq-config"
    INPUT_EDIT_BQ_TABLES = "agent-detail-input-edit-bq-tables"
    INPUT_EDIT_BQ_TABLES_PREVIEW = "agent-detail-input-edit-bq-tables-preview"
    INPUT_EDIT_LOOKER_URI = "agent-detail-input-edit-looker-uri"
    INPUT_EDIT_LOOKER_EXPLORES = "agent-detail-input-edit-looker-explores"
    INPUT_EDIT_GOLDEN_QUERIES = "agent-detail-input-edit-golden-queries"
    BTN_FIX_GOLDEN_QUERIES_AI = "agent-detail-btn-fix-golden-queries-ai"
    ERROR_GOLDEN_QUERIES = "agent-detail-error-golden-queries"
    CARD_GOLDEN_QUERIES = "agent-detail-card-golden-queries"
    SWITCH_INSTRUCTION_VIEW = "agent-detail-switch-instruction-view"
    INSTRUCTION_MARKDOWN = "agent-detail-instruction-markdown"
    INSTRUCTION_RAW = "agent-detail-instruction-raw"

    INPUT_EDIT_LOOKER_EXPLORES_PREVIEW = (
        "agent-detail-input-edit-looker-explores-preview"
    )
    BTN_TEST_LOOKER = "agent-detail-btn-test-looker"
    ALERT_LOOKER_TEST = "agent-detail-alert-looker-test"

    # Duplication Modal
    BTN_DUPLICATE = "agent-detail-btn-duplicate"
    MODAL_DUPLICATE = "agent-detail-modal-duplicate"
    INPUT_DUPLICATE_NAME = "agent-detail-input-duplicate-name"
    BTN_DUPLICATE_SUBMIT = "agent-detail-btn-duplicate-submit"
    DUPLICATE_LOADING_OVERLAY = "agent-detail-duplicate-loading-overlay"
    BTN_ARCHIVE = "agent-detail-btn-archive"
    BTN_RESTORE = "agent-detail-btn-restore"

    MAX_WIDTH = "100%"
    CONTAINER_DATASOURCE = "agent-detail-container-datasource"
    BADGE_DATASOURCE = "agent-detail-badge-datasource"
    STORE_REMOTE_TRIGGER = "agent-detail-store-remote-trigger"
    STORE_REFRESH_TRIGGER = "agent-detail-store-refresh-trigger"
    BTN_EMPTY_RUN_EVAL = {"type": "agent-detail-btn-run-eval", "index": "empty"}

    # Analytics
    SELECT_EVAL_ACCURACY_DAYS = "agent-detail-select-eval-accuracy-days"
    CHART_EVAL_ACCURACY_ROOT = "agent-detail-chart-eval-accuracy-root"
    SELECT_DURATION_DAYS = "agent-detail-select-duration-days"
    CHART_DURATION_ROOT = "agent-detail-chart-duration-root"

    class EvalModal:
      ROOT = "agent-detail-eval-modal"
      SELECT_SUITE = "agent-detail-eval-select-suite"
      BTN_START = "agent-detail-eval-btn-start"
      BTN_CANCEL = "agent-detail-eval-btn-cancel"
      SUITE_DETAILS = "agent-detail-eval-suite-details"
      ALERT_VALIDATION = "agent-detail-eval-alert-validation"
      TOGGLE_SUGGESTIONS = "agent-detail-eval-toggle-suggestions"
      INPUT_CONCURRENCY = "agent-detail-eval-input-concurrency"
