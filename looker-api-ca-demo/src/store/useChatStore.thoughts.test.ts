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

import { describe, it, expect, beforeEach } from 'vitest';
import { useChatStore } from './useChatStore';

describe('useChatStore - Thought Messages', () => {
  beforeEach(() => {
    useChatStore.setState({
      messages: [],
      conversationId: null,
      isLoading: false,
      error: null,
    });
  });

  it('should append consecutive thoughts to the history', () => {
    const { addMessage } = useChatStore.getState();

    // Add first thought
    // @ts-ignore
    addMessage({ type: 'system', text: 'Reviewing schemas...', isThought: true });
    expect(useChatStore.getState().messages).toHaveLength(1);
    expect(useChatStore.getState().messages[0].text).toBe('Reviewing schemas...');

    // Add second thought - should be appended
    // @ts-ignore
    addMessage({ type: 'system', text: 'Fetching data...', isThought: true });
    expect(useChatStore.getState().messages).toHaveLength(2);
    expect(useChatStore.getState().messages[1].text).toBe('Fetching data...');
  });
});
