/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        ink: '#0f172a',
        primary: '#3730a3',
        'primary-dark': '#2e2a8a',
        accent: '#6366f1',
        slate: '#f1f5f9',
        border: '#e2e8f0',
        muted: '#64748b',
        body: '#334155',
        high: '#15803d',
        'high-bg': '#ecfdf5',
        mod: '#b45309',
        'mod-bg': '#fffbeb',
        low: '#b91c1c',
        'low-bg': '#fef2f2',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgb(0 0 0 / 0.08), 0 1px 2px -1px rgb(0 0 0 / 0.06)',
        'card-hover': '0 10px 15px -3px rgb(0 0 0 / 0.06), 0 4px 6px -4px rgb(0 0 0 / 0.06)',
      },
      borderRadius: {
        card: '10px',
        btn: '8px',
      },
    },
  },
  plugins: [],
}
