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
import { Link, useNavigate } from "react-router-dom";
import { onAuthStateChanged, signOut } from "firebase/auth";
import { useUser } from "./UserContext";
import { auth } from "./utils/firebase";
import { persistFileInLocalStorage } from "./utils/storage";

import "./styles/Layout.css";

interface LayoutProps {
  children: React.ReactNode;
  variant?: "default" | "branded";
  onCustomAvatarChange?: (url: string) => void;
}

const DEFAULT_LOGO_URL = "/cymbalpets_horizontal_logo.png";
const DEFAULT_BRANDED_TITLE = "Global Pets Data Agent";
const CUSTOM_VARS = [
  "bodyBackground",
  "userQuestionBackground",
  "userQuestionText",
  "newConversationButtonBackground",
  "newConversationButtonColor",
] as const;

function Layout({
  children,
  variant = "default",
  onCustomAvatarChange,
}: LayoutProps) {
  const { user, setUser } = useUser();
  const [editorOpen, setEditorOpen] = useState(false);
  const navigate = useNavigate();
  const defaultColorsRef = React.useRef<Record<string, string> | null>(null);

  const handleSignOut = async () => {
    try {
      await signOut(auth);
      navigate("/login");
    } catch (error) {
      console.error("Sign out error:", error);
      alert("An error occurred during sign out.");
    }
  };

  // custom logo, title, and colors
  const [logo, setLogo] = useState<string>(
    localStorage.getItem("customLogo") || DEFAULT_LOGO_URL
  );
  const [brandedTitle, setBrandedTitle] = useState(
    localStorage.getItem("customTitle") || DEFAULT_BRANDED_TITLE
  );

  // compute once on mount, store in ref
  const [colors, setColors] = useState<Record<string, string>>(() => {
    const raw = Object.fromEntries(
      CUSTOM_VARS.map((k) => [
        k,
        getComputedStyle(document.documentElement)
          .getPropertyValue(`--${k}`)
          .trim(),
      ])
    ) as Record<string, string>;
    defaultColorsRef.current = raw;
    return {
      ...raw,
      ...JSON.parse(localStorage.getItem("customColors") || "{}"),
    };
  });

  const handleAvatarUpload = (file: File) => {
    persistFileInLocalStorage("customAgentAvatar", file, (url) => {
      onCustomAvatarChange?.(url);
    });
  };

  const handleLogoUpload = (file: File) => {
    persistFileInLocalStorage("customLogo", file, (url) => {
      setLogo(url);
    });
  };

  const resetDefaults = () => {
    setLogo(DEFAULT_LOGO_URL);
    setBrandedTitle(DEFAULT_BRANDED_TITLE);
    if (defaultColorsRef.current) {
      setColors(defaultColorsRef.current);
      // also re-apply them immediately:
      Object.entries(defaultColorsRef.current).forEach(([k, v]) =>
        document.documentElement.style.setProperty(`--${k}`, v)
      );
    }
    localStorage.removeItem("customColors");
    localStorage.removeItem("customLogo");
    localStorage.removeItem("customTitle");
    localStorage.removeItem("customAgentAvatar");
    onCustomAvatarChange?.(
      variant === "branded" ? "/cymbalpets.png" : "/gemini.png"
    );
  };

  // write CSS vars whenever they change
  useEffect(() => {
    if (variant === "branded") {
      const root = document.documentElement;
      for (const k of CUSTOM_VARS) {
        const def = defaultColorsRef.current?.[k] || "";
        root.style.setProperty(`--${k}`, colors[k] ?? def);
      }
      root.style.setProperty("--custom-logo", `url(${logo})`);

      // derive hover from newConversationButtonBackground: darken by 10%
      const defBtn =
        defaultColorsRef.current?.newConversationButtonBackground || "";
      const c = colors.newConversationButtonBackground ?? defBtn;
      const d = c.replace(/^#/, "");
      const n = parseInt(d, 16);
      const r = Math.max(0, (n >> 16) - 16)
        .toString(16)
        .padStart(2, "0");
      const g = Math.max(0, ((n >> 8) & 0xff) - 16)
        .toString(16)
        .padStart(2, "0");
      const b = Math.max(0, (n & 0xff) - 16)
        .toString(16)
        .padStart(2, "0");
      root.style.setProperty("--btnHoverBg", `#${r + g + b}`);
      localStorage.setItem("customLogo", logo);
      localStorage.setItem("customTitle", brandedTitle);
      localStorage.setItem("customColors", JSON.stringify(colors));
    }
  }, [variant, logo, brandedTitle, colors]);

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
              {/* use CSS var for logo */}
              <div className="logo branded logo--custom" />
            </Link>
          ) : (
            <>
              <img src="/gcp_cloud.png" alt="GCP Logo" className="logo" />
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
            <>
              {/* Sign out button */}
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

              {/* Customization button */}
              <button
                className="gear-button"
                onClick={() => setEditorOpen((o) => !o)}
                title="Customize Styles"
              >
                <img
                  src="/settings_gear.png"
                  alt="Customize Styles"
                  className="gear-icon"
                />
              </button>
            </>
          )}
        </div>
      </header>

      {/* Only show editor on branded pages */}
      {editorOpen && variant === "branded" && (
        <div className="style-editor-modal">
          <h2>Customize Branding</h2>

          <div className="editor-row">
            <span className="editor-label">Logo:</span>
            <input
              type="file"
              accept="image/*"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleLogoUpload(f);
              }}
            />
          </div>

          <div className="editor-row">
            <span className="editor-label">Agent Avatar:</span>
            <input
              type="file"
              accept="image/*"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleAvatarUpload(file);
              }}
            />
          </div>

          <div className="editor-row">
            <span className="editor-label"> Page Title:</span>
            <input
              className="page-title-input"
              type="text"
              value={brandedTitle}
              onChange={(e) => setBrandedTitle(e.target.value)}
            />
          </div>

          {CUSTOM_VARS.map((v) => (
            <div key={v} className="editor-row">
              <span className="editor-label">{v}:</span>
              <input
                type="color"
                value={colors[v]}
                onChange={(e) =>
                  setColors((c) => ({ ...c, [v]: e.target.value }))
                }
              />
            </div>
          ))}

          <button onClick={resetDefaults}>Restore Defaults</button>

          <button onClick={() => setEditorOpen(false)}>Close</button>
        </div>
      )}

      <main>
        {variant === "branded" && (
          <div className="branded-title-container">
            <h1>{brandedTitle}</h1>
          </div>
        )}
        {children}
      </main>
    </div>
  );
}

export default Layout;
