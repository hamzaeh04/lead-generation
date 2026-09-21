import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        surface2: "var(--surface-2)",
        border: "var(--border)",
        borderStrong: "var(--border-strong)",
        fg: "var(--text)",
        fgMuted: "var(--text-muted)",
        fgSubtle: "var(--text-subtle)",
        accent: "var(--accent)",
        accentSoft: "var(--accent-soft)",
        success: "var(--success)",
        successSoft: "var(--success-soft)",
        warning: "var(--warning)",
        warningSoft: "var(--warning-soft)",
        danger: "var(--danger)",
        dangerSoft: "var(--danger-soft)",
      },
      fontFamily: {
        sans: [
          "var(--font-inter)",
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          '"Helvetica Neue"',
          "Arial",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          '"SF Mono"',
          '"Cascadia Code"',
          '"Roboto Mono"',
          "Consolas",
          "monospace",
        ],
      },
      fontSize: {
        // Named scale for the pixel values already in de facto use across
        // the app, so new components stop hand-picking arbitrary values.
        "2xs": ["10.5px", { lineHeight: "14px" }],
        xs: ["11.5px", { lineHeight: "16px" }],
        sm: ["12.5px", { lineHeight: "18px" }],
        base: ["13px", { lineHeight: "20px" }],
        md: ["14px", { lineHeight: "21px" }],
        lg: ["16px", { lineHeight: "24px" }],
        xl: ["18px", { lineHeight: "26px" }],
        "2xl": ["22px", { lineHeight: "28px" }],
        "3xl": ["28px", { lineHeight: "34px" }],
        "4xl": ["34px", { lineHeight: "40px" }],
      },
      borderRadius: {
        lg: "10px",
        xl: "14px",
        "2xl": "18px",
      },
      boxShadow: {
        card: "var(--shadow)",
        popover: "var(--shadow-lg)",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "slide-in-from-top": {
          from: { opacity: "0", transform: "translateY(-4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 120ms ease-out",
        "slide-in-from-top": "slide-in-from-top 120ms ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
