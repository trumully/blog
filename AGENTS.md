# Agent guidance

Read [ARCHITECTURE.md](ARCHITECTURE.md) before changing content flow, rendering, or site structure. Follow [CONVENTIONS.md](CONVENTIONS.md) for shared naming, formatting, error-handling, and content conventions.

## Content creation

Use the scaffolding scripts rather than creating posts or comments manually; they generate the expected paths, timestamps, and starter frontmatter:

```sh
node .vscode/new-post.mts <post-slug>
node .vscode/new-comment.mts <post-slug> "<author-name>"
```

The **New Post** and **New Comment** VS Code tasks are also available. See [src/content.config.ts](src/content.config.ts) for the authoritative content schemas. New posts automatically reuse the registered signature and matching preview—no rendering is needed; for approved artwork changes, see [tools/signatures/README.md](tools/signatures/README.md).

## Checks

Use `build.py` for checks and fixes:

```sh
uv run build.py --check
uv run build.py --skip-install --check
uv run build.py --fix
uv run build.py --skip-install --fix
```

`--check` runs typecheck, lint, formatting checks, and the static build. Run it after `--fix`. Use `--skip-install` only when dependencies are installed and Astro has already been synced.
