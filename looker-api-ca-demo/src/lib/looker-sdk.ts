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

import { LookerNodeSDK } from "@looker/sdk-node";
import { Looker40SDKStream } from "@looker/sdk/lib/4.0/streams";
import { Looker40SDK } from "@looker/sdk";
import { AuthSession, IApiSettings, IRequestProps, ITransport, AuthToken } from "@looker/sdk-rtl";

/**
 * A custom session for server-side user-based authentication using a Bearer token.
 */
class UserSession extends AuthSession {
  private token: AuthToken;

  constructor(settings: IApiSettings, transport: ITransport, authToken: string) {
    super(settings, transport);
    this.token = new AuthToken({
      access_token: authToken,
      token_type: "Bearer",
      expires_in: 3600,
    });
  }

  async authenticate(props: IRequestProps): Promise<IRequestProps> {
    const token = await this.getToken();
    if (token && token.access_token) {
      props.headers = {
        ...props.headers,
        Authorization: `Bearer ${token.access_token}`,
      };
    }
    return props;
  }

  isAuthenticated(): boolean {
    return !!this.token.access_token;
  }

  async getToken(): Promise<any> {
    return this.token;
  }
}

let sdkInstance: any = null;

/**
 * Initializes and returns an instance of the Looker 4.0 SDK.
 * @param authToken Optional Bearer token for user-based authentication.
 * If provided, returns a new instance for that specific user.
 * If not provided, returns the singleton instance using environment credentials.
 */
export const getLookerSDK = (authToken?: string) => {
  const rawBaseUrl = process.env.NEXT_PUBLIC_LOOKER_BASE_URL || "";
  const baseUrl = rawBaseUrl.replace(/\/api\/4\.0\/?$/, "");

  const settings = {
    base_url: baseUrl,
    client_id: process.env.LOOKER_CLIENT_ID,
    client_secret: process.env.LOOKER_CLIENT_SECRET,
    verify_ssl: true,
    timeout: 120,
    readConfig: () => settings,
  };

  if (authToken) {
    // Mode B: User OAuth using custom UserSession on the server
    // We need to initialize the default transport for the session
    const nodeSdk = LookerNodeSDK.init40(settings as any);
    const session = new UserSession(settings as any, nodeSdk.authSession.transport, authToken);
    const sdk: any = new Looker40SDK(session);
    sdk.stream = new Looker40SDKStream(sdk.authSession);
    return sdk;
  }

  // Mode A: Service Account using singleton
  if (sdkInstance && !authToken) return sdkInstance;

  sdkInstance = LookerNodeSDK.init40(settings as any);

  // Ensure the stream property is available
  if (!sdkInstance.stream) {
    sdkInstance.stream = new Looker40SDKStream(sdkInstance.authSession);
  }

  return sdkInstance;
};
