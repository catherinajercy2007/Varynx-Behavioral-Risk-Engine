import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Varynx — Behavioral Risk Control Engine",
  description: "Analyst dashboard for the Varynx Behavioral Risk Control Engine",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50">
        <nav className="bg-varynx-blue text-white px-6 py-4 flex items-center gap-8">
          <span className="font-bold text-xl">Varynx</span>
          <a href="/" className="hover:underline">Overview</a>
          <a href="/agents" className="hover:underline">Agents</a>
          <a href="/audit" className="hover:underline">Audit</a>
          <a href="/evaluation" className="hover:underline">Evaluation</a>
          <a href="/bcse" className="hover:underline">BCSE</a>
        </nav>
        <main className="p-6">{children}</main>
      </body>
    </html>
  );
}