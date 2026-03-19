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

/**
 * Sends a message to the Looker Conversational Analytics API and streams the response.
 * @param conversationId The ID of the conversation.
 * @param userQuery The user's query text.
 * @param authToken Optional Bearer token for user-based authentication.
 * @returns An async generator that yields parsed message chunks.
 */
export async function* sendLookerChatMessageStreaming(
  conversationId: string,
  userQuery: string,
  authToken?: string
): AsyncGenerator<any> {
  const sdk = getLookerSDK(authToken);

  // Ensure authenticated
  if (!sdk.authSession.isAuthenticated()) {
    await sdk.authSession.login();
  }

  const body = {
    conversation_id: conversationId,
    user_message: userQuery,
  };

  const queue: any[] = [];
  let resolveNext: ((value: any) => void) | null = null;
  let finished = false;
  let error: any = null;

  const push = (obj: any) => {
    if (resolveNext) {
      resolveNext(obj);
      resolveNext = null;
    } else {
      queue.push(obj);
    }
  };

  const callback = async (response: Response) => {
    const reader = response.body?.getReader();
    if (!reader) {
        finished = true;
        if (resolveNext) {
            resolveNext(null);
            resolveNext = null;
        }
        return;
    }
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        
        // Strategy: Attempt to extract and parse JSON objects from the buffer.
        // This is a basic approach to handle pretty-printed JSON or multiple objects.
        let startIndex = buffer.indexOf('{');
        while (startIndex !== -1) {
            let braceCount = 0;
            let endIndex = -1;
            let inString = false;
            let escaped = false;

            for (let i = startIndex; i < buffer.length; i++) {
                const char = buffer[i];
                if (char === '"' && !escaped) {
                    inString = !inString;
                }
                if (!inString) {
                    if (char === '{') braceCount++;
                    if (char === '}') braceCount--;
                    if (braceCount === 0) {
                        endIndex = i;
                        break;
                    }
                }
                escaped = char === '\\' && !escaped;
            }

            if (endIndex !== -1) {
                const jsonStr = buffer.substring(startIndex, endIndex + 1);
                try {
                    const obj = JSON.parse(jsonStr);
                    push(obj);
                } catch (e) {
                    // Ignore parsing errors for partial/invalid matches
                }
                buffer = buffer.substring(endIndex + 1);
                startIndex = buffer.indexOf('{');
            } else {
                // Incomplete object, wait for more data
                break;
            }
        }
      }
    } catch (e) {
      error = e;
    } finally {
      finished = true;
      if (resolveNext) {
        resolveNext(null);
        resolveNext = null;
      }
    }
  };

  // Start the SDK stream
  sdk.stream.conversational_analytics_chat(callback, body);

  while (true) {
    if (queue.length > 0) {
      yield queue.shift();
    } else if (finished) {
      if (error) throw error;
      break;
    } else {
      const next = await new Promise((resolve) => {
        resolveNext = resolve;
      });
      if (next !== null) yield next;
    }
  }
}
