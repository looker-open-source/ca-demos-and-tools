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

import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Looker CA API Demo",
  description: "A demo reference app for Looker SDK and Gemini Data Analytics API integration.",
  icons: {
    icon: "/favicon.png",
  },
};

// Force dynamic rendering to ensure environment variables are read at runtime in Cloud Run
export const dynamic = "force-dynamic";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Read environment variables at runtime (server-side)
  // Using bracket notation to help bypass static build-time replacement
  const initialConfig = {
    authMode: process.env["NEXT_PUBLIC_LOOKER_AUTH_MODE"] || process.env["LOOKER_AUTH_MODE"],
    baseUrl: process.env["NEXT_PUBLIC_LOOKER_BASE_URL"] || process.env["LOOKER_BASE_URL"],
    oauthClientId: process.env["NEXT_PUBLIC_LOOKER_OAUTH_CLIENT_ID"] || process.env["LOOKER_OAUTH_CLIENT_ID"],
  };

  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <Providers initialConfig={initialConfig}>
          {children}
        </Providers>
      </body>
    </html>
  );
}
