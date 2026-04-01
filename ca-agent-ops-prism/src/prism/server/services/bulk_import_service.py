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

"""Service for AI-assisted bulk import formatting and validation."""

import logging
import os
from typing import TYPE_CHECKING

from prism.common.schemas import example as example_schemas
from prism.server.clients import gen_ai_client
import pydantic
import yaml

# Path to the prompt template
BULK_IMPORT_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "prompts", "bulk_import_prompt.txt"
)


class BulkImportService:
  """Service for bulk importing test cases with AI assistance."""

  def __init__(self, gen_ai_client_inst: gen_ai_client.GenAIClient):
    self.gen_ai_client = gen_ai_client_inst
    self._prompt_template = self._load_prompt_template()

  def _load_prompt_template(self) -> str:
    """Loads the prompt template from the file system."""
    try:
      with open(BULK_IMPORT_PROMPT_PATH, "r") as f:
        return f.read()
    except FileNotFoundError:
      logging.error(
          "Bulk import prompt template not found at %s", BULK_IMPORT_PROMPT_PATH
      )
      return ""

  def format_with_ai(self, input_text: str) -> str:
    """Uses Gemini to format unstructured text into a structured YAML string."""
    if not input_text.strip():
      return ""

    prompt = self._prompt_template.replace("{{input_text}}", input_text)

    try:
      # Pydantic schema for the list of test cases
      class BulkImportResponse(pydantic.BaseModel):
        test_cases: list[example_schemas.TestCaseInput]

      response = self.gen_ai_client.generate_structured(
          prompt, BulkImportResponse
      )

      if not response or not response.test_cases:
        return input_text

      # Convert to YAML for the editor
      data = []
      for tc in response.test_cases:
        tc_dict = tc.model_dump(mode="json")
        assertions = tc_dict.get("assertions", [])
        if not assertions:
          tc_dict.pop("assertions", None)
        else:
          for assertion in assertions:
            assertion.pop("weight", None)
        data.append(tc_dict)

      return yaml.dump(data, sort_keys=False)

    except Exception:  # pylint: disable=broad-except
      logging.exception("Failed to format bulk import with AI")
      return input_text

  def parse_yaml(self, yaml_text: str) -> list[example_schemas.TestCaseInput]:
    """Parses and validates YAML text into a list of TestCaseInput."""
    if not yaml_text.strip():
      return []

    try:
      data = yaml.safe_load(yaml_text)
      if not isinstance(data, list):
        raise ValueError("Bulk import must be a list of test cases.")

      return [
          example_schemas.TestCaseInput.model_validate(item) for item in data
      ]
    except (yaml.YAMLError, pydantic.ValidationError, ValueError) as e:
      logging.warning("Invalid bulk import YAML: %s", e)
      raise ValueError(f"Invalid format: {str(e)}") from e
