import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brick: {
          red: "#C91A09",
          blue: "#0051A8",
          yellow: "#F5CD2F",
          green: "#237841",
          black: "#1B2A34",
          white: "#FFFFFF",
          gray: "#A0A5A9",
          orange: "#FE8A18",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
