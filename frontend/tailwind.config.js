/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        slate: {
          950: '#070b14',
          900: '#0f172a',
          850: '#131d35',
          800: '#1e293b',
          700: '#334155',
        }
      }
    },
  },
  plugins: [],
}
