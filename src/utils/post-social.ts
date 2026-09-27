import { createHash } from "node:crypto";
import type { CollectionEntry } from "astro:content";
import { selectSignatureAccent, selectSignatureComposition } from "./signature-selection.ts";
import { markdownExcerpt } from "./summary.ts";
import { postPath } from "./urls.ts";

export function postSocialCard(post: CollectionEntry<"blog">) {
  const title = post.data.title;
  const description = post.data.description?.trim() || markdownExcerpt(post.body ?? "", 180);
  const path = postPath(post.id);
  const composition = selectSignatureComposition(path);
  const accent = selectSignatureAccent(path).mocha;
  // Change the version when the card design changes; edits to copy get a new URL automatically.
  const revision = createHash("sha256")
    .update(JSON.stringify([1, title, description, composition, accent]))
    .digest("hex")
    .slice(0, 12);
  const imageId = `${post.id}/${revision}`;

  return {
    title,
    description,
    composition,
    accent,
    imageId,
    imagePath: `/social/posts/${imageId}.jpg`,
    imageAlt: `${title}${description ? ` — ${description}` : ""}`,
  };
}

export type PostSocialCard = ReturnType<typeof postSocialCard>;
