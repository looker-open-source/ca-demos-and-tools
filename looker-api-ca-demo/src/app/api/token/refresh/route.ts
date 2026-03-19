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

import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const { refresh_token } = await req.json();

    if (!refresh_token) {
      return NextResponse.json(
        { error: "Missing refresh_token" },
        { status: 400 },
      );
    }

    const rawBaseUrl = process.env.NEXT_PUBLIC_LOOKER_BASE_URL || "";
    const baseUrl = rawBaseUrl.replace(/\/api\/4\.0\/?$/, "");
    // Looker OAuth documentation uses /api/token
    const tokenUrl = `${baseUrl}/api/token`;

    // Use the OAuth Client ID for Mode B refreshes
    const clientId = process.env.NEXT_PUBLIC_LOOKER_OAUTH_CLIENT_ID;

    const body = {
      grant_type: "refresh_token",
      refresh_token: refresh_token,
      client_id: clientId || "",
    };

    const response = await fetch(tokenUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error("Looker token refresh failed:", response.status, errorText);
      return NextResponse.json(
        { error: "Failed to refresh token" },
        { status: 500 },
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error in token refresh route:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 },
    );
  }
}
