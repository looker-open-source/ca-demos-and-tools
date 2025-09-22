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
import { appDatasourceReferences, getSystemInstruction } from "./config";
import { askQuestion } from "./GeminiDataAnalytics";
import { VertexAI } from "@google-cloud/vertexai";

const ALLOWED = ["openaq", "thelook", "cymbalpets"] as const;
type Allowed = (typeof ALLOWED)[number];

// Vertex model parameters
const ORCHESTRATOR_LOCATION = "us-central1";
const ORCHESTRATOR_MODEL = "gemini-2.5-flash";

// require an exact single-token match
function exactPickFromText(raw: string): Allowed | null {
  const t = (raw || "").trim().toLowerCase();
  return (ALLOWED as readonly string[]).includes(t) ? (t as Allowed) : null;
}

const ROUTER_SYSTEM_INSTRUCTION = `
You are a strict request router for data questions.

Your job:
- Choose EXACTLY ONE datasource name from: openaq, thelook, cymbalpets.
- Output ONLY that single word (no punctuation, no extra text).
- If the user asks "what data do you have access to" (or similar), respond with an explanation of the datasources.
- If you are unsure based on the question, ask a clarifying question.

Hints:
- air quality, PM2.5/PM10, AQI → openaq
- pet store sales, orders, pet products → cymbalpets
- events, traffic_source, ecommerce web analytics → thelook

Examples:
- "Which cities have the highest PM2.5 lately?" → openaq
- "How many events per traffic source were there last week?" → thelook
- "Average order value for pet toys" → cymbalpets
- "What data can you use?" → "I can use: openaq, thelook, cymbalpets."
`.trim();

export async function orchestrateQuestion(req: Request, res: Response) {
  try {
    const { messages, projectId } = req.body as {
      messages: Array<any>;
      projectId: string;
      pythonAnalysisEnabled?: boolean;
      threadsByDatasource?: Record<Allowed, any[]>;
    };
    if (!messages?.length)
      return res.status(400).json({ error: "Messages is required" });

    const lastText: string | undefined = messages.at(-1)?.userMessage?.text;
    if (!lastText)
      return res.status(400).json({ error: "Last user message missing" });

    // Build model using a single text system instruction
    const vertex = new VertexAI({
      project: projectId,
      location: ORCHESTRATOR_LOCATION,
    });
    const model = vertex.getGenerativeModel({
      model: ORCHESTRATOR_MODEL,
      systemInstruction: {
        role: "system",
        parts: [{ text: ROUTER_SYSTEM_INSTRUCTION }],
      },
    });

    const { response } = await model.generateContent({
      contents: [{ role: "user", parts: [{ text: lastText }] }],
    });

    // Extract routing text
    const raw =
      (response?.candidates?.[0]?.content?.parts ?? [])
        .map((p: any) => p?.text ?? "")
        .join("")
        .trim() ||
      (response as any)?.text?.trim() ||
      "";

    // Only proceed if Gemini output is EXACTLY one of ALLOWED; otherwise short-circuit and return Gemini's text
    const exact = exactPickFromText(raw);
    if (!exact) {
      // Stream a single JSON line with the Gemini text and do not call CA API
      const line = {
        timestamp: new Date().toISOString(),
        systemMessage: { text: { parts: [raw || ""] } },
      };
      res.write(JSON.stringify(line) + "\n");
      res.end();
      return;
    }

    // Proceed with CA API using the exact token
    const selected: Allowed = exact;
    const agentPageId = `cortado_${selected}`;
    const systemInstruction = await getSystemInstruction(agentPageId);

    // Remove any messages with schema result datasources specified to get around CA API validation checks
    function stripMessagesWithDatasources(messages: any[]): any[] {
      return messages.filter((m) => {
        const hasSchemaDatasources =
          "datasources" in (m?.systemMessage?.schema?.result ?? {});
        return !hasSchemaDatasources;
      });
    }
    req.body.messages = stripMessagesWithDatasources(req.body.messages);
    req.body.datasourceReferences =
      appDatasourceReferences[selected].datasourceReferences;
    req.body.systemInstruction = systemInstruction;
    req.body.pythonAnalysisEnabled = Boolean(req.body.pythonAnalysisEnabled);

    return askQuestion(req, res);
  } catch (err: any) {
    console.error("[orchestrateQuestion] error:", err?.message, err?.stack);
    if (!res.headersSent)
      res.status(500).json({ error: "Orchestration failed" });
  }
}
