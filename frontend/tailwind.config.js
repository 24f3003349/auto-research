/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0b1020",
        panel: "#121a31",
        accent: "#7dd3fc",
        ok: "#86efac",
        warn: "#fde68a",
        bad: "#fca5a5",
      },
    },
  },
  plugins: [],
};
