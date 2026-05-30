/**
 * Thin localStorage adapter. All writes are JSON; all reads are typed.
 * Safe to call on the server (returns null/undefined when window is absent).
 */
"use client";

const SAFE = typeof window !== "undefined";

function readJSON<T>(key: string): T | null {
  if (!SAFE) return null;
  const raw = window.localStorage.getItem(key);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function writeJSON(key: string, value: unknown) {
  if (!SAFE) return;
  window.localStorage.setItem(key, JSON.stringify(value));
}

function remove(key: string) {
  if (!SAFE) return;
  window.localStorage.removeItem(key);
}

function listKeys(prefix: string): string[] {
  if (!SAFE) return [];
  const out: string[] = [];
  for (let i = 0; i < window.localStorage.length; i++) {
    const k = window.localStorage.key(i);
    if (k && k.startsWith(prefix)) out.push(k);
  }
  return out;
}

// ---- domain accessors -------------------------------------------------------

export type AttemptRecord = {
  id: string;
  section: "reading" | "listening" | "writing" | "speaking";
  testId: string;
  startedAt: string;
  finishedAt?: string;
  raw?: number;
  total?: number;
  band?: number;
};

const K = {
  attempts: "ielts.attempts",
  attemptAnswers: (id: string) => `ielts.attempt.${id}.answers`,
  attemptFlags: (id: string) => `ielts.attempt.${id}.flags`,
  attemptHighlights: (id: string) => `ielts.attempt.${id}.highlights`,
  essay: (testId: string, ts: string) => `ielts.essays.${testId}.${ts}`,
  essayPrefix: "ielts.essays.",
  speaking: (testId: string, ts: string) => `ielts.speaking.${testId}.${ts}`,
  speakingPrefix: "ielts.speaking.",
  fullMock: (id: string) => `ielts.fullMock.${id}`,
};

export const Attempts = {
  list(): AttemptRecord[] {
    return readJSON<AttemptRecord[]>(K.attempts) || [];
  },
  upsert(rec: AttemptRecord) {
    const all = this.list();
    const idx = all.findIndex((a) => a.id === rec.id);
    if (idx >= 0) all[idx] = rec;
    else all.unshift(rec);
    writeJSON(K.attempts, all);
  },
  getAnswers(attemptId: string): Record<string, string | string[]> {
    return readJSON(K.attemptAnswers(attemptId)) || {};
  },
  saveAnswers(attemptId: string, answers: Record<string, string | string[]>) {
    writeJSON(K.attemptAnswers(attemptId), answers);
  },
  getFlags(attemptId: string): number[] {
    return readJSON<number[]>(K.attemptFlags(attemptId)) || [];
  },
  saveFlags(attemptId: string, flags: number[]) {
    writeJSON(K.attemptFlags(attemptId), flags);
  },
  getHighlights(attemptId: string): { start: number; end: number; passage: number }[] {
    return readJSON(K.attemptHighlights(attemptId)) || [];
  },
  saveHighlights(attemptId: string, list: { start: number; end: number; passage: number }[]) {
    writeJSON(K.attemptHighlights(attemptId), list);
  },
};

export type EssayRecord = {
  testId: string;
  timestamp: string;
  task1: string;
  task2: string;
};

export const Essays = {
  save(rec: EssayRecord) {
    writeJSON(K.essay(rec.testId, rec.timestamp), rec);
  },
  list(): EssayRecord[] {
    return listKeys(K.essayPrefix)
      .map((k) => readJSON<EssayRecord>(k))
      .filter((x): x is EssayRecord => !!x)
      .sort((a, b) => (a.timestamp < b.timestamp ? 1 : -1));
  },
  remove(testId: string, timestamp: string) {
    remove(K.essay(testId, timestamp));
  },
};

export type SpeakingRecord = {
  testId: string;
  timestamp: string;
  part1: string[];
  part2: string;
  part3: string[];
};

export const Speaking = {
  save(rec: SpeakingRecord) {
    writeJSON(K.speaking(rec.testId, rec.timestamp), rec);
  },
  list(): SpeakingRecord[] {
    return listKeys(K.speakingPrefix)
      .map((k) => readJSON<SpeakingRecord>(k))
      .filter((x): x is SpeakingRecord => !!x)
      .sort((a, b) => (a.timestamp < b.timestamp ? 1 : -1));
  },
  remove(testId: string, timestamp: string) {
    remove(K.speaking(testId, timestamp));
  },
};

export type FullMockState = {
  id: string;
  reading: string;
  listening: string;
  writing: string;
  speaking: string;
  currentStage: "listening" | "reading" | "writing" | "speaking" | "done";
};

export const FullMock = {
  save(state: FullMockState) {
    writeJSON(K.fullMock(state.id), state);
  },
  load(id: string): FullMockState | null {
    return readJSON<FullMockState>(K.fullMock(id));
  },
};
