import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        // Real CB-IELTS uses Arial; sans fallback keeps it readable on any system.
        exam: ["Arial", "Helvetica", "sans-serif"],
      },
      colors: {
        exam: {
          bg: "#ffffff",
          border: "#cccccc",
          text: "#222222",
          accent: "#0a5c8a", // sober navy used for nav buttons
          warn: "#b03030",
          highlight: "#fff59d",
        },
      },
    },
  },
  plugins: [],
};
export default config;
