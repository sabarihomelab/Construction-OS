import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Construction OS",
  description: "Field, project and financial operations in one construction platform.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
