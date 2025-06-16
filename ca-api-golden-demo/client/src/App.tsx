import React, { useState, useEffect } from "react";
import { Routes, Route, Navigate, BrowserRouter } from "react-router-dom";
import { onAuthStateChanged, User } from "firebase/auth";
import { auth } from "./utils/firebase";
import AllowlistWrapper from "./AllowlistWrapper";
import HomePage from "./HomePage";
import ChatRouteWrapper from "./ChatRouteWrapper";
import IframePage from ".//IframePage";
import Multimodal from "Multimodal";
import Resources from "./Resources";
import LoginPage from "./LoginPage";
import Layout from "./Layout";
import { UserProvider } from "./UserContext";

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
                    path="/studio-embed"
                    element={
                      <Layout variant="branded">
                        <IframePage />
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
                        <AllowlistWrapper pageId="cortado_multimodal">
                          <Multimodal />
                        </AllowlistWrapper>
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
