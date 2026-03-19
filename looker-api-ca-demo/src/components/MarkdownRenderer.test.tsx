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

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MarkdownRenderer } from './MarkdownRenderer';

describe('MarkdownRenderer', () => {
  it('should render bold text', () => {
    render(<MarkdownRenderer content="Hello **World**" />);
    const strong = screen.getByText('World');
    expect(strong.tagName).toBe('STRONG');
  });

  it('should render headers', () => {
    render(<MarkdownRenderer content="# Title" />);
    const h1 = screen.getByRole('heading', { level: 1 });
    expect(h1).toHaveTextContent('Title');
  });

  it('should render lists', () => {
    render(<MarkdownRenderer content="- Item 1
- Item 2" />);
    expect(screen.getByText('Item 1')).toBeInTheDocument();
    expect(screen.getByText('Item 2')).toBeInTheDocument();
  });
});
