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
        {/* Dynatrace Real User Monitoring — Change this Script following the instructions in the README */}
        <Script
          src="https://js-cdn.dynatrace.com/jstag/<follow-the-instructions-in-the-README>.js"
          strategy="afterInteractive"
          crossOrigin="anonymous"
        />
      </body>
    </html>
  );
}
