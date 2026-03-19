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
import { searchLookerConversations } from '@/lib/looker-conversation';

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

export async function GET(request: NextRequest) {
  const authToken = getAuthToken(request);
  const baseUrl = process.env.NEXT_PUBLIC_LOOKER_BASE_URL;
  const clientId = process.env.LOOKER_CLIENT_ID;
  const clientSecret = process.env.LOOKER_CLIENT_SECRET;

  if (!authToken && (!baseUrl || !clientId || !clientSecret)) {
    return NextResponse.json(
      { error: 'Looker configuration missing' },
      { status: 500 }
    );
  }

  try {
    const { searchParams } = new URL(request.url);
    const agent_id = searchParams.get('agent_id');
    
    if (!agent_id) {
      return NextResponse.json(
        { error: 'agent_id is required' },
        { status: 400 }
      );
    }

    const conversations = await searchLookerConversations({ agent_id }, authToken);

    return NextResponse.json(JSON.parse(JSON.stringify(conversations)));
  } catch (error: any) {
    console.error('Conversations search error:', error);
    return NextResponse.json(
      { error: error.message || 'Internal Server Error' },
      { status: 500 }
    );
  }
}
