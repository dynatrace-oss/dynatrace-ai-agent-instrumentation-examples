import type { Metadata } from "next";
import Script from "next/script";
import "./globals.css";

export const metadata: Metadata = {
  title: "Music History Explorer — RUM",
  description: "AI music agent with Dynatrace Real User Monitoring",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        {children}
        {/* Dynatrace Real User Monitoring — pydantic-music-app (APPLICATION-B52D32BDE3935DE1)
            afterInteractive is the correct App Router strategy for third-party analytics.
            It loads immediately after hydration, before any user action can fire a fetch,
            so every request still gets the W3C traceparent header injected automatically. */}
        <Script
          src="https://js-cdn.dynatracelabs.com/jstag/1468ae7109d/bf48777rib/b52d32bde3935de1_complete.js"
          strategy="afterInteractive"
          crossOrigin="anonymous"
        />
      </body>
    </html>
  );
}
