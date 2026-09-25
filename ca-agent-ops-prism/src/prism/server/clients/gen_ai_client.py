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

"""Client for interacting with the Google Vertex AI API."""

import logging
from typing import Any, Type, TypeVar

from google import genai
from google.genai import types
from prism.server.clients import recording
import pydantic

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.8-flash"

ResponseSchema = TypeVar("ResponseSchema", bound=pydantic.BaseModel)


class GenAIClient:
  """A client for interacting with the Google Gen AI API.

  This client uses the `google-genai` SDK (google.genai).
  """

  def __init__(self, project: str, location: str, model: str | None = None):
    """Initializes the GenAIClient.

    Args:
      project: GCP project ID.
      location: Location for Vertex AI.
      model: The name of the Gemini model to use. If not specified, uses the
        default model.
    """
    try:
      self.project = project
      self.location = location

      if not model:
        logger.info(
            "[GenAI] No model specified, using default model: %s",
            DEFAULT_MODEL,
        )
        model = DEFAULT_MODEL
      self.model = model

      if recording.offline():
        # Replaying cassettes. Constructing the SDK client would need
        # credentials for a call that never leaves the process.
        self.client = None
      else:
        self.client = genai.Client(
            vertexai=True, project=self.project, location=self.location
        )

    except Exception as e:  # pylint: disable=broad-except
      logger.error("[GenAI] Failed to initialize Gen AI Client: %s", e)
      raise

  def _cassette_identity(self) -> dict[str, Any]:
    """Fields identifying this client in a cassette key."""
    return {
        "project": self.project,
        "location": self.location,
        "model": self.model,
    }

  @recording.cassette()
  def generate_text(
      self,
      prompt: str,
  ) -> str | None:
    """Generates text using the specified Gemini model.

    Raises whatever the SDK raises. There is no error return.

    Args:
      prompt: The text prompt to send to the model.

    Returns:
      The generated text as a string, or None if the model returned an
      empty response.
    """
    try:
      response = self.client.models.generate_content(
          model=self.model,
          contents=prompt,
      )

      if response and response.text:
        return response.text

      logger.warning("Gen AI response was empty or malformed.")
      return None

    except Exception as e:  # pylint: disable=broad-except
      logger.error("[GenAI] Error during text generation: %s", e, exc_info=True)
      raise

  @recording.cassette(recording.ResponseSchemaCodec())
  def generate_structured(
      self,
      prompt: str,
      response_schema: Type[ResponseSchema],
  ) -> ResponseSchema | None:
    """Generates a structured response from the LLM with the given schema.

    Raises whatever the SDK raises. There is no error return.

    Args:
      prompt: The text prompt to send to the model.
      response_schema: The Pydantic model class to use for validation.

    Returns:
      An instance of the response_schema, or None if the model returned an
      empty response.
    """
    try:
      schema_dict = response_schema.model_json_schema()
      cleaned_schema = self._clean_schema(schema_dict)

      config = types.GenerateContentConfig(
          response_mime_type="application/json",
          response_schema=cleaned_schema,
      )

      response = self.client.models.generate_content(
          model=self.model,
          contents=prompt,
          config=config,
      )

      if response and response.text:
        return response_schema.model_validate_json(response.text)

      logger.warning("Gen AI structured response was empty.")
      return None

    except Exception as e:  # pylint: disable=broad-except
      logger.error(
          "[GenAI] Error during structured generation: %s",
          e,
          exc_info=True,
      )
      raise

  def _clean_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
    """Recursively cleans schema to be compatible with Vertex AI.

    - Removes 'const' keys, replacing with 'enum'.
    - Removes 'null' types from 'oneOf' and 'anyOf' (Vertex AI doesn't
      support NULL type).
    - Hoists a single remaining item to the parent level.
    - Rewrites a surviving 'oneOf' as 'anyOf', which Vertex AI prefers.
    - Removes 'discriminator', which Vertex AI doesn't support.

    Args:
      schema: The JSON schema dictionary to clean.

    Returns:
      The cleaned JSON schema dictionary.
    """
    if not isinstance(schema, dict):
      return schema

    clean = schema.copy()

    if "const" in clean:
      clean["enum"] = [clean.pop("const")]

    for key in ["oneOf", "anyOf"]:
      if key in clean and isinstance(clean[key], list):
        items = [
            item
            for item in clean[key]
            if not (isinstance(item, dict) and item.get("type") == "null")
        ]

        if not items:
          clean.pop(key)
        elif len(items) == 1:
          single_item = items[0]
          clean.pop(key)
          if isinstance(single_item, dict):
            clean.update(single_item)
        else:
          clean.pop(key)
          clean["anyOf"] = items

    if "discriminator" in clean:
      clean.pop("discriminator")

    for key, value in clean.items():
      if isinstance(value, dict):
        clean[key] = self._clean_schema(value)
      elif isinstance(value, list):
        clean[key] = [
            self._clean_schema(item) if isinstance(item, dict) else item
            for item in value
        ]

    return clean
