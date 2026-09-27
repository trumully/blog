import { resolve } from "node:path";
import sharp, { type OverlayOptions } from "sharp";
import type { PostSocialCard } from "./post-social";

const width = 1200;
const height = 630;
// These source assets are read only during Astro's static build (or local development).
const fontFile = resolve("src/assets/fonts/newsreader/newsreader-variable.ttf");

export async function renderSocialCard(card: PostSocialCard): Promise<Buffer> {
  const artworkSource = resolve("src/assets/signatures", card.composition, "mocha.png");
  const artwork = await sharp(artworkSource).resize(430, 460, { fit: "inside" }).png().toBuffer();
  const title = await renderText(card.title, 64, 248, "#cdd6f4", 180);
  const description = card.description ? await renderText(card.description, 30, 140, "#bac2de", 260) : undefined;
  const brand = await renderText("Truman Mulholland", 25, 40, card.accent, 80);
  const layers: OverlayOptions[] = [
    { input: artwork, left: 730, top: 100 },
    { input: brand.data, left: 64, top: 60 },
    { input: title.data, left: 64, top: 150 },
  ];
  if (description) layers.push({ input: description.data, left: 64, top: 150 + title.info.height + 32 });

  return sharp({ create: { width, height, channels: 3, background: "#1e1e2e" } })
    .composite(layers)
    .jpeg({ quality: 92, mozjpeg: true, chromaSubsampling: "4:4:4" })
    .toBuffer();
}

async function renderText(value: string, size: number, maxHeight: number, color: string, maxCharacters: number) {
  const characters = Array.from(value.replace(/\s+/g, " ").trim());
  const copy =
    characters.length > maxCharacters
      ? `${characters
          .slice(0, maxCharacters - 1)
          .join("")
          .trim()}…`
      : characters.join("");
  const escaped = copy.replace(/[&<>"']/g, (character) => `&#${character.charCodeAt(0)};`);
  const text = {
    text: `<span foreground="${color}">${escaped || " "}</span>`,
    font: `Newsreader ${size}`,
    fontfile: fontFile,
    width: 630,
    rgba: true,
    wrap: "word-char" as const,
  };
  const rendered = await sharp({ text }).png().toBuffer({ resolveWithObject: true });
  if (rendered.info.height <= maxHeight) return rendered;
  return sharp({ text: { ...text, height: maxHeight } })
    .png()
    .toBuffer({ resolveWithObject: true });
}
