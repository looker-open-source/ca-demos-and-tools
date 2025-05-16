import React, { useEffect, useState, useRef } from "react";
import { LookerEmbedSDK } from "@looker/embed-sdk";
import { parseFilters } from "utils/dataHelpers";

interface DashboardEmbedProps {
  dashboardId: string;
  onDashboardFilterChange: (currentFilters: string) => void;
}

const LOOKML_MODEL = "cymbal_pets";

const DashboardEmbed: React.FC<DashboardEmbedProps> = ({
  dashboardId,
  onDashboardFilterChange,
}) => {
  const [privateUrl, setPrivateUrl] = useState<string>("");
  const embedRef = useRef<HTMLIFrameElement>(null);

  // Fetch the private embed URL when the dashboardId changes.
  useEffect(() => {
    async function fetchPrivateUrl() {
      try {
        const response = await fetch(
          `/api/looker-embed?dashboardId=${LOOKML_MODEL}::${dashboardId}`
        );
        const data = await response.json();
        if (data.embedUrl) {
          setPrivateUrl(data.embedUrl);
        } else {
          console.error("No embedUrl returned:", data);
        }
      } catch (error) {
        console.error("Error fetching embed URL:", error);
      }
    }
    fetchPrivateUrl();
  }, [dashboardId]);

  // Once we have the embed URL, initialize and embed the dashboard.
  useEffect(() => {
    if (privateUrl && embedRef.current) {
      LookerEmbedSDK.init(process.env.REACT_APP_LOOKER_INSTANCE_URI!);
      LookerEmbedSDK.createDashboardWithUrl(privateUrl)
        .appendTo(embedRef.current)
        .build()
        .connect()
        .then((dashboard) => {
          console.log("Dashboard embedded successfully!", dashboard);
        })
        .catch((error) => {
          console.error("Error embedding dashboard:", error);
        });
    }
  }, [privateUrl]);

  // Listen for events from the iframe
  // https://cloud.google.com/looker/docs/embedded-javascript-events#event_type_summary_table
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const iframeWindow = embedRef.current?.contentWindow;
      if (
        event.source === iframeWindow &&
        event.origin === process.env.REACT_APP_LOOKER_INSTANCE_URI &&
        event.data.action !== "pendo::connect" &&
        event.data.destination !== "pendo-designer-agent" &&
        event.data.action !== 0
      ) {
        try {
          const parsedData = JSON.parse(event.data);
          // console.log("Received message:", parsedData); // uncomment to log all messages

          // Can't use dashboard:filters:changed as this does not capture cross filtering events
          // When user changes filters -> update system instructions
          if (
            parsedData.type === "page:changed" &&
            parsedData.page.type === "dashboard"
          ) {
            const currentFilters = `The user is currently looking at a Looker embedded dashboard with the following filters. Use this filter context to answer their question: ${JSON.stringify(
              parseFilters(parsedData)
            )}`;
            onDashboardFilterChange(currentFilters);
          }
        } catch (err) {
          console.error("Error parsing message data:", err);
        }
      }
    };

    window.addEventListener("message", handleMessage);

    // Remove the listener when the component unmounts
    return () => window.removeEventListener("message", handleMessage);
  }, [onDashboardFilterChange]);

  return (
    <iframe
      id="looker"
      ref={embedRef}
      style={{ width: "100%", border: "none", flexGrow: 1 }}
      title="Embedded Dashboard"
      src={privateUrl}
    ></iframe>
  );
};

export default DashboardEmbed;
