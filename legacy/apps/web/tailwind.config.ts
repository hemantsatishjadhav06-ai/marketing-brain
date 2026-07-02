import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        bg2: "var(--bg-2)",
        panel: "var(--panel)",
        panel2: "var(--panel-2)",
        panel3: "var(--panel-3)",
        line: "var(--line)",
        line2: "var(--line-2)",
        ink: "var(--ink)",
        ink2: "var(--ink-2)",
        mute: "var(--mute)",
        // sport accents (per-brand) — UI shouldn't mix them on the same view
        tennis: "#CCFF00",
        padel: "#22D3EE",
        pickleball: "#F59E0B",
        badminton: "#A78BFA",
        squash: "#EF4444",
        accent: "var(--accent)",
        accentInk: "var(--accent-ink)",
        good: "var(--good)",
        warn: "var(--warn)",
        danger: "var(--danger)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
        serif: ["Fraunces", "ui-serif", "Georgia", "serif"],
      },
      borderRadius: {
        DEFAULT: "var(--radius)",
        sm: "var(--radius-sm)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
      },
      boxShadow: {
        soft: "0 8px 24px rgba(0,0,0,0.45)",
        glow: "0 0 0 1px color-mix(in srgb, var(--accent) 35%, transparent), 0 8px 32px color-mix(in srgb, var(--accent) 22%, transparent)",
      },
    },
  },
} satisfies Config;
