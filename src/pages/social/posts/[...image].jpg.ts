import type { APIRoute, GetStaticPaths } from "astro";
import { getCollection } from "astro:content";
import { postSocialCard, type PostSocialCard } from "../../../utils/post-social";
import { renderSocialCard } from "../../../utils/render-social-card";

export const getStaticPaths = (async () => {
  const posts = await getCollection("blog");
  return posts.map((post) => {
    const card = postSocialCard(post);
    return { params: { image: card.imageId }, props: { card } };
  });
}) satisfies GetStaticPaths;

export const GET: APIRoute = async ({ props }) => {
  const image = await renderSocialCard(props.card as PostSocialCard);
  return new Response(new Uint8Array(image), { headers: { "Content-Type": "image/jpeg" } });
};
