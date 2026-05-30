/**
 * IELTS band score conversion tables and answer-equality helper.
 *
 * Source: standard published Cambridge / IDP guidance. The exact thresholds
 * vary by 1–2 marks across actual exams (paper equating); the tables here
 * are the most commonly cited "average" tables — accurate enough for prep.
 */

import type { AnswerValue } from "@/lib/types";

type BandTable = Array<{ min: number; max: number; band: number }>;

export const ACADEMIC_READING_BANDS: BandTable = [
  { min: 39, max: 40, band: 9.0 },
  { min: 37, max: 38, band: 8.5 },
  { min: 35, max: 36, band: 8.0 },
  { min: 33, max: 34, band: 7.5 },
  { min: 30, max: 32, band: 7.0 },
  { min: 27, max: 29, band: 6.5 },
  { min: 23, max: 26, band: 6.0 },
  { min: 19, max: 22, band: 5.5 },
  { min: 15, max: 18, band: 5.0 },
  { min: 13, max: 14, band: 4.5 },
  { min: 10, max: 12, band: 4.0 },
  { min: 8, max: 9, band: 3.5 },
  { min: 6, max: 7, band: 3.0 },
  { min: 4, max: 5, band: 2.5 },
  { min: 0, max: 3, band: 2.0 },
];

export const LISTENING_BANDS: BandTable = [
  { min: 39, max: 40, band: 9.0 },
  { min: 37, max: 38, band: 8.5 },
  { min: 35, max: 36, band: 8.0 },
  { min: 32, max: 34, band: 7.5 },
  { min: 30, max: 31, band: 7.0 },
  { min: 26, max: 29, band: 6.5 },
  { min: 23, max: 25, band: 6.0 },
  { min: 18, max: 22, band: 5.5 },
  { min: 16, max: 17, band: 5.0 },
  { min: 13, max: 15, band: 4.5 },
  { min: 10, max: 12, band: 4.0 },
  { min: 8, max: 9, band: 3.5 },
  { min: 6, max: 7, band: 3.0 },
  { min: 4, max: 5, band: 2.5 },
  { min: 0, max: 3, band: 2.0 },
];

export function rawToBand(raw: number, table: BandTable): number {
  for (const row of table) {
    if (raw >= row.min && raw <= row.max) return row.band;
  }
  return 0;
}

/**
 * Normalise a single token for grading: lowercase, trim, collapse whitespace,
 * strip leading articles, strip trailing punctuation.
 */
function normalise(s: string): string {
  return String(s)
    .toLowerCase()
    .trim()
    .replace(/[\s ]+/g, " ")
    .replace(/^the\s+|^a\s+|^an\s+/, "")
    .replace(/[.,;:!?"]+$/g, "")
    .replace(/[, ]+(\d)/g, "$1"); // 10,000 -> 10000
}

/**
 * Expand answer alternatives:
 *   "forest(s)"         -> ["forest", "forests"]
 *   "forest/forests"    -> ["forest", "forests"]
 *   "20 minutes"        -> ["20 minutes", "20 minute"]
 */
function expandAlternatives(key: string): string[] {
  const acc = new Set<string>();
  const stripped = key.trim();
  // optional plural in parens: "forest(s)"
  const parenMatch = stripped.match(/^(.+)\(([^)]+)\)$/);
  if (parenMatch) {
    acc.add(parenMatch[1]);
    acc.add(parenMatch[1] + parenMatch[2]);
  } else {
    acc.add(stripped);
  }
  // slash alternatives
  const expanded = [...acc].flatMap((s) =>
    s.includes("/") ? s.split("/").map((x) => x.trim()) : [s],
  );
  return expanded.map(normalise).filter(Boolean);
}

/** True if `user` answer matches `key`. Handles string vs string[] (multi-select). */
export function answerEquals(user: AnswerValue | undefined, key: AnswerValue): boolean {
  if (user == null) return false;

  // Array on either side -> set equality of normalised alternatives.
  const toSet = (v: AnswerValue) =>
    new Set((Array.isArray(v) ? v : [v]).flatMap((s) => expandAlternatives(String(s))));

  const u = toSet(user);
  const k = toSet(key);

  // For multi-letter answers (matching/multiselect) we require exact set match.
  if (Array.isArray(user) || Array.isArray(key)) {
    if (u.size !== k.size) return false;
    for (const v of u) if (!k.has(v)) return false;
    return true;
  }

  // For singletons, accept any alternative within the key.
  return [...u].some((v) => k.has(v));
}

export function gradeAnswers(
  answerKey: Record<string, AnswerValue>,
  userAnswers: Record<string, AnswerValue | undefined>,
): { raw: number; total: number; perQuestion: Record<string, boolean> } {
  const total = Object.keys(answerKey).length;
  let raw = 0;
  const perQuestion: Record<string, boolean> = {};
  for (const [qNum, key] of Object.entries(answerKey)) {
    const ok = answerEquals(userAnswers[qNum], key);
    perQuestion[qNum] = ok;
    if (ok) raw += 1;
  }
  return { raw, total, perQuestion };
}
