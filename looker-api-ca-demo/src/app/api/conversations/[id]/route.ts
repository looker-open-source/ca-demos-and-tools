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
import {
  getLookerConversation,
  deleteLookerConversation,
  patchLookerConversation,
} from '@/lib/looker-conversation';

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

function checkConfig(authToken?: string) {
  const baseUrl = process.env.NEXT_PUBLIC_LOOKER_BASE_URL;
  const clientId = process.env.LOOKER_CLIENT_ID;
  const clientSecret = process.env.LOOKER_CLIENT_SECRET;

  if (!authToken && (!baseUrl || !clientId || !clientSecret)) {
    throw new Error('Looker configuration missing');
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const authToken = getAuthToken(request);
    checkConfig(authToken);
    const conversation = await getLookerConversation(id, authToken);
    return NextResponse.json(JSON.parse(JSON.stringify(conversation)));
  } catch (error: any) {
    console.error('Get conversation error:', error);
    const status = error.message === 'Looker configuration missing' ? 500 : 500;
    return NextResponse.json(
      { error: error.message || 'Internal Server Error' },
      { status }
    );
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const authToken = getAuthToken(request);
    checkConfig(authToken);
    await deleteLookerConversation(id, authToken);
    return NextResponse.json({ success: true });
  } catch (error: any) {
    console.error('Delete conversation error:', error);
    return NextResponse.json(
      { error: error.message || 'Internal Server Error' },
      { status: 500 }
    );
  }
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const { name } = await request.json();
    if (!name) {
      return NextResponse.json(
        { error: 'name is required' },
        { status: 400 }
      );
    }

    const authToken = getAuthToken(request);
    checkConfig(authToken);
    const conversation = await patchLookerConversation(id, { name }, authToken);
    return NextResponse.json(JSON.parse(JSON.stringify(conversation)));
  } catch (error: any) {
    console.error('Patch conversation error:', error);
    return NextResponse.json(
      { error: error.message || 'Internal Server Error' },
      { status: 500 }
    );
  }
}
