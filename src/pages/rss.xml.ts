import rss from "@astrojs/rss";
import type { APIContext } from "astro";
import { getCollection } from "astro:content";
import { postPath, publicPath } from "../utils/urls";

export async function GET(context: APIContext) {
  const posts = await getCollection("blog");
  return rss({
    title: "My Blog",
    description: "My journey learning Astro",
    site: new URL(publicPath("/"), context.site!),
    items: posts.map((post) => ({
      title: post.data.title,
      date: post.data.date,
      description: post.data.description,
      link: publicPath(postPath(post.id)),
    })),
    customData: `<language>en-us</language>`,
  });
}
