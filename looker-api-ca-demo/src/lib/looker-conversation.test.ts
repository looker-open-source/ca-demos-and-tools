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

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createLookerConversation } from "./looker-conversation";
import { getLookerSDK } from "./looker-sdk";

vi.mock("./looker-sdk", () => ({
  getLookerSDK: vi.fn(),
}));

describe("createLookerConversation", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-02-23T12:00:00Z"));
    
    (getLookerSDK as any).mockReturnValue({
        authSession: {
            isAuthenticated: vi.fn().mockReturnValue(true),
            login: vi.fn().mockResolvedValue(undefined),
        },
        create_conversation: vi.fn(),
        get_conversation: vi.fn(),
        all_conversation_messages: vi.fn(),
        update_conversation: vi.fn(),
        delete_conversation: vi.fn(),
        ok: vi.fn((p) => p),
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("should create a conversation with a timestamped title", async () => {
    const sdk = getLookerSDK();
    (sdk.create_conversation as any).mockResolvedValue({ id: "conv_123" });

    await createLookerConversation();

    const createArgs = (sdk.create_conversation as any).mock.calls[0][0];
    expect(createArgs.name).toContain("2026-02-23T12:00:00");
    expect(createArgs.name).toContain("SDK Demo");
  });
});
