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

import React from "react";
import { useParams } from "react-router-dom";
import Layout from "./Layout";
import ChatPage from "./ChatPage";
import EmbedPage from "./EmbedPage";

const ChatRouteWrapper: React.FC = () => {
  const { pageId } = useParams<{ pageId: string }>();

  const isBranded =
    pageId === "cymbalpets_branded" || pageId === "cymbalpets_embed";

  const content =
    pageId === "cymbalpets_embed" ? (
      <EmbedPage />
    ) : (
      <ChatPage variant={isBranded ? "branded" : undefined} />
    );

  return <Layout variant={isBranded ? "branded" : undefined}>{content}</Layout>;
};

export default ChatRouteWrapper;
