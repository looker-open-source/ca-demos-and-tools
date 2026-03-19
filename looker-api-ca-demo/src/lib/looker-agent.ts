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
import type { IAgent } from "@looker/sdk/lib/4.0/models";

/**
 * Lists available conversational agents in Looker using the Looker SDK.
 * @param authToken Optional Bearer token for user-based authentication.
 * @returns A promise that resolves to the array of agents.
 */
export async function listLookerAgents(authToken?: string): Promise<IAgent[]> {
  const sdk = getLookerSDK(authToken);
  
  if (!sdk.authSession.isAuthenticated()) {
    await sdk.authSession.login();
  }

  const agents = await sdk.ok(sdk.search_agents({}));
  return agents;
}
