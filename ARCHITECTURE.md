# Architecture

An [Astro](https://astro.build) blog site using minimal template.

- `src/pages/` — File-based routing. `.astro`, `.md`, and `.js` files become routes. Includes `posts/`, `tags/` subdirs and `rss.xml.js` endpoint.
- `src/components/` — Astro components: `BlogPost.astro`, `Comment.astro`, `Comments.astro`, `Footer.astro`, `Header.astro`, `Navigation.astro`, `Social.astro`, `ThemeIcon.astro`.
- `src/layouts/` — Page layouts: `BaseLayout.astro`, `MarkdownPostLayout.astro`.
- `src/blog/` — Markdown blog post content files.
- `src/content/comments/` — Markdown comment files. Organized as `src/content/comments/<postSlug>/<unixTimestamp>-<authorSlug>.md`.
- `src/styles/` — Global CSS (`global.css`).
- `src/assets/` — Static assets imported by components.
- `src/utils/` — Utility functions (e.g. `date.ts`).
- `src/content.config.ts` — Content collection schema for the blog.
- `public/` — Static assets served at root (e.g. `public/favicon.svg` → `/favicon.svg`).
- `astro.config.mts` — Astro configuration.

Astro pages use a frontmatter fence (`---`) at the top for server-side JavaScript, followed by HTML/component markup. TypeScript is configured in strict mode via `astro/tsconfigs/strict`.
