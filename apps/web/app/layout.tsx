import type { Metadata } from "next";
import DeploymentGate from "./deployment-gate";
import "./globals.css";

export const metadata: Metadata = {
  title: "Construction OS India",
  description: "India-first construction project controls, field operations and commercial workflows.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en-IN">
      <body><DeploymentGate>{children}</DeploymentGate></body>
    </html>
  );
}
