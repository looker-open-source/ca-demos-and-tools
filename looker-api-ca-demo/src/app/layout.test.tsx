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

import { expect, it, describe, vi } from "vitest";

vi.mock("next/font/google", () => ({
  Geist: () => ({ variable: "geist-sans" }),
  Geist_Mono: () => ({ variable: "geist-mono" }),
}));

import { metadata } from "./layout";

describe("RootLayout Metadata", () => {
  it("should have the correct title", () => {
    expect(metadata.title).toBe("Looker CA API Demo");
  });

  it("should have the correct description", () => {
    expect(metadata.description).toBe("A demo reference app for Looker SDK and Gemini Data Analytics API integration.");
  });

  it("should have the correct icon", () => {
    expect((metadata.icons as any)?.icon).toBe("/favicon.png");
  });
});
