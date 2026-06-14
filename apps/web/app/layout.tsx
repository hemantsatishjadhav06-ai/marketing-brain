import "./globals.css";
import type { Metadata } from "next";
import { Toaster } from "sonner";
import { ThemeProvider } from "@/lib/theme/ThemeProvider";

export const metadata: Metadata = {
  title: "Marketing Dog — the marketing brain that fetches, decides & ships",
  description:
    "Point Marketing Dog at your website. It learns your brand, skins itself in your colours, then plans, writes, critiques and publishes on-brand content & video across every channel.",
  icons: { icon: "/favicon.svg" },
  openGraph: {
    title: "Marketing Dog",
    description: "An autonomous marketing brain — brand-adaptive, brand-safe, always on.",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-mode="dark" suppressHydrationWarning>
      <body className="bg-bg text-ink min-h-screen antialiased">
        {/* keyboard users land here first */}
        <a href="#main" className="skip-link">Skip to content</a>
        <ThemeProvider initialBrand={{ primary: "#CCFF00" }} initialMode="dark">
          <div id="main">{children}</div>
        </ThemeProvider>
        <Toaster theme="dark" position="top-right" richColors closeButton />
      </body>
    </html>
  );
}
