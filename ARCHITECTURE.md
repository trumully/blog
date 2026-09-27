# Architecture

This is a static Astro blog: Markdown collections feed file-based routes and the production build writes the site to `dist/`.

## Content and rendering

- [src/content.config.ts](src/content.config.ts) defines the Markdown loaders and authoritative schemas. Posts live in `src/blog/`; comments live under `src/content/comments/<post-slug>/`.
- `src/pages/[...page].astro` builds the paginated writing feed; `src/pages/posts/[...slug].astro` generates post pages. Other routes provide tags, archive, about, 404, and RSS.
- `src/layouts/` and `src/components/` provide shared page/article rendering. `MarkdownPostLayout.astro` joins post content with metadata, Git history, comments, and signature art; `Comments.astro` associates nested comment entries with their post. `src/utils/` holds supporting helpers and `src/styles/global.css` supplies global styling.

## Signature artwork

Production PNGs are in `src/assets/signatures/` and are imported and optimized by `src/components/SignatureArt.astro`; `src/utils/signature-selection.ts` pins canonical post identities and deterministically selects among shared compositions. The selected composition also determines each post's shared `public/social/<id>.jpg` preview. `tools/signatures/` is an offline Blender study generator, not part of the site runtime or build; its workspace registry is separate from website selection, and output is not installed or published automatically. See [the signature and preview workflow](tools/signatures/README.md) for authoring and integration details.

## Build and deployment

Astro configuration is in `astro.config.mts` (default site URL `https://truman.mulholland.nz`, overridable with `SITE_URL`). [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs `uv run build.py --check` on pull requests and pushes to `main`; a push to `main` publishes the `dist/` artifact to GitHub Pages.
