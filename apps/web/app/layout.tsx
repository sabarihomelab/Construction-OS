import type { Metadata } from "next";
import type { ReactNode } from "react";
import DeploymentGate from "./deployment-gate";
import WebSessionGate from "./web-session-gate";
import "./globals.css";

export const metadata: Metadata = {
  title: "Construction OS India",
  description: "India-first construction project operating platform",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en-IN">
      <body>
        <DeploymentGate>
          <WebSessionGate>{children}</WebSessionGate>
        </DeploymentGate>
      </body>
    </html>
  );
}
