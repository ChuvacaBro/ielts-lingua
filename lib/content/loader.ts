/**
 * Server-side content loaders. content/ ships in the repo, so we read the
 * JSON synchronously at request time. Next.js statically caches these.
 */
import fs from "node:fs";
import path from "node:path";
import { WRITING_IMG_IDS } from "@/lib/r2-assets";
import type {
  Catalog,
  ListeningTest,
  ReadingTest,
  SpeakingTest,
  WritingTest,
} from "@/lib/types";

const CONTENT_DIR = path.join(process.cwd(), "content");

function readJSON<T>(file: string): T {
  const raw = fs.readFileSync(path.join(CONTENT_DIR, file), "utf8");
  return JSON.parse(raw) as T;
}

export function loadCatalog(): Catalog {
  return readJSON<Catalog>("index.json");
}

/** Prefix asset paths ("/reading-img/…") with the R2 base URL in production. */
function withAssets(paths: string[] | undefined, assetsUrl: string) {
  if (!paths || !assetsUrl) return paths;
  return paths.map((p) => (p.startsWith("/") ? `${assetsUrl}${p}` : p));
}

export function loadReading(id: string): ReadingTest {
  const test = readJSON<ReadingTest>(path.join("reading", `${id}.json`));
  const assetsUrl = process.env.NEXT_PUBLIC_ASSETS_URL || "";
  if (assetsUrl) {
    for (const p of test.passages || []) {
      p.images = withAssets(p.images, assetsUrl);
    }
  }
  return test;
}

export function loadListening(id: string): ListeningTest {
  const test = readJSON<ListeningTest>(path.join("listening", `${id}.json`));
  const assetsUrl = process.env.NEXT_PUBLIC_ASSETS_URL || "";
  if (assetsUrl) {
    if (test.localAudioPath) {
      const r2Path = test.localAudioPath.replace(/^\/audio\//, "/listening/");
      test.localAudioPath = `${assetsUrl}${r2Path}`;
    }
    for (const p of test.parts || []) {
      p.images = withAssets(p.images, assetsUrl);
    }
  }
  return test;
}

export function loadWriting(id: string): WritingTest {
  const test = readJSON<WritingTest>(path.join("writing", `${id}.json`));
  const assetsUrl = process.env.NEXT_PUBLIC_ASSETS_URL || "";
  if (assetsUrl && test.task1 && WRITING_IMG_IDS.has(id)) {
    test.task1.imageUrl = `${assetsUrl}/writing-img/${id}/image_1.png`;
  }
  return test;
}

export function loadSpeaking(id: string): SpeakingTest {
  return readJSON<SpeakingTest>(path.join("speaking", `${id}.json`));
}

/**
 * Pick a random test of each section for the "Full Mock" CTA.
 * Constraint: Listening test must reference an audio URL.
 */
export function pickFullMockIds(): {
  reading: string;
  listening: string;
  writing: string;
  speaking: string;
} {
  const cat = loadCatalog();
  const r = pickRandom(cat.reading.map((x) => x.id));
  const lWithAudio = cat.listening
    .filter((x) => x.flags.hasAudioUrl)
    .map((x) => x.id);
  const l = pickRandom(
    lWithAudio.length ? lWithAudio : cat.listening.map((x) => x.id),
  );
  const w = pickRandom(cat.writing.map((x) => x.id));
  const s = pickRandom(cat.speaking.map((x) => x.id));
  return { reading: r, listening: l, writing: w, speaking: s };
}

function pickRandom<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}
