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

import { getLookerSDK } from "./looker-sdk";
import type {
  IConversation,
  IConversationMessage,
  IWriteConversation,
  IWriteConversationMessages,
} from "@looker/sdk/lib/4.0/models";

async function ensureAuthenticated(sdk: any) {
  if (!sdk.authSession.isAuthenticated()) {
    await sdk.authSession.login();
  }
}

/**
 * Creates a new conversation context in Looker using the Looker SDK.
 * @param agentId The ID of the agent for the conversation.
 * @param authToken Optional Bearer token for user-based authentication.
 * @returns A promise that resolves to the created conversation object.
 */
export async function createLookerConversation(
  agentId?: string,
  authToken?: string,
): Promise<IConversation> {
  const sdk = getLookerSDK(authToken);
  await ensureAuthenticated(sdk);
  const timestamp = new Date().toISOString();
  const body: IWriteConversation = {
    name: `${timestamp} - SDK Demo`,
  };
  if (agentId) {
    (body as any).agent_id = agentId;
  }

  return await sdk.ok(sdk.create_conversation(body));
}

/**
 * Persists messages back to the conversation for context management using the Looker SDK.
 */
export async function persistLookerMessages(
  conversationId: string,
  userQuery: string,
  systemMessages: any[],
  timestamp: string,
  authToken?: string,
): Promise<void> {
  const sdk = getLookerSDK(authToken);
  await ensureAuthenticated(sdk);
  const persistPayload: IWriteConversationMessages = {
    messages: [
      {
        type: "user",
        message: {
          userMessage: { text: userQuery },
          timestamp,
        },
      },
      ...systemMessages.map((msg) => ({ type: "system", message: msg })),
    ],
  };

  await sdk.ok(sdk.create_conversation_message(conversationId, persistPayload));
}

/**
 * Searches for conversations in Looker using the Looker SDK.
 * @param params Search parameters (e.g., agent_id).
 * @param authToken Optional Bearer token for user-based authentication.
 * @returns A promise that resolves to the array of conversations.
 */
export async function searchLookerConversations(
  params: { agent_id: string },
  authToken?: string,
): Promise<IConversation[]> {
  const sdk = getLookerSDK(authToken);
  await ensureAuthenticated(sdk);
  return await sdk.ok(sdk.search_conversations(params as any));
}

/**
 * Gets a single conversation from Looker using the Looker SDK.
 * @param conversationId The ID of the conversation.
 * @param authToken Optional Bearer token for user-based authentication.
 * @returns A promise that resolves to the conversation details.
 */
export async function getLookerConversation(
  conversationId: string,
  authToken?: string,
): Promise<IConversation> {
  const sdk = getLookerSDK(authToken);
  await ensureAuthenticated(sdk);
  return await sdk.ok(sdk.get_conversation(conversationId));
}

/**
 * Gets all messages for a specific conversation using the Looker SDK.
 * @param conversationId The ID of the conversation.
 * @param authToken Optional Bearer token for user-based authentication.
 * @returns A promise that resolves to the array of messages.
 */
export async function getLookerConversationMessages(
  conversationId: string,
  authToken?: string,
): Promise<IConversationMessage[]> {
  const sdk = getLookerSDK(authToken);
  await ensureAuthenticated(sdk);
  return await sdk.ok(sdk.all_conversation_messages(conversationId));
}

/**
 * Deletes a conversation from Looker using the Looker SDK.
 * @param conversationId The ID of the conversation.
 * @param authToken Optional Bearer token for user-based authentication.
 */
export async function deleteLookerConversation(
  conversationId: string,
  authToken?: string,
): Promise<void> {
  const sdk = getLookerSDK(authToken);
  await ensureAuthenticated(sdk);
  await sdk.ok(sdk.delete_conversation(conversationId));
}

/**
 * Updates a conversation in Looker (e.g., renaming) using the Looker SDK.
 * @param conversationId The ID of the conversation.
 * @param body The update body (e.g., { name: 'New Name' }).
 * @param authToken Optional Bearer token for user-based authentication.
 * @returns A promise that resolves to the updated conversation.
 */
export async function patchLookerConversation(
  conversationId: string,
  body: { name: string },
  authToken?: string,
): Promise<IConversation> {
  const sdk = getLookerSDK(authToken);
  await ensureAuthenticated(sdk);
  return await sdk.ok(sdk.update_conversation(conversationId, body as any));
}
