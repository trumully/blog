import type { AstroIntegration, AstroUserConfig } from "astro";
import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";
import astroMermaid from "astro-mermaid";
interface MermaidCodeNode {
  type: "code";
  value: string;
  lang?: string | null;
  meta?: string | null;
}

const site = "https://truman.mulholland.nz";
const protectedMeta = "blog-mermaid-protected";

function isBlogPost(fileURL: URL | undefined): boolean {
  const pathname = fileURL?.pathname.toLowerCase().replaceAll("\\", "/") ?? "";
  return pathname.includes("/src/blog/");
}

/*
 * astro-mermaid's Markdown plugin is global. Protect non-blog and source
 * fences before it runs, then restore them for the normal Shiki pipeline.
 */
function protectMermaidCode(fileURL: URL | undefined) {
  const isBlog = isBlogPost(fileURL);

  return {
    name: "blog-mermaid-protect",
    code(node: MermaidCodeNode) {
      if (node.lang !== "mermaid") return;

      const info = node.meta?.trim() ?? "";
      const isSource = info.split(/\s+/, 1)[0] === "source";
      if (isBlog && !isSource) return;

      return {
        ...node,
        lang: null,
        meta: [node.meta, protectedMeta].filter(Boolean).join(" "),
      };
    },
  };
}

const restoreMermaidCode = {
  name: "blog-mermaid-restore",
  code(node: MermaidCodeNode) {
    const marker = ` ${protectedMeta}`;
    if (node.lang !== null || (node.meta !== protectedMeta && !node.meta?.endsWith(marker))) return;

    const meta = node.meta?.slice(0, -marker.length).trim() ?? "";
    return {
      ...node,
      lang: "mermaid",
      meta: meta || null,
    };
  },
};

function scopeMermaidProcessing(): AstroIntegration {
  return {
    name: "blog-mermaid-scope",
    hooks: {
      "astro:config:setup": ({ config, updateConfig }) => {
        const processor = config.markdown?.processor;
        if (processor?.name !== "satteri") {
          throw new Error("blog-mermaid-scope requires Astro's Sätteri Markdown processor");
        }

        const options = processor.options;
        options.mdastPlugins = [
          (context) => protectMermaidCode(context.fileURL),
          ...options.mdastPlugins,
          restoreMermaidCode,
        ];
        updateConfig({ markdown: { processor } });
      },
    },
  };
}

// https://astro.build/config
export default defineConfig({
  site: process.env.SITE_URL ?? site,
  integrations: [sitemap(), astroMermaid({ autoTheme: true, enableLog: false }), scopeMermaidProcessing()],
  markdown: {
    shikiConfig: {
      themes: {
        light: "catppuccin-latte",
        dark: "catppuccin-mocha",
      },
    },
  },
}) satisfies AstroUserConfig;
