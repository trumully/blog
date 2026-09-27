/** Normalize a path for canonical identity; deployment bases are intentionally not applied. */
export function canonicalPath(path: string): string {
  const input = path.trim();
  let pathname = input;

  if (/^[a-z][a-z\d+.-]*:\/\//i.test(input)) {
    try {
      pathname = new URL(input).pathname;
    } catch {
      pathname = input;
    }
  } else if (input.startsWith("//")) {
    try {
      pathname = new URL(input, "https://canonical.invalid").pathname;
    } catch {
      pathname = input;
    }
  }

  pathname = pathname.split(/[?#]/, 1)[0] ?? "";
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length === 0) return "/";

  const normalized = `/${segments.join("/")}`;
  const lastSegment = segments.at(-1) ?? "";
  return /\.[^./]+$/.test(lastSegment) ? normalized : `${normalized}/`;
}

export function postPath(id: string): string {
  return canonicalPath(`/posts/${id}/`);
}

/** Add Astro's deployment base to a site-local path without changing canonical identity paths. */
export function publicPath(path: string, base = import.meta.env.BASE_URL): string {
  const normalizedPath = canonicalPath(path);
  const normalizedBase = canonicalPath(base);
  if (normalizedBase === "/") return normalizedPath;
  if (normalizedPath === normalizedBase.slice(0, -1) || normalizedPath.startsWith(normalizedBase)) {
    return normalizedPath;
  }
  return `${normalizedBase.slice(0, -1)}${normalizedPath}`;
}
