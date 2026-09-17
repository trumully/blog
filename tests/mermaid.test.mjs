import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { runInNewContext } from "node:vm";
import test from "node:test";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const postId = "mermaid-test-fixture-25";
const postPath = resolve(root, "src/blog", `${postId}.md`);
const commentDirectory = resolve(root, "src/content/comments", postId);
const commentPath = resolve(commentDirectory, "comment.md");

const post = `---
title: Mermaid test fixture
date: 2026-09-17
tags: [testing]
---

A rendered diagram:

\`\`\`mermaid
flowchart TD
  Start --> Finish
\`\`\`

The source:

\`\`\`mermaid source
flowchart TD
  Start --> Finish
\`\`\`

An existing code block:

\`\`\`csharp
var answer = 42;
\`\`\`
`;

const comment = `---
author: Mermaid test
date: 2026-09-17T00:00:00Z
---

\`\`\`mermaid
flowchart TD
  CommentStart --> CommentFinish
\`\`\`
`;

function runBuild() {
  return spawnSync("npm run build", {
    cwd: root,
    encoding: "utf8",
    shell: true,
    env: { ...process.env, NODE_OPTIONS: "--max_old_space_size=10000" },
  });
}

test("renders blog Mermaid fences without changing comments", async () => {
  try {
    await mkdir(commentDirectory, { recursive: true });
    await writeFile(postPath, post);
    await writeFile(commentPath, comment);

    const result = runBuild();
    assert.equal(result.status, 0, `${result.error?.message ?? ""}\n${result.stdout}\n${result.stderr}`);

    const html = await readFile(resolve(root, "dist/posts", postId, "index.html"), "utf8");
    const mermaidBlocks = html.match(/<pre class="mermaid">/g) ?? [];
    assert.equal(mermaidBlocks.length, 1, "only the blog diagram should become a Mermaid block");
    assert.match(html, /data-language="mermaid"/, "Mermaid source should remain a highlighted code block");
    assert.match(html, /data-language="csharp"/, "existing code highlighting should remain enabled");
    const themeStart = html.indexOf("  const theme =");
    const themeEnd = html.indexOf("</script>", themeStart);
    assert.notEqual(themeStart, -1, "the theme script should render");
    assert.notEqual(themeEnd, -1, "the theme script should be complete");
    const classes = new Set();
    const themeStorage = {
      getItem: () => "light",
      setItem: () => {},
    };
    const documentElement = {
      dataset: {},
      classList: {
        toggle: (name, force) => (force ? classes.add(name) : classes.delete(name)),
        contains: (name) => classes.has(name),
      },
    };
    let toggleTheme;
    runInNewContext(html.slice(themeStart, themeEnd), {
      document: {
        documentElement,
        getElementById: () => ({ addEventListener: (_event, handler) => (toggleTheme = handler) }),
      },
      localStorage: themeStorage,
      window: { localStorage: themeStorage, matchMedia: () => ({ matches: false }) },
    });
    assert.equal(documentElement.dataset.theme, "light");
    assert.equal(classes.has("dark"), false);
    toggleTheme();
    assert.equal(documentElement.dataset.theme, "dark");
    assert.equal(classes.has("dark"), true);
    assert.match(html, /dataset\.theme/, "the theme state should be exposed to Mermaid");

    const commentStart = html.indexOf('<div class="comment-body"');
    const commentEnd = html.indexOf('<div class="comment-footer"', commentStart);
    assert.notEqual(commentStart, -1, "the fixture comment should render");
    assert.notEqual(commentEnd, -1, "the fixture comment footer should render");
    const commentBody = html.slice(commentStart, commentEnd);
    assert.doesNotMatch(commentBody, /<pre class="mermaid">/, "comments must not render Mermaid diagrams");
    assert.match(commentBody, /data-language="mermaid"/, "comment Mermaid fences must remain code");

    const readme = await readFile(resolve(root, "README.md"), "utf8");
    assert.match(readme, /```mermaid\s/, "README should document Mermaid diagram fences");
    assert.match(readme, /```mermaid source\s/, "README should document Mermaid source fences");
  } finally {
    await Promise.all([rm(postPath, { force: true }), rm(commentDirectory, { recursive: true, force: true })]);
  }
});
