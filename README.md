# IELTS CB Mock Platform

Computer-Delivered IELTS practice — Next.js (App Router) + React + TypeScript + Tailwind. No backend, no accounts. All progress is stored in `localStorage`.

## Quick start

```bash
cd ielts-platform
npm install
npm run dev
```

Open <http://localhost:3000>.

## How content gets in

The repo ships pre-built JSON content under `content/`.

**Reading & Listening** come from the cleaned `v2/` dataset (flat text blocks + complete answer keys + real MP3s). Rebuild them with:

```bash
python3 scripts/build_content_v2.py --copy-audio
```

This reads `v2/reading/*.json`, `v2/listening_structured/*.json`, and `v2/audio/*.mp3`, converts each into the app's typed schema, and copies the audio into `public/audio/{NNNN}.mp3`. The v2 answer keys are authoritative, and every answer-key number is guaranteed a rendered input (un-classifiable questions fall back to a `gapFill` text box).

**Writing & Speaking** still come from the original `Tests/` materials (v2 has none):

```bash
python3 scripts/build_content.py --copy-images   # writing + speaking only needed now
```

Output layout:

```
content/
├── reading/{NNNN}.json     (from v2 — 304 tests)
├── listening/{NNNN}.json   (from v2 — 186 tests, 172 with audio)
├── writing/{NNNN}.json     (from Tests/ — 117 tests)
├── speaking/{NNNN}.json    (from Tests/ — 29 unique topics)
└── index.json
```

### Listening audio

Audio now ships locally: `npm run build:content` copies `v2/audio/{n}_we.mp3` → `public/audio/{NNNN}.mp3`, and the player prefers the local file. 14 listening tests have no audio in the source and will show a "no audio attached" notice.

> Legacy: the original HTML pool referenced MP3s on `practicepteonline.com` (hotlink-protected, unreliable). The `scripts/fetch-audio.ts` fetcher below targets those and is no longer needed now that v2 ships real audio.

```bash
npm run fetch:audio
```

This downloads every referenced MP3 into `public/audio/{id}.mp3` (polite: 1 req/sec, 5 retries, skips files already on disk). If you don't run it, the Listening player falls back to the remote URL — which will work as long as the source site allows hotlinking. If it doesn't, you'll see a warning in the test page.

## Adding a new mock

For any of Reading / Listening / Writing, drop a new `extracted_content.html` into the matching `Tests/` folder structure (`ielts-{section}-test-{N}/extracted_content.html`) and re-run `python3 scripts/build_content.py`. The parser expects:

- An embedded `<div id="bg-showmore-hidden-...">` with the answer key (one `N. answer<br>` per line)
- Question groups introduced by `Questions N-M`
- Standard instruction phrases (`Choose the correct letter`, `Complete the notes`, `TRUE/FALSE/NOT GIVEN`, …)

If your test follows that template, it parses cleanly.

For Speaking, drop a `Speaking-{N}.docx` into `Tests/Speaking/docx/`. The DOCX is expected to have four short lines:

```
Describe an artist or entertainer you admire:
Speaking Part 1: What kind of music or movies do you enjoy?
Speaking Part 2: Describe a song or piece of music you like.
Speaking Part 3: Why are some artists or entertainers considered role models?
```

## JSON content schema

See `lib/types.ts` for the full TypeScript definitions. Quick reference:

- **ReadingTest** — `id`, `passages: ReadingPassage[]` (1–3, HTML body), `questions: Question[]` (40), `answerKey: { [num]: string | string[] }`.
- **ListeningTest** — `id`, `parts: ListeningPart[]` (4), `audioUrl?`, `localAudioPath?`, `questions`, `answerKey`.
- **WritingTest** — `id`, `task1: { prompt, imageUrl?, minWords: 150 }`, `task2: { prompt, minWords: 250 }`.
- **SpeakingTest** — `id`, `topic`, `part1.questions`, `part2.{cueCard,bulletPoints,prepSeconds,answerSeconds}`, `part3.questions`.
- **Question** is a discriminated union over `type`: `multipleChoice`, `tfng`, `ynng`, `matchHeadings`, `matchInfo`, `matchFeatures`, `matchEndings`, plus a generic gap-fill family (`sentenceCompletion`, `summaryCompletion`, `noteCompletion`, `tableCompletion`, `formCompletion`, `flowChartCompletion`, `diagramLabel`, `mapPlanLabelling`, `shortAnswer`, `gapFill`) and an `unsupported` fallback that just shows the raw HTML chunk and a free text input.

## Routes

