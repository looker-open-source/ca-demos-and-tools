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

import { render, screen } from "@testing-library/react";
import LoadingOverlay from "./LoadingOverlay";
import { describe, it, expect } from "vitest";

describe("LoadingOverlay", () => {
  it("should be visible when isVisible is true", () => {
    render(<LoadingOverlay isVisible={true} />);
    const overlay = screen.getByTestId("loading-overlay");
    expect(overlay).toBeInTheDocument();
    expect(overlay).toHaveClass("fixed");
    expect(overlay).toHaveClass("inset-0");
  });

  it("should NOT be visible when isVisible is false", () => {
    const { queryByTestId } = render(<LoadingOverlay isVisible={false} />);
    expect(queryByTestId("loading-overlay")).not.toBeInTheDocument();
  });

  it("should have the AI-First Glow effect (neon cyan pulse)", () => {
    render(<LoadingOverlay isVisible={true} />);
    const pulse = screen.getByTestId("loading-pulse");
    expect(pulse).toHaveClass("bg-cyan-400");
    expect(pulse).toHaveClass("animate-pulse");
  });
});
