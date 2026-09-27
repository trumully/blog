import { execFileSync } from "node:child_process";

export interface GitCommit {
  hash: string;
  committerDate: Date;
  subject: string;
}

const GITHUB_REPO = "https://github.com/trumully/blog";
const COMMIT_HASH_PATTERN = /^(?:[a-f\d]{40}|[a-f\d]{64})$/i;
const ISO_COMMITTER_DATE_PATTERN =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|[+-](\d{2}):(\d{2}))$/;

export function getPostHistory(postId: string): GitCommit[] {
  const filePath = `src/blog/${postId}.md`;
  try {
    const output = execFileSync("git", ["log", "--follow", "--format=%H%x00%cI%x00%s", "--", filePath], {
      encoding: "utf-8",
    });
    return parsePostHistoryOutput(output);
  } catch {
    return [];
  }
}

export function parsePostHistoryOutput(output: string): GitCommit[] {
  return output.split(/\r?\n/).flatMap((line) => {
    const [hash, dateText, subject, extra] = line.split("\0");
    if (extra !== undefined || !hash || !dateText || subject === undefined || !COMMIT_HASH_PATTERN.test(hash))
      return [];

    const committerDate = parseCommitterDate(dateText);
    if (!committerDate) return [];

    return [{ hash, committerDate, subject }];
  });
}

export function shouldShowPostHistory(history: readonly GitCommit[]): boolean {
  return history.length > 1;
}

export function commitUrl(hash: string): string {
  return `${GITHUB_REPO}/commit/${hash}`;
}

export function postHistoryUrl(postId: string): string {
  return `${GITHUB_REPO}/commits/main/src/blog/${postId}.md`;
}

function parseCommitterDate(value: string): Date | null {
  const match = ISO_COMMITTER_DATE_PATTERN.exec(value);
  if (!match) return null;

  const [, yearText, monthText, dayText, hourText, minuteText, secondText, offsetHourText, offsetMinuteText] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const hour = Number(hourText);
  const minute = Number(minuteText);
  const second = Number(secondText);
  const offsetHour = Number(offsetHourText ?? 0);
  const offsetMinute = Number(offsetMinuteText ?? 0);
  const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const daysInMonth = [31, leapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1];

  if (
    month < 1 ||
    month > 12 ||
    day < 1 ||
    day > (daysInMonth ?? 0) ||
    hour > 23 ||
    minute > 59 ||
    second > 59 ||
    offsetHour > 23 ||
    offsetMinute > 59
  ) {
    return null;
  }

  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date : null;
}
