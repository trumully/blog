# Signature artwork and Blender studies

## 1. Create a post (normal path)

```sh
node .vscode/new-post.mts <post-slug>
```

That's all: normal posts automatically reuse a registered signature and its matching social-preview image. No Blender run, image generation, or artwork decision is needed. The canonical post path selects a shared composition in [src/utils/signature-selection.ts](../../src/utils/signature-selection.ts); [src/components/SignatureArt.astro](../../src/components/SignatureArt.astro) uses its Latte/Mocha pair, and [src/layouts/MarkdownPostLayout.astro](../../src/layouts/MarkdownPostLayout.astro) uses the matching preview. Posts do not get unique artwork, and their titles, bodies, and tags do not affect selection.

## 2. Optionally render a candidate

For an existing post only, generate an offline candidate pair with:

```sh
uv run tools/signatures/generate.py <existing-post-slug> --background transparent
```

A real render requires Blender. Preview quality is the default; the command prints the output directory containing `latte.png` and `mocha.png`. Inspect both as a pair. Use `--quality final` only when a preview merits a final render. This creates a study candidate, not website artwork: the generator's workspace registry assigns an offline study family only; it does not register, install, or select site art.

## 3. Deliberately publish approved artwork

A Blender study family is separate from a website composition ID. Choose and approve the site artwork, ID, accent colors, and any post pin deliberately; promotion is manual.

1. Copy the reviewed transparent RGBA pair (no theme-colored matte) to [src/assets/signatures/](../../src/assets/signatures/) as `<id>/latte.png` and `<id>/mocha.png`.
2. Add the ID to `SIGNATURE_COMPOSITIONS` and its Latte/Mocha colors to `SIGNATURE_ACCENTS` in [src/utils/signature-selection.ts](../../src/utils/signature-selection.ts). Add a `PINNED_COMPOSITIONS` entry keyed by the canonical path `/posts/<post-slug>/` only when that post should keep this composition. Unpinned posts are selected automatically; adding an ID can reassign some of them, while pins remain stable.
3. Import both PNGs and add the same ID to `masterPairs` in [src/components/SignatureArt.astro](../../src/components/SignatureArt.astro). Keep the asset folder, imports, pair, composition ID, and accent palette aligned.
4. After adding the source PNGs, run the manual preview generator:

   ```sh
   node tools/social/generate-previews.mjs
   ```

   It reads each composition's transparent `mocha.png` and writes `public/social/<id>.jpg`; it is not run by the site build and requires project dependencies including `sharp`. Review and commit the resulting JPEG with the PNGs and registration changes.

5. Validate with the project check (dependencies installed and Astro synced):

   ```sh
   uv run build.py --skip-install --check
   ```

   Check `dist/posts/<post-slug>/index.html` points `og:image` and `twitter:image` to the intended `/social/<id>.jpg`, and confirm `dist/social/<id>.jpg` exists.

## Advanced

See `uv run tools/signatures/generate.py --help` for options. Use `--variation N` for a reproducible alternate, `--quality final` for final rendering, and `--workspace <path>` or `SIGNATURE_WORKSPACE` to choose an isolated workspace outside the repository. `--dry-run` prints paths and the Blender command without writing files or launching Blender; use that command for direct replay (`--job` requires an absolute path). `--overwrite` is opt-in and limited to matching generated outputs; unrelated files are preserved. `--blender PATH` and `--timeout SECONDS` adjust Blender execution.
