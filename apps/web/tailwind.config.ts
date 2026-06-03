import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#08080A",
        panel: "#0F0F12",
        panel2: "#14141A",
        line: "#1F1F26",
        ink: "#F5F5F7",
        mute: "#8A8A93",
        // sport accents (per-brand) — UI shouldn't mix them on the same view
        tennis: "#CCFF00",
        padel: "#22D3EE",
        pickleball: "#F59E0B",
        badminton: "#A78BFA",
        squash: "#EF4444",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
        serif: ["Instrument Serif", "ui-serif", "Georgia", "serif"],
      },
    },
  },
} satisfies Config;
