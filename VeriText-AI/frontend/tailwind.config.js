/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          50: '#f4f7fb',
          100: '#e6edf5',
          200: '#c8d7e8',
          300: '#9bb4d2',
          400: '#6789b3',
          500: '#476a96',
          600: '#35527a',
          700: '#2a4263',
          800: '#1b3050',
          900: '#0f2540',
          950: '#0a1929',
        },
        accent: {
          50: '#eff5ff',
          100: '#dbe8fe',
          200: '#bed7fe',
          300: '#92bdfd',
          400: '#5f9afa',
          500: '#2563eb',
          600: '#1d4ed8',
          700: '#1e40af',
        },
        signal: {
          low: '#15803d',
          moderate: '#b45309',
          high: '#b91c1c',
        },
      },
      fontFamily: {
        sans: [
          'Inter var', 'Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI',
          'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif',
        ],
        serif: ['Iowan Old Style', 'Palatino Linotype', 'Georgia', 'serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(15, 37, 64, 0.06), 0 1px 3px rgba(15, 37, 64, 0.04)',
        raised: '0 4px 12px rgba(15, 37, 64, 0.08), 0 1px 3px rgba(15, 37, 64, 0.05)',
        pop: '0 12px 32px rgba(15, 37, 64, 0.14)',
      },
      borderRadius: {
        card: '0.75rem',
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-500px 0' },
          '100%': { backgroundPosition: '500px 0' },
        },
      },
      animation: {
        'fade-up': 'fade-up 220ms ease-out both',
        shimmer: 'shimmer 1.4s linear infinite',
      },
    },
  },
  plugins: [],
}
