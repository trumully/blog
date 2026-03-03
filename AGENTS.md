# AGENTS.md

This file provides guidance to AI agents working with code in this repository.

## Commands

```sh
npm run dev       # Start dev server at localhost:4321
npm run build     # Build production site to ./dist/
npm run preview   # Preview production build locally
npm run astro ... # Run Astro CLI commands (e.g. astro add, astro check)
```

## Architecture

This is an [Astro](https://astro.build) blog site using the minimal template with strict TypeScript.

- `src/pages/` — File-based routing. `.astro` and `.md` files become routes based on filename.
- `src/components/` — Astro/framework components (directory doesn't exist yet but is the conventional location).
- `public/` — Static assets served at root (e.g. `public/favicon.svg` → `/favicon.svg`).
- `astro.config.mjs` — Astro configuration.

Astro pages use a frontmatter fence (`---`) at the top for server-side JavaScript, followed by HTML/component markup. TypeScript is configured in strict mode via `astro/tsconfigs/strict`.
