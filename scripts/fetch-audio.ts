#!/usr/bin/env tsx
/**
 * Walks content/listening/*.json, downloads every audioUrl to public/audio/<id>.mp3.
 * Polite: 1 req/sec, 5 retries, skips files already on disk.
 *
 * Run:   npm run fetch:audio
 */

import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CONTENT_DIR = path.resolve(__dirname, "../content/listening");
const AUDIO_DIR = path.resolve(__dirname, "../public/audio");

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

async function exists(p: string) {
  try {
    await fs.access(p);
    return true;
  } catch {
    return false;
  }
}

async function fetchWithRetry(url: string, tries = 5): Promise<ArrayBuffer> {
  let lastErr: unknown;
  for (let i = 1; i <= tries; i++) {
    try {
      const res = await fetch(url, { headers: { "User-Agent": "ielts-mock-client/0.1" } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.arrayBuffer();
    } catch (e) {
      lastErr = e;
      console.warn(`  retry ${i}/${tries} for ${url}: ${(e as Error).message}`);
      await sleep(2000 * i);
    }
  }
  throw lastErr;
}

async function main() {
  await fs.mkdir(AUDIO_DIR, { recursive: true });
  const files = (await fs.readdir(CONTENT_DIR)).filter((f) => f.endsWith(".json"));
  console.log(`Scanning ${files.length} listening tests…`);

  const failures: string[] = [];
  let ok = 0;
  let skipped = 0;

  for (const f of files) {
    const id = f.replace(/\.json$/, "");
    const doc = JSON.parse(await fs.readFile(path.join(CONTENT_DIR, f), "utf8"));
    const url: string | undefined = doc.audioUrl;
    if (!url) {
      skipped++;
      continue;
    }
    const dest = path.join(AUDIO_DIR, `${id}.mp3`);
    if (await exists(dest)) {
      skipped++;
      continue;
    }
    process.stdout.write(`  ${id} ← ${url}\n`);
    try {
      const buf = await fetchWithRetry(url);
      await fs.writeFile(dest, Buffer.from(buf));
      ok++;
      await sleep(1000); // polite
    } catch (e) {
      failures.push(`${id}: ${(e as Error).message}`);
    }
  }

  console.log(`\nDone: downloaded ${ok}, skipped ${skipped}, failed ${failures.length}`);
  if (failures.length) {
    await fs.writeFile(
      path.resolve(__dirname, "fetch-audio-failures.log"),
      failures.join("\n"),
    );
    console.log("See scripts/fetch-audio-failures.log");
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
