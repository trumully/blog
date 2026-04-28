import { execSync } from "node:child_process";

export interface GitCommit {
  hash: string;
  date: Date;
  message: string;
}

const GITHUB_REPO = "https://github.com/trumully/blog";

export function getPostHistory(postId: string): GitCommit[] {
  const filePath = `src/blog/${postId}.md`;
  try {
    const output = execSync(`git log --follow --format="%H|%aI|%s" -- "${filePath}"`, {
      encoding: "utf-8",
    }).trim();
    if (!output) return [];
    return output.split("\n").map((line) => {
      const first = line.indexOf("|");
      const second = line.indexOf("|", first + 1);
      return {
        hash: line.slice(0, first),
        date: new Date(line.slice(first + 1, second)),
        message: line.slice(second + 1),
      };
    });
  } catch {
    return [];
  }
}

export function commitUrl(hash: string): string {
  return `${GITHUB_REPO}/commit/${hash}`;
}

export function postHistoryUrl(postId: string): string {
  return `${GITHUB_REPO}/commits/main/src/blog/${postId}.md`;
}
