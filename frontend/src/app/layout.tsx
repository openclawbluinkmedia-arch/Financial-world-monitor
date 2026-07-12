import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FIOS — Financial Intelligence Operating System",
  description: "Privacy-first B2B financial-intelligence platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900">
        {children}
      </body>
    </html>
  );
}
