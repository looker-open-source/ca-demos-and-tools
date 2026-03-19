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

/**
 * Maps technical Looker API errors to user-friendly messages.
 * @param error The raw error object from the API.
 * @returns A string containing a helpful user message.
 */
export function mapLookerError(error: any): string {
  if (!error) {
    return 'An unexpected error occurred. Please try again.';
  }

  const message = error.message || '';

  if (message.includes('ACTION_GENERATION')) {
    return 'I encountered an internal error while trying to process your request (Action Generation Failed). This might be due to a complex query or a temporary issue with the AI backend. Please try rephrasing your question.';
  }

  if (error.code === 500) {
    return 'Something went wrong on the server while processing your query. Please try again in a few moments.';
  }

  return error.message || 'An unknown error occurred during the conversation.';
}
