import { writeFileSync } from "fs";
import { join } from "path";

const [slug] = process.argv.slice(2);

if (!slug) {
  console.error("Usage: node new-post.mjs <post-slug>");
  process.exit(1);
}

const now = new Date();
const date = now.toISOString().replace(/\.\d{3}Z$/, "Z");

const filepath = join("src", "blog", `${slug}.md`);

const content = `---
title:
date: ${date}
description:
tags: []
---
`;

writeFileSync(filepath, content);
console.log(`Created ${filepath}`);
