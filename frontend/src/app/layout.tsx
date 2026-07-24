import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FIOS — Financial Intelligence Operating System",
  description: "Privacy-first B2B financial-intelligence platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#0a0b10] text-fg">
        {children}
      </body>
    </html>
  );
}
