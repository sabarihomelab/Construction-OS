import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Construction OS India",
  description: "India-first construction project controls, field operations and commercial workflows.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en-IN">
      <body>{children}</body>
    </html>
  );
}
