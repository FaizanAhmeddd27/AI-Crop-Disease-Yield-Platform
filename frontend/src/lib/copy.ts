export const copy = {
  en: {
    disclaimer: {
      title: "Decision support only.",
      body: "Confirm with a local agronomist before applying any treatment.",
    },
    navigation: {
      aboutModels: "About the models",
      weatherData: "Weather data",
    },
  },
} as const;

export type Locale = keyof typeof copy;
