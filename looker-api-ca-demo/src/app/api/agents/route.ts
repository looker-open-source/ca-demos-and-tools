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

import { NextRequest, NextResponse } from 'next/server';
import { listLookerAgents } from '@/lib/looker-agent';

/**
 * Extracts the Bearer token from the Authorization header if present.
 */
function getAuthToken(req: NextRequest): string | undefined {
  const authHeader = req.headers.get("authorization");
  if (authHeader?.startsWith("Bearer ")) {
    return authHeader.substring(7);
  }
  return undefined;
}

export async function GET(req: NextRequest) {
  const authToken = getAuthToken(req);
  const NEXT_PUBLIC_LOOKER_BASE_URL = process.env.NEXT_PUBLIC_LOOKER_BASE_URL;
  const LOOKER_CLIENT_ID = process.env.LOOKER_CLIENT_ID;
  const LOOKER_CLIENT_SECRET = process.env.LOOKER_CLIENT_SECRET;

  if (!authToken && (!NEXT_PUBLIC_LOOKER_BASE_URL || !LOOKER_CLIENT_ID || !LOOKER_CLIENT_SECRET)) {
    return NextResponse.json({ error: 'Looker configuration missing' }, { status: 500 });
  }

  try {
    const agents = await listLookerAgents(authToken);
    return NextResponse.json({
      agents: JSON.parse(JSON.stringify(agents)),
      defaultAgentId: process.env.NEXT_PUBLIC_DEFAULT_AGENT_ID || null,
      lookerBaseUrl: process.env.NEXT_PUBLIC_LOOKER_BASE_URL || null
    });
  } catch (error: any) {
    console.error('[API] Agents Error:', error);
    return NextResponse.json({ error: error.message || 'Failed to fetch agents' }, { status: 500 });
  }
}
