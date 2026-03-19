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
import { Tooltip } from "./Tooltip";
import { describe, it, expect } from "vitest";

describe("Tooltip", () => {
  it("should render children", () => {
    render(<Tooltip isVisible={true} content="Metadata"><span>Hover Me</span></Tooltip>);
    expect(screen.getByText("Hover Me")).toBeInTheDocument();
  });

  it("should display content when isVisible is true", () => {
    render(<Tooltip isVisible={true} content="Metadata Info"><span>Hover Me</span></Tooltip>);
    expect(screen.getByText("Metadata Info")).toBeInTheDocument();
  });

  it("should NOT display content when isVisible is false", () => {
    render(<Tooltip isVisible={false} content="Metadata Info"><span>Hover Me</span></Tooltip>);
    expect(screen.queryByText("Metadata Info")).not.toBeInTheDocument();
  });

  it("should have the AI-First Dark style", () => {
    render(<Tooltip isVisible={true} content="Metadata Info"><span>Hover Me</span></Tooltip>);
    const tooltipContent = screen.getByText("Metadata Info").parentElement;
    expect(tooltipContent).toHaveClass("bg-zinc-950");
    expect(tooltipContent).toHaveClass("border-zinc-800");
  });
});
