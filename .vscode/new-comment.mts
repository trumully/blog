import { mkdirSync, writeFileSync } from "fs";
import { join } from "path";

const [postSlug, authorName] = process.argv.slice(2);

if (!postSlug || !authorName) {
  console.error("Usage: node new-comment.mjs <post-slug> <author-name>");
  process.exit(1);
}

const now = new Date();
const ts = Math.floor(now.getTime() / 1000);
const iso = now.toISOString().replace(/\.\d{3}Z$/, "Z");
const slug = authorName.toLowerCase().replace(/\s+/g, "-");

const dir = join("src", "content", "comments", postSlug);
const filepath = join(dir, `${ts}-${slug}.md`);

const content = `---
author: ${authorName}
date: ${iso}
# url: https://example.com  # optional, delete this line if not applicable
---

`;

mkdirSync(dir, { recursive: true });
writeFileSync(filepath, content);
console.log(`Created ${filepath}`);
