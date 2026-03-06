import { defineConfig } from "astro/config";
import type { AstroUserConfig } from "astro";
import sitemap from "@astrojs/sitemap";

const site = "https://trumully.netlify.app";

// https://astro.build/config
export default defineConfig({
  site: process.env.SITE_URL ?? site,
  integrations: [sitemap()],
}) satisfies AstroUserConfig;
