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

"""IDs for the Agent Context Prototype Page."""


class ContextPrototypeIds:
  """IDs for Agent Context Prototype Page."""

  ROOT = "context-proto-root"
  TABS = "context-proto-tabs"

  # Store for UI state (list of examples, glossary terms, etc.)
  STORE_STATE = "context-proto-store-state"

  # General
  INSTRUCTION = "context-proto-instruction"

  # Datasources
  SELECT_DS_TYPE = "context-proto-select-ds-type"
  BQ_TABLE_LIST = "context-proto-bq-table-list"
  BTN_ADD_BQ_TABLE = "context-proto-btn-add-bq-table"
  LOOKER_URI = "context-proto-looker-uri"
  LOOKER_EXPLORE_LIST = "context-proto-looker-explore-list"
  BTN_ADD_LOOKER_EXPLORE = "context-proto-btn-add-looker-explore"

  # Golden Queries (Looker)
  GOLDEN_LIST = "context-proto-golden-list"
  BTN_ADD_GOLDEN = "context-proto-btn-add-golden"

  # Schema Relationships
  RELATION_LIST = "context-proto-relation-list"
  BTN_ADD_RELATION = "context-proto-btn-add-relation"

  # Examples
  EXAMPLE_LIST = "context-proto-example-list"
  BTN_ADD_EXAMPLE = "context-proto-btn-add-example"

  # Glossary
  GLOSSARY_LIST = "context-proto-glossary-list"
  BTN_ADD_GLOSSARY = "context-proto-btn-add-glossary"

  # Advanced
  SWITCH_PYTHON = "context-proto-switch-python"
  INPUT_MAX_BYTES = "context-proto-input-max-bytes"

  # Actions
  BTN_SAVE = "context-proto-btn-save"
  OUTPUT_JSON = "context-proto-output-json"
  SUMMARY_CARD = "context-proto-summary-card"

  @staticmethod
  def example_row(index: int):
    return {"type": "context-proto-example-row", "index": index}

  @staticmethod
  def example_question(index: int):
    return {"type": "context-proto-example-question", "index": index}

  @staticmethod
  def example_sql(index: int):
    return {"type": "context-proto-example-sql", "index": index}

  @staticmethod
  def example_delete(index: int):
    return {"type": "context-proto-example-delete", "index": index}

  @staticmethod
  def glossary_row(index: int):
    return {"type": "context-proto-glossary-row", "index": index}

  @staticmethod
  def glossary_term(index: int):
    return {"type": "context-proto-glossary-term", "index": index}

  @staticmethod
  def glossary_desc(index: int):
    return {"type": "context-proto-glossary-desc", "index": index}

  @staticmethod
  def glossary_delete(index: int):
    return {"type": "context-proto-glossary-delete", "index": index}

  @staticmethod
  def bq_table_row(index: int):
    return {"type": "context-proto-bq-table-row", "index": index}

  @staticmethod
  def bq_table_input(index: int):
    return {"type": "context-proto-bq-table-input", "index": index}

  @staticmethod
  def bq_table_delete(index: int):
    return {"type": "context-proto-bq-table-delete", "index": index}

  @staticmethod
  def looker_explore_row(index: int):
    return {"type": "context-proto-looker-explore-row", "index": index}

  @staticmethod
  def looker_explore_model(index: int):
    return {"type": "context-proto-looker-explore-model", "index": index}

  @staticmethod
  def looker_explore_name(index: int):
    return {"type": "context-proto-looker-explore-name", "index": index}

  @staticmethod
  def looker_explore_delete(index: int):
    return {"type": "context-proto-looker-explore-delete", "index": index}

  @staticmethod
  def golden_row(index: int):
    return {"type": "context-proto-golden-row", "index": index}

  @staticmethod
  def golden_questions(index: int):
    return {"type": "context-proto-golden-questions", "index": index}

  @staticmethod
  def golden_model(index: int):
    return {"type": "context-proto-golden-model", "index": index}

  @staticmethod
  def golden_explore(index: int):
    return {"type": "context-proto-golden-explore", "index": index}

  @staticmethod
  def golden_delete(index: int):
    return {"type": "context-proto-golden-delete", "index": index}

  @staticmethod
  def relation_row(index: int):
    return {"type": "context-proto-relation-row", "index": index}

  @staticmethod
  def relation_left_table(index: int):
    return {"type": "context-proto-relation-left-table", "index": index}

  @staticmethod
  def relation_left_cols(index: int):
    return {"type": "context-proto-relation-left-cols", "index": index}

  @staticmethod
  def relation_right_table(index: int):
    return {"type": "context-proto-relation-right-table", "index": index}

  @staticmethod
  def relation_right_cols(index: int):
    return {"type": "context-proto-relation-right-cols", "index": index}

  @staticmethod
  def relation_delete(index: int):
    return {"type": "context-proto-relation-delete", "index": index}
