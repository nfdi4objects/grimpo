import gbv from "eslint-config-gbv"

export default [
  ...gbv,
  {
    languageOptions: {
      globals: { Vue: "readable" },
    },
  },
]
