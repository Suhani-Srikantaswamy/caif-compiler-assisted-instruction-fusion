import colors from 'tailwindcss/colors'

/*
 * Dark theme by palette inversion.
 *
 * The components are written with ordinary "light" utility classes
 * (bg-slate-50 page, bg-slate-100 cards, text-slate-800 text, bg-blue-100 chips...).
 * Here every colour scale is flipped (50 <-> 950, 100 <-> 900, ...), so those
 * same classes render as a consistent dark theme: light tints become dark
 * surfaces and dark inks become light text. Shade 500 stays put.
 *
 * Slate (the neutral) is flipped with a +1 shift in the middle so secondary text
 * (slate-500/600) stays readable on the dark surface.
 */
const invert = (scale) => ({
  50: scale[950], 100: scale[900], 200: scale[800], 300: scale[700], 400: scale[600],
  500: scale[500], 600: scale[400], 700: scale[300], 800: scale[200], 900: scale[100], 950: scale[50],
})

const s = colors.slate
const darkSlate = {
  50: s[950],   // page background
  100: s[900],  // cards, panels
  200: s[800],  // borders, dividers
  300: s[700],  // input borders
  400: s[500],  // faint text
  500: s[400],  // secondary text
  600: s[300],  // body text
  700: s[200],
  800: s[100],
  900: s[50],   // headings
  950: s[50],
}

const families = ['blue', 'violet', 'amber', 'cyan', 'red', 'emerald', 'indigo', 'orange', 'green', 'yellow']

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      white: colors.white,
      black: colors.black,
      slate: darkSlate,
      ...Object.fromEntries(families.map((f) => [f, invert(colors[f])])),
    },
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
}
