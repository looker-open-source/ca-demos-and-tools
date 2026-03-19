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

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { getLookerSDK } from "./looker-sdk";

// Mock Looker SDKs
vi.mock("@looker/sdk-node", () => ({
  LookerNodeSDK: {
    init40: vi.fn().mockImplementation(() => ({
      authSession: {
        settings: { base_url: "https://test.looker.com" },
        isAuthenticated: vi.fn().mockReturnValue(true),
        transport: {},
      },
    })),
  },
}));

vi.mock("@looker/sdk-rtl", () => {
  class AuthSession {
    settings: any;
    transport: any;
    constructor(settings: any, transport: any) {
      this.settings = settings;
      this.transport = transport;
    }
  }
  class AuthToken {
    access_token: string;
    constructor(token: any) {
      this.access_token = token.access_token;
    }
  }
  return {
    AuthSession,
    AuthToken,
    ProxySession: vi.fn(),
  };
});

vi.mock("@looker/sdk", () => ({
  Looker40SDK: vi.fn(function(session) {
    return {
      authSession: session,
    };
  }),
}));

vi.mock("@looker/sdk/lib/4.0/streams", () => ({
  Looker40SDKStream: vi.fn(function() {
    return {};
  }),
}));

describe("looker-sdk client", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    vi.resetModules();
    process.env = {
      ...originalEnv,
      NEXT_PUBLIC_LOOKER_BASE_URL: "https://test.looker.com",
      LOOKER_CLIENT_ID: "test-id",
      LOOKER_CLIENT_SECRET: "test-secret",
    };
    vi.clearAllMocks();
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  it("should initialize the Looker SDK client with environment credentials by default", () => {
    const sdk = getLookerSDK();
    expect(sdk).toBeDefined();
    expect(sdk.authSession).toBeDefined();
    expect(sdk.authSession.settings.base_url).toContain("test.looker.com");
  });

  it("should initialize the Looker SDK with a Bearer token when provided", () => {
    const testToken = "test-bearer-token";
    const sdk = getLookerSDK(testToken);
    
    expect(sdk).toBeDefined();
    expect(sdk.authSession).toBeDefined();
    // In our mock, the custom session is an instance of AuthSession
    expect(sdk.authSession.isAuthenticated()).toBe(true);
  });
});
