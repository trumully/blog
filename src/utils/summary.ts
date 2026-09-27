const MAX_EXCERPT_LENGTH = 240;

export function markdownExcerpt(markdown: string, maxLength = MAX_EXCERPT_LENGTH): string {
  const paragraphs = extractParagraphs(markdown);
  const excerpt = paragraphs.find(isMeaningfulParagraph) ?? paragraphs[0] ?? "";

  return truncate(excerpt, maxLength);
}

function extractParagraphs(markdown: string): string[] {
  const lines = markdown
    .replace(/\r\n?/g, "\n")
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/<(script|style|pre|code)\b[^>]*>[\s\S]*?<\/\1\s*>/gi, "")
    .split("\n");
  const blocks: string[] = [];
  let paragraph: string[] = [];
  let skippingStructuredBlock = false;
  let fence: { marker: "`" | "~"; length: number } | undefined;

  const flushParagraph = () => {
    if (paragraph.length > 0) {
      blocks.push(paragraph.join(" "));
      paragraph = [];
    }
  };

  for (const line of lines) {
    const fenceMatch = line.match(/^\s{0,3}(`{3,}|~{3,})/);
    if (fence) {
      const closingFence = fenceMatch?.[1];
      if (closingFence && closingFence[0] === fence.marker && closingFence.length >= fence.length) {
        fence = undefined;
      }
      flushParagraph();
      continue;
    }
    if (fenceMatch) {
      flushParagraph();
      fence = { marker: fenceMatch[1][0] as "`" | "~", length: fenceMatch[1].length };
      continue;
    }

    if (!line.trim()) {
      flushParagraph();
      skippingStructuredBlock = false;
      continue;
    }

    if (/^(?: {4}|\t)/.test(line)) {
      flushParagraph();
      skippingStructuredBlock = true;
      continue;
    }

    if (/^\s{0,3}#{1,6}(?:\s|$)/.test(line)) {
      flushParagraph();
      skippingStructuredBlock = false;
      continue;
    }

    if (/^\s{0,3}(?:={2,}|-{3,})\s*$/.test(line)) {
      paragraph = [];
      skippingStructuredBlock = false;
      continue;
    }

    if (/^\s{0,3}(?:>|[-+*]\s|\d+[.)]\s)/.test(line)) {
      flushParagraph();
      skippingStructuredBlock = true;
      continue;
    }

    if (skippingStructuredBlock && /^ {1,3}\S/.test(line)) continue;
    skippingStructuredBlock = false;
    paragraph.push(line.trim());
  }
  flushParagraph();

  return blocks.map(toPlainText).filter(Boolean);
}

function toPlainText(markdown: string): string {
  const withoutLinks = stripLinkSyntax(markdown);
  const plainText = withoutLinks
    .replace(/(`+)[\s\S]*?\1/g, " ")
    .replace(/<((?:https?:\/\/|mailto:)[^>]+)>/gi, " ")
    .replace(/<[^>]*>/g, " ")
    .replace(/\\([\\`*{}\[\]()#+\-.!_>])/g, "$1")
    .replace(/\*\*|__|~~|[*_~]/g, "")
    .replace(/\s+/g, " ")
    .trim();

  return decodeCommonEntities(plainText);
}

function stripLinkSyntax(markdown: string): string {
  let result = "";
  let index = 0;

  while (index < markdown.length) {
    const image = markdown[index] === "!" && markdown[index + 1] === "[";
    const opening = image ? index + 1 : index;
    if (markdown[opening] !== "[") {
      result += markdown[index];
      index++;
      continue;
    }

    const labelEnd = findClosing(markdown, opening, "[", "]");
    if (labelEnd === -1) {
      result += markdown[index];
      index++;
      continue;
    }

    const label = markdown.slice(opening + 1, labelEnd);
    const destinationStart = labelEnd + 1;
    if (markdown[destinationStart] === "(") {
      const destinationEnd = findClosing(markdown, destinationStart, "(", ")");
      if (destinationEnd !== -1) {
        result += image ? " " : label;
        index = destinationEnd + 1;
        continue;
      }
    } else if (markdown[destinationStart] === "[") {
      const referenceEnd = findClosing(markdown, destinationStart, "[", "]");
      if (referenceEnd !== -1) {
        result += image ? " " : label;
        index = referenceEnd + 1;
        continue;
      }
    }

    result += markdown.slice(index, opening + 1);
    index = opening + 1;
  }

  return result;
}

function findClosing(value: string, start: number, open: string, close: string): number {
  let depth = 0;
  let escaped = false;

  for (let index = start; index < value.length; index++) {
    const character = value[index];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (character === "\\") {
      escaped = true;
      continue;
    }
    if (character === open) depth++;
    if (character === close && --depth === 0) return index;
  }

  return -1;
}

function isMeaningfulParagraph(value: string): boolean {
  const words = value.match(/[\p{L}\p{N}]{2,}/gu) ?? [];
  return words.length >= 4 || value.length >= 32;
}

function truncate(value: string, maxLength: number): string {
  const characters = Array.from(value);
  if (characters.length <= maxLength) return value;
  const shortened = characters
    .slice(0, maxLength + 1)
    .join("")
    .replace(/\s+\S*$/, "")
    .trim();
  return `${shortened || characters.slice(0, maxLength).join("").trim()}…`;
}

function decodeCommonEntities(value: string): string {
  return value.replace(/&(#x[\da-f]+|#\d+|amp|apos|gt|lt|quot|nbsp);/gi, (entity, match: string) => {
    const lower = match.toLowerCase();
    if (lower === "amp") return "&";
    if (lower === "apos") return "'";
    if (lower === "gt") return ">";
    if (lower === "lt") return "<";
    if (lower === "quot") return '"';
    if (lower === "nbsp") return " ";

    const codePoint = lower.startsWith("#x") ? Number.parseInt(lower.slice(2), 16) : Number(lower.slice(1));
    return Number.isSafeInteger(codePoint) && codePoint >= 0 && codePoint <= 0x10ffff
      ? String.fromCodePoint(codePoint)
      : entity;
  });
}
