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

from prism.common.schemas import assertion as assertion_schemas
from prism.common.schemas import example as example_schemas
from prism.server.clients import gen_ai_client
import pydantic
import yaml

logger = logging.getLogger(__name__)

BULK_IMPORT_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "prompts", "bulk_import_prompt.txt"
)

# What parse_yaml puts back when the key is absent.
DEFAULT_ASSERTION_WEIGHT = assertion_schemas.AssertionSchema.model_fields[
    "weight"
].default


class BulkImportService:
  """Service for bulk importing test cases with AI assistance."""

  def __init__(self, gen_ai_client_inst: gen_ai_client.GenAIClient):
    self.gen_ai_client = gen_ai_client_inst
    self._prompt_template = self._load_prompt_template()

  def _load_prompt_template(self) -> str:
    """Loads the prompt template from the file system.

    A missing template is a packaging fault, not a runtime condition. Swallowing
    it would send the model an empty prompt and report whatever came back as a
    result, so let it raise.
    """
    with open(BULK_IMPORT_PROMPT_PATH, "r") as f:
      return f.read()

  def format_with_ai(self, input_text: str) -> str:
    """Uses Gemini to format unstructured text into a structured YAML string.

    Blank input gives "".

    A failure raises, the way format_golden_queries does. Both paths used to
    hand the input back instead: the callback wrote it into the textarea
    unchanged and showed nothing, so a quota error and a model with nothing to
    change looked the same and the AI Fix Failed toast was never reached.
    """
    if not input_text.strip():
      return ""

    prompt = self._prompt_template.replace("{{input_text}}", input_text)

    class BulkImportResponse(pydantic.BaseModel):
      test_cases: list[example_schemas.TestCaseInput]

    response = self.gen_ai_client.generate_structured(
        prompt, BulkImportResponse
    )

    if not response or not response.test_cases:
      raise RuntimeError("The model returned no test cases.")

    data = []
    for tc in response.test_cases:
      tc_dict = tc.model_dump(mode="json")
      assertions = tc_dict.get("assertions", [])
      if not assertions:
        tc_dict.pop("assertions", None)
      else:
        for assertion in assertions:
          # Only the default comes out. The pop was unconditional, so a
          # weight the user had typed came back as 1.0 on re-parse and an
          # assertion they had marked diagnostic started counting toward the
          # score.
          if assertion.get("weight") == DEFAULT_ASSERTION_WEIGHT:
            assertion.pop("weight", None)
      data.append(tc_dict)

    return yaml.dump(data, sort_keys=False)

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
      logger.warning("Invalid bulk import YAML: %s", e)
      raise ValueError(f"Invalid format: {str(e)}") from e
