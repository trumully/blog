import { mkdir, readdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import sharp from "sharp";

const projectRoot = fileURLToPath(new URL("../../", import.meta.url));
const sourceRoot = path.join(projectRoot, "src/assets/signatures");
const outputRoot = path.join(projectRoot, "public/social");
const width = 1200;
const height = 630;
const backgroundColor = "#1e1e2e";

function createBackground() {
  return Buffer.from(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
      <defs>
        <radialGradient id="ambient" cx="900" cy="315" r="540" gradientUnits="userSpaceOnUse">
          <stop offset="0" stop-color="#45475a" stop-opacity="0.58" />
          <stop offset="0.58" stop-color="#313244" stop-opacity="0.2" />
          <stop offset="1" stop-color="${backgroundColor}" stop-opacity="0" />
        </radialGradient>
      </defs>
      <rect width="${width}" height="${height}" fill="${backgroundColor}" />
      <rect width="${width}" height="${height}" fill="url(#ambient)" />
    </svg>`
  );
}

async function generatePreview(compositionId, background) {
  const sourcePath = path.join(sourceRoot, compositionId, "mocha.png");
  const sourceMetadata = await sharp(sourcePath).metadata();
  if (!sourceMetadata.hasAlpha || !sourceMetadata.width || !sourceMetadata.height) {
    throw new Error(`Expected a transparent source signature: ${sourcePath}`);
  }

  const { data: artwork, info: artworkInfo } = await sharp(sourcePath)
    .resize(650, 600, { fit: "inside", withoutEnlargement: true })
    .png()
    .toBuffer({ resolveWithObject: true });
  const left = width - artworkInfo.width - 50;
  const top = Math.round((height - artworkInfo.height) / 2);
  const outputPath = path.join(outputRoot, `${compositionId}.jpg`);

  await sharp(background)
    .composite([{ input: artwork, left, top }])
    .jpeg({ quality: 92, mozjpeg: true, chromaSubsampling: "4:4:4" })
    .toFile(outputPath);

  const outputMetadata = await sharp(outputPath).metadata();
  if (
    outputMetadata.format !== "jpeg" ||
    outputMetadata.width !== width ||
    outputMetadata.height !== height ||
    outputMetadata.hasAlpha
  ) {
    throw new Error(`Generated preview has unexpected image properties: ${outputPath}`);
  }

  console.log(`${path.relative(projectRoot, outputPath)} (${outputMetadata.width}x${outputMetadata.height})`);
}

const compositions = (await readdir(sourceRoot, { withFileTypes: true }))
  .filter((entry) => entry.isDirectory())
  .map((entry) => entry.name)
  .sort();

if (compositions.length === 0) {
  throw new Error(`No signature compositions found in ${sourceRoot}`);
}

await mkdir(outputRoot, { recursive: true });
const background = createBackground();
for (const compositionId of compositions) {
  await generatePreview(compositionId, background);
}
