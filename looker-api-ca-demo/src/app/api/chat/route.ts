// Copyright 2026 Google LLC
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

import { NextRequest, NextResponse } from "next/server";
import { sendLookerChatMessageStreaming } from "@/lib/looker-chat";
import {
  createLookerConversation,
  persistLookerMessages,
} from "@/lib/looker-conversation";
import { listLookerAgents } from "@/lib/looker-agent";
import { dumpDevLog } from "@/lib/log-utils";
import { mapLookerError } from "@/lib/error-mapping";

/**
 * Extracts the Bearer token from the Authorization header if present.
 */
function getAuthToken(req: NextRequest): string | undefined {
  const authHeader = req.headers.get("authorization");
  if (authHeader?.startsWith("Bearer ")) {
    return authHeader.substring(7);
  }
  return undefined;
}

export async function POST(req: NextRequest) {
  const { userMessage, conversationId, agentId, timestamp } = await req.json();
  const authToken = getAuthToken(req);

  const baseUrl = process.env.NEXT_PUBLIC_LOOKER_BASE_URL;
  const clientId = process.env.LOOKER_CLIENT_ID;
  const clientSecret = process.env.LOOKER_CLIENT_SECRET;

  // If no user token, we need server credentials
  if (!authToken && (!baseUrl || !clientId || !clientSecret)) {
    return NextResponse.json(
      { error: "Looker configuration missing" },
      { status: 500 },
    );
  }

  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      try {
        console.log("[API] Starting chat session...");

        let activeConversationId = conversationId;
        if (!activeConversationId) {
          console.log("[API] No conversation ID provided, creating new one...");

          let targetAgentId = agentId;
          if (!targetAgentId) {
            const agents = await listLookerAgents(authToken);
            if (agents.length === 0) throw new Error("No agents found");
            targetAgentId = agents[0].id;
          }

          const createLogId = Math.random().toString(36).substring(2, 9);
          controller.enqueue(
            encoder.encode(
              JSON.stringify({
                type: "dev-log",
                log: {
                  id: createLogId,
                  path: "/conversations",
                  method: "POST",
                  status: "pending",
                  startTime: Date.now(),
                  payload: { 
                    name: `${new Date().toISOString()} - SDK Demo`,
                    agent_id: targetAgentId 
                  }
                }
              }) + "\n"
            )
          );

          const conv = await createLookerConversation(targetAgentId, authToken);
          activeConversationId = conv.id;

          controller.enqueue(
            encoder.encode(
              JSON.stringify({
                type: "dev-log",
                log: { id: createLogId, status: 200, endTime: Date.now() }
              }) + "\n"
            )
          );

          console.log(
            `[API] New conversation created: ${activeConversationId} using agent: ${targetAgentId}`,
          );

          // Send back the new conversation ID first
          controller.enqueue(
            encoder.encode(
              JSON.stringify({
                type: "control",
                conversationId: activeConversationId,
              }) + "\n",
            ),
          );
        }

        const systemMessages: any[] = [];

        console.log(
          `[API] Streaming messages for conversation: ${activeConversationId}`,
        );
        for await (const msg of sendLookerChatMessageStreaming(
          activeConversationId,
          userMessage,
          authToken,
        )) {
          dumpDevLog(activeConversationId, "looker-msg", msg);

          if (msg.error) {
            const mappedError = mapLookerError(msg.error);
            controller.enqueue(
              encoder.encode(
                JSON.stringify({
                  type: "message",
                  data: { systemMessage: { text: { parts: [mappedError] } } },
                }) + "\n",
              ),
            );
          } else {
            systemMessages.push(msg);
            controller.enqueue(
              encoder.encode(
                JSON.stringify({ type: "message", data: msg }) + "\n",
              ),
            );
          }
        }

        // Persist session after streaming
        console.log("[API] Persisting conversation messages...");
        
        const persistLogId = Math.random().toString(36).substring(2, 9);
        const persistPayload = {
          messages: [
            {
              type: "user",
              message: {
                userMessage: { text: userMessage },
                timestamp: timestamp,
              },
            },
            ...systemMessages.map((msg) => ({ type: "system", message: msg })),
          ],
        };

        controller.enqueue(
          encoder.encode(
            JSON.stringify({
              type: "dev-log",
              log: {
                id: persistLogId,
                path: `/conversations/${activeConversationId}/messages`,
                method: "POST",
                status: "pending",
                startTime: Date.now(),
                payload: persistPayload
              }
            }) + "\n"
          )
        );

        dumpDevLog(activeConversationId, "full-turn", {
          userMessage,
          systemMessages,
        });
        await persistLookerMessages(
          activeConversationId,
          userMessage,
          systemMessages,
          timestamp,
          authToken,
        );

        controller.enqueue(
          encoder.encode(
            JSON.stringify({
              type: "dev-log",
              log: { id: persistLogId, status: 200, endTime: Date.now() }
            }) + "\n"
          )
        );

        console.log("[API] Conversation persisted successfully.");

        controller.close();
      } catch (err: any) {
        console.error("[API] Streaming Error:", err);
        controller.enqueue(
          encoder.encode(
            JSON.stringify({ type: "error", message: err.message }) + "\n",
          ),
        );
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
