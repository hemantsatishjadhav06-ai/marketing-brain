import "./globals.css";
import type { Metadata } from "next";
import { Toaster } from "sonner";

export const metadata: Metadata = {
  title: "Marketing Brain — AI content brain for sports e-commerce",
  description:
    "Multi-agent AI marketing platform: idea generation, calendar planning, brand-safe critique, native publishing, performance learning. Built for racket-sport brands.",
  icons: { icon: "/favicon.svg" },
  openGraph: {
    title: "Marketing Brain",
    description: "AI content brain for sports e-commerce — multi-brand, multi-agent, brand-safe.",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="bg-bg text-ink min-h-screen antialiased">
        {children}
        <Toaster theme="dark" position="top-right" richColors closeButton />
      </body>
    </html>
  );
}