| Path | Purpose |
|---|---|
| `/` | Home — section browsers, random buttons, Full Mock CTA |
| `/reading/[id]` | Reading runner (split-screen, 60-min timer) |
| `/listening/[id]` | Listening runner (once-only audio + 2 min review) |
| `/writing/[id]` | Writing runner (Task 1 / Task 2 tabs, word counter, autosave) |
| `/speaking/[id]` | Speaking runner (Part 1 → 2-prep → 2-answer → 3) |
| `/full-mock/[id]` | Full Mock orchestrator |
| `/results/[attemptId]` | Reading/Listening band-score result |
| `/my-essays`, `/my-speaking` | Saved Writing/Speaking with export and delete |
| `/history` | All scored attempts |

## localStorage keys

| Key | Type |
|---|---|
| `ielts.attempts` | `AttemptRecord[]` index of all scored attempts |
| `ielts.attempt.<id>.answers` | `{ [questionNumber]: answer }` |
| `ielts.attempt.<id>.flags` | `number[]` review flags |
| `ielts.attempt.<id>.highlights` | `{ start, end, passage }[]` (Reading) |
| `ielts.essays.<testId>.<timestamp>` | `EssayRecord` |
| `ielts.speaking.<testId>.<timestamp>` | `SpeakingRecord` |
| `ielts.fullMock.<id>` | `FullMockState` |

Nothing leaves the browser.

## What's NOT implemented in v1 (and what to do about it)

1. **Voice recording for Speaking.** Text input only. The cue-card timer logic and 4-bullet template already match the real exam; swapping the textarea for `MediaRecorder` is a contained change. Suggested approach: store base64-encoded `audio/webm` blobs in IndexedDB (not localStorage — too small).

2. **Auto-grading of Writing/Speaking.** Deliberately out of scope. If you want a feedback layer, point at a small open-weights model running locally, or wire `/api/grade` to an LLM. The schema already includes `wordCount` per essay so you can prefilter.

3. **Reading highlight + sticky notes UI.** The CSS hook (`mark.exam-hl`), the schema entry (`ielts.attempt.<id>.highlights`), and the storage adapter exist; the actual range-selection/right-click logic is not wired. Add a Selection API handler in `components/reading/ReadingRunner.tsx` and wrap user-selected ranges in `<mark>`.

4. **Mobile layout.** The grid collapses on narrow screens but isn't ergonomic. Real CB-IELTS is desktop-only; for parity, consider showing a "use a wider screen" notice under 1024px.

5. **General Training Reading variant.** Schema field `variant` exists; band table for GT is not included. Add it to `lib/grading/band.ts` and pick by `test.variant`.

6. **Parser coverage.** With the current corpus (~276 reading, ~188 listening, ~120 writing HTMLs), the build produces:

   ```
   Reading:   197 / 276 parsed
   Listening: 140 / 188 parsed
   Writing:   117 / 120 parsed
   Speaking:   31 /  31 parsed
   ```

   Failures are logged to `scripts/parse-failures.log`. Most are tests where the "Questions N-M" header uses non-standard punctuation, or where the embedded answer block is missing. Easiest fix: open the affected HTML, normalize the header, re-run.

   Within successfully-parsed tests, some individual question groups fall through to the `unsupported` type — the UI still renders them (raw text + a free text field), and grading still works because the answer key is parsed independently. To improve parser hit-rate, extend `INSTRUCTION_CUES` in `scripts/build_content.py`.

7. **The Listening MP3 dependency.** The 115 MP3 URLs in the source point at one external host. Long-term, you'll want either local audio or a self-hosted mirror. The fetcher script gives you the local-audio path with one command.

8. **Reading passage segmentation.** Currently the parser dumps the entire passage body into `passages[0].bodyHtml`. Improving this requires a `<h2>`-based splitter; in practice the single-pane render is readable enough.

9. **Copyright.** The scraped HTML appears to come from a third-party site. Before publishing this app, confirm the source content is licensed (or rebuild content from materials you have rights to — the DOCX pool of 31 tests is a safer starting point).

10. **No Vercel config.** As you asked, this runs locally only. To deploy: `npx vercel`. Static export should also work since the only runtime API is `localStorage`.

## Why these particular decisions

The CB-IELTS spec (researched May 2026) confirms: 30-min Listening with no transfer time, 60-min Reading with split-screen + highlight + notes + review flags, 60-min Writing with word counter, face-to-face Speaking. The platform models all of that except the live Speaking examiner — instead you type your answer, which is a fair preparation tool, not an exam simulator.

Band-score conversion tables use the most commonly cited averages — Cambridge's exact equating differs by 1–2 marks per test version, so don't treat the displayed band as a guaranteed real-exam outcome.

---

Built 2026-05. Materials and scripts in this repo are for personal study.
