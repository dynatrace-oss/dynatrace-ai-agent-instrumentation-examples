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
        {/* Dynatrace Real User Monitoring — set NEXT_PUBLIC_DT_RUM_SCRIPT to your JS tag URL */}
        {process.env.NEXT_PUBLIC_DT_RUM_SCRIPT && (
          <Script
            src={process.env.NEXT_PUBLIC_DT_RUM_SCRIPT}
            strategy="afterInteractive"
            crossOrigin="anonymous"
          />
        )}
      </body>
    </html>
  );
}
