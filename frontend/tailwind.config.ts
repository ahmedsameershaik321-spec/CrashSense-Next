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
        canvas: "#f8fafc",
        panel: "#ffffff",
        surface: "#f1f5f9",
        line: "#e2e8f0",
        muted: "#64748b",
        accent: "#2563eb",
        "accent-strong": "#1d4ed8",
      },
      boxShadow: {
        panel: "0 1px 3px rgba(15, 23, 42, 0.06), 0 8px 24px rgba(15, 23, 42, 0.05)",
      },
      backgroundImage: {
        "auth-glow":
          "radial-gradient(ellipse at 18% 0%, rgba(37, 99, 235, .06), transparent 46%), radial-gradient(ellipse at 90% 100%, rgba(14, 116, 144, .04), transparent 42%)",
      },
    },
  },
  plugins: [],
};

export default config;
