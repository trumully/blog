import { defineConfig } from "astro/config";
import type { AstroUserConfig } from "astro";
import sitemap from "@astrojs/sitemap";

// https://astro.build/config
export default defineConfig({
  site: process.env.SITE_URL ?? "https://your-site.netlify.app",
  integrations: [sitemap()],
}) satisfies AstroUserConfig;
