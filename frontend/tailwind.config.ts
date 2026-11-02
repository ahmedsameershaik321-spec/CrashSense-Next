import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: "#080e18",
        panel: "#0d1624",
        surface: "#111d2d",
        line: "#1d2b3d",
        muted: "#8392a7",
        accent: "#48a9ff",
        "accent-strong": "#1687e8",
      },
      boxShadow: {
        panel: "0 20px 60px rgba(0, 0, 0, 0.24)",
      },
      backgroundImage: {
        "auth-glow":
          "radial-gradient(ellipse at 18% 0%, rgba(32, 111, 187, .22), transparent 46%), radial-gradient(ellipse at 90% 100%, rgba(21, 79, 132, .15), transparent 42%)",
      },
    },
  },
  plugins: [],
};

export default config;
