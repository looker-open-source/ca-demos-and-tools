// Copyright 2025 Google LLC
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

import React, { useState } from "react";
import { useParams } from "react-router-dom";
import Layout from "./Layout";
import ChatPage from "./ChatPage";
import EmbedPage from "./EmbedPage";

const ChatRouteWrapper: React.FC = () => {
  const { pageId } = useParams<{ pageId: string }>();

  // pull initial avatar from localStorage (fallback to default)
  const defaultAvatar = "/gemini.png";
  const [avatarUrl, setAvatarUrl] = useState(
    localStorage.getItem("customAgentAvatar") || defaultAvatar
  );

  const isBranded =
    pageId === "cymbalpets_branded" || pageId === "cymbalpets_embed";

  const content =
    pageId === "cymbalpets_embed" ? (
      <EmbedPage avatarUrl={avatarUrl} />
    ) : (
      <ChatPage
        variant={isBranded ? "branded" : undefined}
        avatarUrl={avatarUrl}
      />
    );

  return (
    // give Layout a prop it can call when the user uploads a new avatar
    <Layout
      variant={isBranded ? "branded" : undefined}
      onCustomAvatarChange={(url) => setAvatarUrl(url)}
    >
      {content}
    </Layout>
  );
};

export default ChatRouteWrapper;
