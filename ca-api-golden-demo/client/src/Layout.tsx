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

import React, { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { onAuthStateChanged, signOut } from "firebase/auth";
import { useUser } from "./UserContext";
import { auth } from "./utils/firebase";
import "./styles/Layout.css";

interface LayoutProps {
  children: React.ReactNode;
  variant?: "default" | "branded";
}

function Layout({ children, variant = "default" }: LayoutProps) {
  const { user, setUser } = useUser();
  const navigate = useNavigate();

  const handleSignOut = async () => {
    try {
      await signOut(auth);
      navigate("/login");
    } catch (error) {
      console.error("Sign out error:", error);
      alert("An error occurred during sign out.");
    }
  };

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (authUser) => {
      setUser(authUser);
    });
    return () => unsubscribe();
  }, [setUser]);

  // Add a custom body class for the branded variant
  useEffect(() => {
    if (variant === "branded") {
      document.body.classList.add("branded");
    } else {
      document.body.classList.remove("branded");
    }
    return () => {
      document.body.classList.remove("branded");
    };
  }, [variant]);

  return (
    <div className={`page-container ${variant === "branded" ? "branded" : ""}`}>
      <header className={`banner ${variant === "branded" ? "branded" : ""}`}>
        <div className="banner-left">
          {variant === "branded" ? (
            <Link to="/">
              <img
                src="/cymbalpets_horizontal_logo.png"
                alt="Cymbal Pets Logo"
                className="logo branded"
              />
            </Link>
          ) : (
            <>
              <img src="/looker_logo.png" alt="Looker Logo" className="logo" />
              <Link to="/" className="site-title">
                Conversational Analytics API
              </Link>
            </>
          )}
        </div>
        <nav className={`banner-nav ${variant === "branded" ? "branded" : ""}`}>
          <ul className="nav-list">
            {variant === "branded" ? (
              <>
                {/* TODO unhide route when ready to publish */}
                {/* <li className="nav-item dropdown branded">
                  <span className="nav-link dropdown-toggle" role="button">
                    Reports
                  </span>
                  <ul className="dropdown-menu">
                    <li>
                      <Link to="/studio-embed" className="dropdown-item">
                        Business Pulse
                      </Link>
                    </li>
                  </ul>
                </li> */}

                <li className="nav-item dropdown branded">
                  <span className="nav-link dropdown-toggle" role="button">
                    Dashboards
                  </span>
                  <ul className="dropdown-menu">
                    <li>
                      <Link
                        to="/chat/cymbalpets_embed/business_pulse"
                        className="dropdown-item"
                      >
                        Business Pulse
                      </Link>
                    </li>
                    <li>
                      <Link
                        to="/chat/cymbalpets_embed/supplier_metrics"
                        className="dropdown-item"
                      >
                        Supplier Metrics
                      </Link>
                    </li>
                  </ul>
                </li>

                <li className="nav-item dropdown branded">
                  <span className="nav-link dropdown-toggle">Chat</span>
                  <ul className="dropdown-menu">
                    <li>
                      <Link to="/chat/cymbalpets" className="dropdown-item">
                        Classic
                      </Link>
                    </li>
                    <li>
                      <Link
                        to="/chat/cymbalpets_branded"
                        className="dropdown-item"
                      >
                        Branded
                      </Link>
                    </li>
                  </ul>
                </li>

                <li className="nav-item dropdown branded">
                  <span className="nav-link dropdown-toggle">Multimodal</span>
                  <ul className="dropdown-menu">
                    <li>
                      <Link
                        to="/chat/multimodal?datasource=bq"
                        className="dropdown-item"
                      >
                        BigQuery
                      </Link>
                    </li>
                    <li>
                      <Link
                        to="/chat/multimodal?datasource=looker"
                        className="dropdown-item"
                      >
                        Looker
                      </Link>
                    </li>
                  </ul>
                </li>
                <li className="nav-item branded">
                  <Link to="/resources" className="nav-link">
                    Help
                  </Link>
                </li>
              </>
            ) : (
              <>
                <li className="nav-item">
                  <Link to="/chat/openaq" className="nav-link">
                    OpenAQ
                  </Link>
                </li>
                <li className="nav-item">
                  <Link to="/chat/thelook" className="nav-link">
                    The Look
                  </Link>
                </li>
                <li className="nav-item dropdown">
                  <span className="nav-link dropdown-toggle" role="button">
                    Cymbal Pets
                  </span>

                  <ul className="dropdown-menu">
                    <li className="dropdown-submenu">
                      <span className="dropdown-item dropdown-toggle">
                        Chat
                      </span>
                      <ul className="dropdown-menu">
                        <li>
                          <Link to="/chat/cymbalpets" className="dropdown-item">
                            Classic
                          </Link>
                        </li>
                        <li>
                          <Link
                            to="/chat/cymbalpets_branded"
                            className="dropdown-item"
                          >
                            Branded
                          </Link>
                        </li>
                      </ul>
                    </li>

                    {/* TODO unhide route when ready to publish */}
                    {/* <li className="dropdown-submenu">
                      <span className="dropdown-item dropdown-toggle">
                        Reports
                      </span>
                      <ul className="dropdown-menu">
                        <li>
                          <Link to="/studio-embed" className="dropdown-item">
                            Business Pulse
                          </Link>
                        </li>
                      </ul>
                    </li> */}

                    <li className="dropdown-submenu">
                      <span className="dropdown-item dropdown-toggle">
                        Embed
                      </span>
                      <ul className="dropdown-menu">
                        <li>
                          <Link
                            to="/chat/cymbalpets_embed/business_pulse"
                            className="dropdown-item"
                          >
                            Business Pulse
                          </Link>
                        </li>
                        <li>
                          <Link
                            to="/chat/cymbalpets_embed/supplier_metrics"
                            className="dropdown-item"
                          >
                            Supplier Metrics
                          </Link>
                        </li>
                      </ul>
                    </li>

                    <li className="dropdown-submenu">
                      <span className="dropdown-item dropdown-toggle">
                        Multimodal
                      </span>
                      <ul className="dropdown-menu">
                        <li>
                          <Link
                            to="/chat/multimodal?datasource=bq"
                            className="dropdown-item"
                          >
                            BigQuery
                          </Link>
                        </li>
                        <li>
                          <Link
                            to="/chat/multimodal?datasource=looker"
                            className="dropdown-item"
                          >
                            Looker
                          </Link>
                        </li>
                      </ul>
                    </li>
                  </ul>
                </li>

                <li className="nav-item">
                  <Link to="/resources" className="nav-link">
                    Resources
                  </Link>
                </li>
              </>
            )}
          </ul>
        </nav>
        <div className="banner-right">
          {user && (
            <div className="user-info">
              {user.photoURL && (
                <img
                  src={user.photoURL}
                  alt="User Avatar"
                  className="user-avatar"
                  referrerPolicy="no-referrer"
                />
              )}
              <button onClick={handleSignOut} className="sign-out-button">
                Log Out
              </button>
            </div>
          )}
        </div>
      </header>
      <main>
        {variant === "branded" && (
          <div className="branded-title-container">
            <h1>Global Pets Data Agent</h1>
          </div>
        )}
        {children}
      </main>
    </div>
  );
}

export default Layout;
