import { glob } from "astro/loaders";
import { defineCollection } from "astro:content";
import { z } from "astro/zod";
const blog = defineCollection({
  loader: glob({ pattern: "**/[^_]*.md", base: "./src/blog" }),
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    description: z.string(),
    tags: z.array(z.string()),
  }),
});
const comments = defineCollection({
  type: "data",
  schema: z.object({
    author: z.string(),
    date: z.coerce.date(),
    content: z.string(),
    url: z.string().url().optional(),
  }),
});
// Export a single `collections` object to register your collection(s)
export const collections = { blog, comments };
