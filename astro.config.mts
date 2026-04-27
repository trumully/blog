import { defineConfig } from "astro/config";
import type { AstroUserConfig } from "astro";
import sitemap from "@astrojs/sitemap";

const site = "https://truman.mulholland.nz";

// https://astro.build/config
export default defineConfig({
  site: process.env.SITE_URL ?? site,
  integrations: [sitemap()],
  markdown: {
    shikiConfig: {
      themes: {
        light: "catppuccin-latte",
        dark: "catppuccin-mocha",
      },
    },
  },
}) satisfies AstroUserConfig;
