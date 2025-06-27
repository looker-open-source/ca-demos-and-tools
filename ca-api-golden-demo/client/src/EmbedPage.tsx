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

import React, { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import DashboardEmbed from "./DashboardEmbed";
import ChatPage from "./ChatPage";
import { updateSystemInstructions } from "./utils/dataHelpers";

import "./styles/EmbedPage.css";

const DEFAULT_DASHBOARD_ID = "business_pulse";

const EmbedPage: React.FC = () => {
  const { dashboardId } = useParams<{ dashboardId: string }>();
  const [selectedDashboard, setSelectedDashboard] = useState<string>(
    dashboardId || DEFAULT_DASHBOARD_ID
  );
  const [systemInstruction, setSystemInstruction] = useState<
    string | undefined
  >(undefined);

  // Update system instructions with dashboard's current filter selection
  const handleDashboardFilterChange = (currentFilters: string) => {
    console.log(currentFilters);
    if (systemInstruction !== undefined) {
      const newSystemInstruction = updateSystemInstructions(
        systemInstruction,
        currentFilters
      );
      setSystemInstruction(newSystemInstruction);
    }
  };

  // Update selectedDashboard if the URL parameter changes.
  useEffect(() => {
    if (dashboardId) {
      setSelectedDashboard(dashboardId);
    }
  }, [dashboardId]);

  // Fetch/update system instruction from the backend endpoint when dashboard changes
  useEffect(() => {
    const agentPageId = `cortado_cymbalpets_branded_embed_${selectedDashboard}`;
    fetch(`/api/system-instructions?agentPageId=${agentPageId}`)
      .then((res) => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
      })
      .then((data) => {
        setSystemInstruction(data.systemInstruction);
      })
      .catch((err) => {
        console.error("Error fetching system instructions:", err);
      });
  }, [selectedDashboard, dashboardId]);

  return (
    <div className="embed-page">
      <div className="dashboard-content">
        <main className="dashboard-main">
          <DashboardEmbed
            dashboardId={selectedDashboard}
            onDashboardFilterChange={handleDashboardFilterChange}
          />
        </main>

        <aside className="dashboard-sidebar">
          <ChatPage
            variant="branded"
            dashboardId={selectedDashboard}
            systemInstructionOverride={systemInstruction}
          />
        </aside>
      </div>
    </div>
  );
};

export default EmbedPage;
