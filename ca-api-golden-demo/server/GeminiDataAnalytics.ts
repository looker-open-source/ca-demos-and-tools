// Copyright 2025 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import { Request, Response } from "express";
import { TextDecoderStream } from "node:stream/web";
import {
  BqTableReference,
  LookerExploreReference,
  LookerStudioReference,
  Messages,
} from "./config";
import logger from "./logger";

interface askQuestionRequestBody {
  email: string;
  projectId: string;
  token: string;
  messages: Messages[];
  datasourceReferences:
    | BqTableReference
    | LookerExploreReference
    | LookerStudioReference;
  systemInstruction: string;
  pythonAnalysisEnabled: boolean;
}

export async function askQuestion(req: Request, res: Response) {
  const {
    email,
    projectId,
    token,
    messages,
    datasourceReferences,
    systemInstruction,
    pythonAnalysisEnabled,
  } = req.body as askQuestionRequestBody;

  // removing looker API keys from logs
  const datasourceReferencesLog =
    "looker" in datasourceReferences
      ? datasourceReferences.looker.explore_references
      : datasourceReferences;
  logger.info({
    email,
    projectId,
    question: messages.at(-1),
    datasourceReferencesLog,
    pythonAnalysisEnabled,
  });

  const url = `https://geminidataanalytics.googleapis.com/v1beta/projects/${projectId}/locations/global:chat`;

  const headers = {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };

  const data = {
    messages,
    inlineContext: {
      systemInstruction,
      datasourceReferences,
      options: {
        analysis: {
          python: {
            enabled: pythonAnalysisEnabled,
          },
        },
      },
    },
  };

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: headers,
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      logger.error(`Error: ${response.status}, ${response.statusText}`);
      const errorText = await response.text();
      logger.error(`Error Details: ${errorText}`);
      return res.status(response.status).send(errorText);
    }

    const decoder = new TextDecoderStream();
    const reader = response.body!.pipeThrough(decoder).getReader();

    const processStream = async () => {
      let partialData = "";

      try {
        while (true) {
          const { done, value } = await reader.read();

          if (done) {
            if (partialData.trim()) {
              try {
                // remove leading and trailing '[' and ']'
                if (partialData.trim().startsWith("[")) {
                  partialData = partialData.substring(1, partialData.length);
                }
                if (partialData.trim().endsWith("]")) {
                  partialData = partialData.substring(
                    0,
                    partialData.length - 1
                  );
                }
                const lastObject = JSON.parse(partialData);
                logger.info("Processing final API chunk", lastObject);
                res.write(JSON.stringify(lastObject) + "\n");
              } catch (error) {
                logger.error(
                  "Error parsing the final chunk:",
                  error,
                  partialData
                );
              }
            }
            logger.info("Stream ended.");
            break;
          }

          partialData += value;
          const chunks = partialData.split(",\r\n"); // Split the data by ',\r\n'
          for (let i = 0; i < chunks.length - 1; i++) {
            let chunk = chunks[i];
            if (i === 0 && chunk.startsWith("[")) {
              chunk = chunk.substring(1); // remove '[' from leading chunk
            }
            if (chunk.trim().endsWith("]")) {
              chunk = chunk.substring(0, chunk.length - 1); // remove ']' from final chunk
              continue;
            }

            try {
              const jsonObject = JSON.parse(chunk);
              logger.info("Processing API chunk", jsonObject);
              // Stream each JSON string chunk to client
              res.write(JSON.stringify(jsonObject) + "\n");
            } catch (error) {
              logger.error("Error parsing JSON:", error, "Chunk:", chunk);
            }
          }

          // Keep the last chunk (which might be incomplete) for the next iteration
          partialData = chunks[chunks.length - 1];
        }
      } catch (error) {
        logger.error("Error during stream processing:", error);
        if (!res.headersSent) {
          res.status(500).send("Internal Server Error");
        }
      } finally {
        res.end();
      }
    };

    processStream();
  } catch (error) {
    logger.error("Error:", error);
    if (!res.headersSent) {
      res.status(500).send("Internal Server Error");
    }
  }
}
