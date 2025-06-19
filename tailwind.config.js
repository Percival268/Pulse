/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class', // ✅ critical
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {},
  },
  plugins: [require('@tailwindcss/line-clamp')],
};
