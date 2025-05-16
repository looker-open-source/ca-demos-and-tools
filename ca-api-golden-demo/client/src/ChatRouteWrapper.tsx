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
