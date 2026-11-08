/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "varynx-blue": "#1d4ed8",
        "trust-high": "#16a34a",
        "trust-elevated": "#65a30d",
        "trust-guarded": "#d97706",
        "trust-low": "#dc2626",
        "trust-critical": "#7f1d1d",
      },
    },
  },
  plugins: [],
};