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

'use client';

import React from 'react';
import ReactMarkdown from 'react-markdown';

interface MarkdownRendererProps {
  content: string;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => {
  return (
    <div className="prose prose-invert prose-zinc max-w-none 
      prose-headings:text-cyan-400 prose-headings:font-bold prose-headings:tracking-tight
      prose-strong:text-white prose-strong:font-black
      prose-a:text-cyan-400 hover:prose-a:text-cyan-300
      prose-code:text-cyan-300 prose-code:bg-zinc-900 prose-code:px-1 prose-code:rounded
      prose-pre:bg-zinc-900 prose-pre:border prose-pre:border-zinc-800
      prose-li:marker:text-cyan-500">
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  );
};
