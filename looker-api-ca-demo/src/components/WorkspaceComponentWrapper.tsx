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

import React, { useState } from 'react';

interface WorkspaceComponentWrapperProps {
  children: React.ReactNode;
  title?: string;
  defaultExpanded?: boolean;
  testId?: string;
}

export const WorkspaceComponentWrapper: React.FC<WorkspaceComponentWrapperProps> = ({
  children,
  title,
  defaultExpanded = true,
  testId,
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  return (
    <div className="space-y-2" data-testid={testId}>
      <div className="flex items-center justify-between px-2">
        <div className="flex items-center space-x-3">
          {title && (
            <h4 className="text-sm font-bold text-zinc-300 border-l-2 border-cyan-500 pl-2">
              {title}
            </h4>
          )}
        </div>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="p-1 hover:bg-zinc-800 rounded transition-colors text-zinc-500 hover:text-cyan-400"
          aria-label={isExpanded ? 'Collapse' : 'Expand'}
        >
          {isExpanded ? (
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m18 15-6-6-6 6"/></svg>
          ) : (
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6"/></svg>
          )}
        </button>
      </div>

      <div 
        className={`max-h-[400px] overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-800 ${isExpanded ? 'block' : 'hidden'}`}
        data-testid={testId ? `${testId}-content-wrapper` : undefined}
      >
        {children}
      </div>
    </div>
  );
};
