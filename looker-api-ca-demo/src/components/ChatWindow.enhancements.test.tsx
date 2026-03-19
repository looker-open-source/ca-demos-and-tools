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

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChatWindow } from "./ChatWindow";

describe("ChatWindow Enhancements", () => {
  it("should render THOUGHT messages with bolded summary and normal paragraph", () => {
    const messages = [
      {
        type: "system" as const,
        text: "Summary\n\nParagraph",
        isThought: true,
        parts: ["Summary", "Paragraph"],
      },
    ];

    render(<ChatWindow messages={messages} />);

    // Check for bold summary
    const summary = screen.getByText("Summary");
    expect(summary.tagName).toBe("P");
    expect(summary).toHaveClass("font-bold");

    // Check for paragraph
    expect(screen.getByText("Paragraph")).toBeInTheDocument();
  });

  it("should render query code block and Explore link when provided in payload", () => {
    const mockQuery = { model: "test", view: "test" };
    const messages = [
      {
        type: "system" as const,
        text: "Here's your data",
        payload: {
          query: mockQuery,
          exploreUrl: "https://looker.com/explore/test",
        },
      },
    ];

    render(<ChatWindow messages={messages} />);

    // Check for Query header
    expect(screen.getByText("Looker Query")).toBeInTheDocument();

    // Check for Query content (using regex to ignore whitespace/newlines)
    expect(screen.getByText(/"model":\s*"test"/)).toBeInTheDocument();
    expect(screen.getByText(/"view":\s*"test"/)).toBeInTheDocument();

    // Check for Explore link
    const link = screen.getByRole("link", { name: /open in looker explore/i });
    expect(link).toHaveAttribute("href", "https://looker.com/explore/test");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("should render payload-only messages in the chat window if they have a query", () => {
    const mockQuery = { model: "test" };
    const messages = [
      {
        type: "system" as const,
        text: "", // Empty text
        payload: {
          query: mockQuery,
          exploreUrl: "http://link",
        },
      },
    ];

    render(<ChatWindow messages={messages} />);

    // Should still show the bubble with Query
    expect(screen.getByText("Looker Query")).toBeInTheDocument();
    expect(screen.getByText(/"model":\s*"test"/)).toBeInTheDocument();
  });
});
