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

import fs from 'fs';
import path from 'path';

const LOG_DIR = path.join(process.cwd(), '.ca_logs');

/**
 * Dumps a payload to a local file for developer debugging.
 * Only runs in development mode.
 * @param conversationId The ID of the conversation to group logs by
 * @param label A label for the entry
 * @param data The data to log
 */
export function dumpDevLog(conversationId: string, label: string, data: any): void {
  if (process.env.NODE_ENV !== 'development') {
    return;
  }

  try {
    if (!fs.existsSync(LOG_DIR)) {
      fs.mkdirSync(LOG_DIR);
    }

    const sanitizedId = conversationId.replace(/[:.]/g, '-');
    
    // Look for an existing file for this conversation
    const files = fs.readdirSync(LOG_DIR);
    let filename = files.find(f => f.endsWith(`_${sanitizedId}.jsonl`));

    if (!filename) {
      // Create new filename with current timestamp
      const timestamp = new Date().toISOString().replace(/\D/g, '').slice(0, 14);
      filename = `${timestamp}_${sanitizedId}.jsonl`;
    }

    const filePath = path.join(LOG_DIR, filename);

    const entry = JSON.stringify({
      timestamp: new Date().toISOString(),
      label,
      data
    }) + '\n';

    fs.appendFileSync(filePath, entry);
    
    // Cleanup: Keep only the 10 most recent conversation files
    const logFiles = fs.readdirSync(LOG_DIR)
      .filter(f => f.endsWith('.jsonl'))
      .map(file => {
        try {
          return { name: file, time: fs.statSync(path.join(LOG_DIR, file)).mtime.getTime() };
        } catch (e) {
          return { name: file, time: 0 };
        }
      })
      .sort((a, b) => b.time - a.time);

    if (logFiles.length > 10) {
      logFiles.slice(10).forEach(file => {
        fs.unlinkSync(path.join(LOG_DIR, file.name));
      });
    }
  } catch (error) {
    console.error('[DevLog] Failed to dump log:', error);
  }
}
