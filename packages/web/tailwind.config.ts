import type { Config } from "tailwindcss";

// LITHOS visual spine: clean, scientific, high-trust, slightly editorial. Near-black
// graphite ground, paper light, a single restrained signal accent. Not a template.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          900: "#0b0e12",
          800: "#12161c",
          700: "#1b212a",
          600: "#283039",
          400: "#8a94a0",
          200: "#aab3bd",
        },
        paper: {
          DEFAULT: "#f6f4ef",
          dim: "#e9e6df",
        },
        signal: {
          // Used sparingly for focus and "live" affordances, never for the data ramp.
          DEFAULT: "#e8c547",
        },
        // Diverging data ramp, colourblind-safe (blue uplift -> grey stable -> red sinking).
        motion: {
          rise3: "#2166ac",
          rise2: "#4393c3",
          rise1: "#92c5de",
          stable: "#cfcfcf",
          sink1: "#f4a582",
          sink2: "#d6604d",
          sink3: "#b2182b",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        panel: "0 10px 40px -12px rgba(0,0,0,0.45)",
      },
    },
  },
  plugins: [],
};

export default config;
