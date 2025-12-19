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
import { Routes, Route, Navigate, BrowserRouter } from "react-router-dom";
import { onAuthStateChanged, User } from "firebase/auth";
import { auth } from "./utils/firebase";
import HomePage from "./HomePage";
import ChatRouteWrapper from "./ChatRouteWrapper";
import Multimodal from "Multimodal";
import Resources from "./Resources";
import LoginPage from "./LoginPage";
import Layout from "./Layout";
import { UserProvider } from "./UserContext";
import OrchestratePage from "./OrchestratePage";

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (authUser) => {
      setUser(authUser);
      setIsLoading(false);
    });
    return () => unsubscribe();
  }, []);

  if (isLoading) {
    return <div>Loading...</div>;
  }

  return (
    <BrowserRouter>
      <UserProvider>
        <Routes>
          <Route
            path="/login"
            element={user ? <Navigate to="/" replace /> : <LoginPage />}
          />
          <Route
            path="*"
            element={
              user ? (
                <Routes>
                  <Route
                    path="/"
                    element={
                      <Layout>
                        <HomePage />
                      </Layout>
                    }
                  />
                  <Route
                    path="/chat/:pageId/:dashboardId?"
                    element={<ChatRouteWrapper />}
                  />
                  <Route
                    path="/chat/multimodal"
                    element={
                      <Layout variant="branded">
                        <Multimodal />
                      </Layout>
                    }
                  />
                  <Route
                    path="/orchestrate"
                    element={
                      <Layout>
                        <OrchestratePage />
                      </Layout>
                    }
                  />
                  <Route
                    path="/resources"
                    element={
                      <Layout>
                        <Resources />
                      </Layout>
                    }
                  />
                </Routes>
              ) : (
                <Navigate to="/login" replace />
              )
            }
          />
        </Routes>
      </UserProvider>
    </BrowserRouter>
  );
}

export default App;
