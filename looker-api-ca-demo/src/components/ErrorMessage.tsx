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

interface ErrorMessageProps {
  message: string;
  onRetry?: () => void;
}

export const ErrorMessage: React.FC<ErrorMessageProps> = ({ message, onRetry }) => {
  return (
    <div className="p-4 bg-red-950/30 border border-red-900 rounded-lg flex items-start space-x-3 text-red-200">
      <div className="text-xl shrink-0" aria-hidden="true">⚠️</div>
      <div className="flex-1 min-w-0">
        <h3 className="text-sm font-semibold text-red-400 uppercase tracking-tight mb-1">System Error</h3>
        <p className="text-sm break-words">{message}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-3 text-xs font-bold text-red-400 hover:text-red-300 uppercase tracking-widest flex items-center transition-colors"
          >
            Retry Connection <span className="ml-1">↺</span>
          </button>
        )}
      </div>
    </div>
  );
};
