import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#0B1120",
          50: "#EDEFF3",
          200: "#C7CDDA",
          300: "#8993A8",
          400: "#5C647A",
        },
        surface: "#121A2B",
        surface2: "#182238",
        border: {
          DEFAULT: "#232C40",
          light: "#2E3A54",
        },
        brass: {
          DEFAULT: "#B8923A",
          bright: "#D4AF5A",
          dim: "#8A6D2C",
        },
        allowed: { DEFAULT: "#2BA793", dim: "#1B4F47" },
        escalated: { DEFAULT: "#E0A030", dim: "#5C4319" },
        blocked: { DEFAULT: "#C44536", dim: "#4F211B" },
      },
      fontFamily: {
        display: ["var(--font-fraunces)", "serif"],
        sans: ["var(--font-plex-sans)", "sans-serif"],
        mono: ["var(--font-plex-mono)", "monospace"],
      },
      backgroundImage: {
        "grain": "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.035'/%3E%3C/svg%3E\")",
      },
    },
  },
  plugins: [],
};

export default config;
