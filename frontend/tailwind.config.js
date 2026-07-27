export default {
  darkMode: "class",
  content: [
    "./{routes,islands,components,utils}/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        "brand-red": {
          DEFAULT: "#ED3237",
          50: "#fcf1f2",
          100: "#fbdfe0",
          200: "#f9bcbe",
          300: "#f6a2a4",
          800: "#b12529",
          900: "#821b1e",
        },
        "brand-green": {
          DEFAULT: "#00A859",
          dark: "#008647",
        },
        "brand-white": "#FEFEFE",
      },
    },
  },
};
