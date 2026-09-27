import { hashString } from "./hash-string.ts";
import { canonicalPath } from "./urls.ts";

export const SIGNATURE_COMPOSITIONS = ["ribbon-v1", "open-crescent", "open-hairpin"] as const;

export type SignatureCompositionId = (typeof SIGNATURE_COMPOSITIONS)[number];

export interface SignatureAccentPalette {
  latte: string;
  mocha: string;
}

const SIGNATURE_ACCENTS: Readonly<Record<SignatureCompositionId, SignatureAccentPalette>> = {
  "ribbon-v1": { latte: "#1e66f5", mocha: "#89b4fa" },
  "open-crescent": { latte: "#8839ef", mocha: "#cba6f7" },
  "open-hairpin": { latte: "#179299", mocha: "#94e2d5" },
};

const PINNED_COMPOSITIONS: Readonly<Record<string, SignatureCompositionId>> = {
  "/posts/my-agentic-development-workflow/": "ribbon-v1",
  "/posts/multi-revit-version-addin-oauth/": "open-hairpin",
  "/posts/my-first-post/": "open-crescent",
};

export function selectSignatureComposition(path: string): SignatureCompositionId {
  const canonicalIdentity = canonicalPath(path);
  const pinnedComposition = PINNED_COMPOSITIONS[canonicalIdentity];
  if (pinnedComposition) return pinnedComposition;
  return selectRendezvousComposition(canonicalIdentity, SIGNATURE_COMPOSITIONS);
}

export function selectSignatureAccent(path: string): SignatureAccentPalette {
  return SIGNATURE_ACCENTS[selectSignatureComposition(path)];
}

// Stable IDs and lexical tie-breaking make selection independent of catalogue order.
// Adding a candidate only moves unpinned identities when that candidate wins; explicit pins never move.
export function selectRendezvousComposition<T extends string>(canonicalIdentity: string, candidates: readonly T[]): T {
  const orderedCandidates = [...new Set(candidates)].sort();
  if (orderedCandidates.length === 0) {
    throw new Error("At least one signature composition is required.");
  }

  let winner = orderedCandidates[0];
  let winningScore = rendezvousScore(canonicalIdentity, winner);

  for (const candidate of orderedCandidates.slice(1)) {
    const score = rendezvousScore(canonicalIdentity, candidate);
    if (score > winningScore) {
      winner = candidate;
      winningScore = score;
    }
  }

  return winner;
}

function rendezvousScore(canonicalIdentity: string, compositionId: string): number {
  return hashString(`${canonicalIdentity}\0${compositionId}`);
}
