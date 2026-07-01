import { existsSync, mkdirSync, writeFileSync } from "fs";
import { join } from "path";

const [postSlug, authorName, replyTo] = process.argv.slice(2);

if (!postSlug || !authorName) {
  console.error("Usage: node new-comment.mjs <post-slug> <author-name> [reply-to-filename]");
  process.exit(1);
}

if (replyTo) {
  const parentPath = join("src", "content", "comments", postSlug, `${replyTo}.md`);
  if (!existsSync(parentPath)) {
    console.error(`Error: parent comment not found: ${parentPath}`);
    process.exit(1);
  }
}

const now = new Date();
const ts = Math.floor(now.getTime() / 1000);
const iso = now.toISOString().replace(/\.\d{3}Z$/, "Z");
const slug = authorName.toLowerCase().replace(/\s+/g, "-");

const dir = join("src", "content", "comments", postSlug);
const filepath = join(dir, `${ts}-${slug}.md`);

const replyToField = replyTo ? `\nreplyTo: ${replyTo}` : "";
const content = `---
author: ${authorName}
date: ${iso}
# url: https://example.com  # optional, delete this line if not applicable${replyToField}
---

`;

mkdirSync(dir, { recursive: true });
writeFileSync(filepath, content);
console.log(`Created ${filepath}`);
