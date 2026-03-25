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
import { DataChatServiceClient } from "@google-cloud/geminidataanalytics";
import { auth } from "./authHelper";
import logger from "./logger";

// Initialize the DataChatServiceClient with the shared auth object.
const client = new DataChatServiceClient({
  auth: auth as any,
});

export async function askQuestion(req: Request, res: Response) {
  const { projectId, messages, datasourceReferences, systemInstruction, pythonAnalysisEnabled } = req.body;

  try {
    const stream = client.chat({
      parent: `projects/${projectId}/locations/global`,
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
    });

    stream.on("data", (response) => {
      // Flatten the data array if present to match the format expected by the frontend.
      // This converts Protobuf Structs back into plain JavaScript objects.
      if (response?.systemMessage?.data?.result?.data) {
        response.systemMessage.data.result.data = response.systemMessage.data.result.data.map((row: any) => {
          const flat: any = {};
          for (const key in row.fields) {
            const value = row.fields[key];
            flat[key] = value[value.kind];
          }
          return flat;
        });
      }
      res.write(JSON.stringify(response) + "\n");
    });

    stream.on("error", (error) => {
      logger.error("Error during stream processing:", error);
      if (!res.headersSent) {
        res.status(500).send("Internal Server Error");
      }
      res.end();
    });

    stream.on("end", () => res.end());
  } catch (error) {
    logger.error("Error:", error);
    if (!res.headersSent) {
      res.status(500).json({ error: "An error occurred" });
    }
  }
}
