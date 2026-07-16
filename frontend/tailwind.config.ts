import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#0f1117",
          alt: "#1a1d27",
          card: "#1e2130",
          hover: "#252836",
          border: "#2e3140",
          "border-light": "#383b4a",
        },
        fg: {
          DEFAULT: "#e2e4e9",
          muted: "#b0b3bc",
          dim: "#6b7080",
          faint: "#4a4e5a",
        },
        accent: {
          green: { DEFAULT: "#22c55e", bg: "#052e16", border: "#166534" },
          red: { DEFAULT: "#ef4444", bg: "#1f0a0a", border: "#991b1b" },
          amber: { DEFAULT: "#f59e0b", bg: "#1c1400", border: "#92400e" },
          blue: { DEFAULT: "#3b82f6", bg: "#0a1a3a", border: "#1d4ed8" },
          purple: { DEFAULT: "#a78bfa", bg: "#1a0e3a", border: "#7c3aed" },
          cyan: { DEFAULT: "#22d3ee", bg: "#042f3a", border: "#0891b2" },
        },
        signal: {
          positive: "#22c55e",
          negative: "#ef4444",
          uncertain: "#f59e0b",
          neutral: "#6b7080",
        },
      },
      fontFamily: {
        mono: ["'JetBrains Mono'", "'Fira Code'", "monospace"],
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
      },
      fontSize: {
        "2xs": ["0.625rem", { lineHeight: "0.875rem" }],
      },
      boxShadow: {
        card: "0 1px 3px 0 rgba(0,0,0,0.4), 0 1px 2px -1px rgba(0,0,0,0.3)",
        "card-hover": "0 4px 6px -1px rgba(0,0,0,0.5), 0 2px 4px -2px rgba(0,0,0,0.4)",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
    },
  },
  plugins: [],
};

export default config;
