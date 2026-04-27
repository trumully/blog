See [ARCHITECTURE.md](ARCHITECTURE.md) to understand the project. See [CONVENTIONS.md](CONVENTIONS.md) for naming, formatting, and other conventions.

Oxfmt used for JS/TS code formatting. Oxfmt + Prettier used for Astro code formatting.

## Content creation

Use these scripts (not manual file creation) — they set correct paths, timestamps, and frontmatter:

```sh
node .vscode/new-post.mts <post-slug>        # creates src/blog/<slug>.md
node .vscode/new-comment.mts <post-slug> <author-name>  # creates src/content/comments/<postSlug>/<ts>-<authorSlug>.md
```

Also available as VS Code tasks: **New Post** / **New Comment** (prompts for inputs).

## Deployment & CI

- Hosted on GitHub Pages at `https://truman.mulholland.nz`
- CI runs lint + build on every push and PR
- Merges to `main` deploy to production

## Commands

Use `build.py` for orchestrated workflows (installs deps, sets env vars, runs steps in order):

```sh
uv run -s build.py --check               # Full CI check: typecheck + lint + fmt + build
uv run -s build.py --lint                # Typecheck + lint + fmt check only
uv run -s build.py --build               # Build only
uv run -s build.py --fix                 # Auto-fix lint and formatting
uv run -s build.py --skip-install <...>  # Skip npm install (use when deps already installed)
```

Individual npm commands for targeted tasks:

```sh
npm run dev          # Start dev server at localhost:4321
npm run build        # Build production site to ./dist/
npm run preview      # Preview production build locally
npm run astro ...    # Run Astro CLI commands (e.g. astro add, astro check)
npm run typecheck    # Run TypeScript type checking
npm run lint         # Run oxlint
npm run lint:fix     # Auto-fix oxlint issues
npm run fmt:check    # Check formatting
npm run fmt          # Auto-fix formatting
```
