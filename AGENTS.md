# AGENTS.md

This file provides guidance to AI agents working with code in this repository.

## Commands

```sh
npm run dev          # Start dev server at localhost:4321
npm run build        # Build production site to ./dist/
npm run preview      # Preview production build locally
npm run astro ...    # Run Astro CLI commands (e.g. astro add, astro check)
npm run lint         # Run ESLint
npm run lint:fix     # Auto-fix ESLint issues
npm run prettier     # Check formatting
npm run prettier:fix # Auto-fix formatting
```

## Architecture

This is an [Astro](https://astro.build) blog site using the minimal template with strict TypeScript.

- `src/pages/` — File-based routing. `.astro` and `.md` files become routes based on filename.
- `src/components/` — Astro components: `BlogPost.astro`, `Footer.astro`, `Header.astro`, `Navigation.astro`, `Social.astro`, `ThemeIcon.astro`.
- `src/layouts/` — Page layouts: `BaseLayout.astro`, `MarkdownPostLayout.astro`.
- `src/blog/` — Markdown blog post content files.
- `src/styles/` — Global CSS (`global.css`).
- `src/assets/` — Static assets imported by components.
- `src/utils/` — Utility functions (e.g. `date.ts`).
- `src/content.config.ts` — Content collection schema for the blog.
- `public/` — Static assets served at root (e.g. `public/favicon.svg` → `/favicon.svg`).
- `astro.config.mts` — Astro configuration.

Astro pages use a frontmatter fence (`---`) at the top for server-side JavaScript, followed by HTML/component markup. TypeScript is configured in strict mode via `astro/tsconfigs/strict`.

## Tooling

- **ESLint** — `eslint-plugin-astro`, `typescript-eslint` (strictTypeChecked), `eslint-config-prettier`
- **Prettier** — `prettier-plugin-astro`, 120-character print width
- **TypeScript** — strict mode via `astro/tsconfigs/strict`

## Deployment & CI

- Hosted on Netlify at `https://trumully.netlify.app`
- CI runs lint + build on every push and PR
- Merges to `main` deploy to production; PRs get a deploy preview
