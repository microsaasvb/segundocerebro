import type { Config } from 'tailwindcss';

export default {
  content: [
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
    './src/layouts/**/*.{js,ts,jsx,tsx,mdx}'
  ],
  theme: {
    extend: {
      colors: {
        background: 'var(--background)',
        foreground: 'var(--foreground)',
        brand: {
          deep: '#1A0B3C',     // roxo profundo
          accent: '#7A1FE0',   // roxo accent
          neon: '#00FF94',     // verde-neon
          pink: '#FF3DA0',     // pink sinapse
          white: '#FFFFFF'
        },
        secondme: {
          'warm-bg': '#FDF8F3',
          blue: '#7A1FE0',
          green: '#00FF94',
          red: '#FF3DA0',
          yellow: '#FFD93D',
          navy: '#1A0B3C',
          gray: {
            100: '#F7F9FA',
            200: '#E9ECEF',
            300: '#DEE2E6',
            400: '#CED4DA',
            500: '#ADB5BD',
            600: '#6C757D',
            700: '#495057',
            800: '#343A40',
            900: '#212529'
          }
        }
      }
    }
  },
  plugins: []
} satisfies Config;
