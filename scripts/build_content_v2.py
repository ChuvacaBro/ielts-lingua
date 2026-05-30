#!/usr/bin/env python3
"""
Convert the v2 dataset (../../v2/) into the app's typed JSON schema.

v2 layout:
    v2/reading/{NNN}.json             { n, title, content: [str], answers: {num: ans} }
    v2/listening_structured/{NNN}.json{ n, title, passages: [str], question_groups: [{q_range,text}], answers }
    v2/audio/{n}_we.mp3               actual MP3s

Output (overwrites previous):
    content/reading/{NNNN}.json       ReadingTest
    content/listening/{NNNN}.json     ListeningTest
    public/audio/{NNNN}.mp3           renamed copies of v2 audio
    content/index.json                rebuilt catalog (reading+listening from v2; writing+speaking untouched)

Design guarantees:
  * v2 answer keys are authoritative -> grading is always correct.
  * EVERY answer-key number gets a rendered question object; if classification
    fails, we emit a `gapFill` fallback so all 40 are answerable.

Usage:
    python3 scripts/build_content_v2.py [--limit N] [--copy-audio]
"""

import argparse
import json
import re
import shutil
from glob import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

print("ROOT", ROOT)
V2 = ROOT / "v2"          # IELTS-cracker/.. -> parent; v2 sits beside IELTS-cracker

print("V2", V2)

# Fall back to ../v2 layout if needed.
if not V2.exists():
    V2 = ROOT.parent / "v2"
    
CONTENT = ROOT / "content"
PUBLIC_AUDIO = ROOT / "public" / "audio"

# ---- question classification (shared with the HTML parser) -----------------

INSTRUCTION_CUES = {
    "ynng": re.compile(
        r"YES/NO/NOT\s*GIVEN|YES\s*[\.,;]\s*NO\s*[\.,;]\s*NOT\s*GIVEN|"
        r"agree with the claims of the writer|writer'?s\s+views|writer'?s\s+claims",
        re.I,
    ),
    "tfng": re.compile(
        r"TRUE/FALSE/NOT\s*GIVEN|TRUE\s*[\.,;]\s*FALSE\s*[\.,;]\s*NOT\s*GIVEN|"
        r"agree with the information",
        re.I,
    ),
    "multipleChoice": re.compile(r"Choose the correct letter|Choose .{0,20}FIVE.{0,20}etters", re.I),
    "matchHeadings": re.compile(r"Choose the correct heading|list\s+of\s+headings", re.I),
    "matchInfo": re.compile(r"Which paragraph contains|Which section (mentions|contains)", re.I),
    "matchFeatures": re.compile(r"Match (each|the)\s+(statement|person|sentence|item|theory|study|claim)", re.I),
    "summaryCompletion": re.compile(r"Complete the summary", re.I),
    "noteCompletion": re.compile(r"Complete the notes?\b", re.I),
    "tableCompletion": re.compile(r"Complete the table", re.I),
    "formCompletion": re.compile(r"Complete the form", re.I),
    "flowChartCompletion": re.compile(r"Complete the flow[- ]?chart", re.I),
    "diagramLabel": re.compile(r"Label the diagram", re.I),
    "mapPlanLabelling": re.compile(r"Label the (map|plan)", re.I),
    "shortAnswer": re.compile(r"Answer the questions? below", re.I),
    "sentenceCompletion": re.compile(r"Complete the sentences?\b", re.I),
}
WORD_LIMIT_RE = re.compile(
    r"(NO MORE THAN [A-Z ]+(?:WORDS?|NUMBERS?)|ONE WORD ONLY|ONE WORD OR A NUMBER|"
    r"NO MORE THAN TWO WORDS AND/?OR A NUMBER|TWO WORDS? AND/OR A NUMBER)",
    re.I,
)
HEADER_RE = re.compile(r"Questions?\s+(\d+)\s*(?:and|–|-|to|,|&)\s*(\d+)|Question\s+(\d+)", re.I)


def classify(text: str):
    for typ, rx in INSTRUCTION_CUES.items():
        if rx.search(text):
            return typ
    return None


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def parse_mcq(chunk: str, lo: int, hi: int):
    """Extract MC questions; tolerant of A./A)/A formats. Falls back to gapFill if no options."""
    out = []
    pat = re.compile(
        r"(\d+)[.)]?\s*(.+?)\s*\bA[.)\s]\s*(.+?)\s*\bB[.)\s]\s*(.+?)\s*\bC[.)\s]\s*(.+?)"
        r"(?=\s*\d+[.)]\s|\s*Part\s|\s*Questions?\s|$)",
        re.S,
    )
    for m in pat.finditer(chunk):
        n = int(m.group(1))
        if lo <= n <= hi:
            out.append({
                "number": n, "type": "multipleChoice",
                "stem": clean(m.group(2)),
                "options": [
                    {"letter": "A", "text": clean(m.group(3))},
                    {"letter": "B", "text": clean(m.group(4))},
                    {"letter": "C", "text": clean(m.group(5))},
                ],
            })
    return out


def parse_statements(chunk: str, lo: int, hi: int, typ: str):
    out = []
    for m in re.finditer(r"(?<![A-Za-z])(\d+)[\s.)]+([^\n]+?)(?=\s*\d+[\s.)]|\s*Questions?\s|$)", chunk):
        n = int(m.group(1))
        if lo <= n <= hi:
            out.append({"number": n, "type": typ, "statement": clean(m.group(2))})
    return out


def parse_gapfills(chunk: str, lo: int, hi: int, typ: str, word_limit):
    out = []
    flat = clean(chunk)
    for n in range(lo, hi + 1):
        m = re.search(rf"\(?\b{n}\)?[.:\s]", flat)
        prompt = ""
        if m:
            start = max(0, m.start() - 60)
            end = min(len(flat), m.start() + 110)
            prompt = flat[start:end].strip()
        q = {"number": n, "type": typ, "prompt": prompt or f"Question {n}"}
        if word_limit:
            q["wordLimit"] = word_limit
        out.append(q)
    return out


def parse_questions_from_text(text: str, answer_nums: set[int]):
    """
    Walk a text stream, segment on Questions N-M headers, classify each chunk,
    and emit typed questions. Guarantee every answer number is covered.
    """
    headers = list(HEADER_RE.finditer(text))
    questions: dict[int, dict] = {}
    for i, h in enumerate(headers):
        if h.group(3):  # single "Question N"
            lo = hi = int(h.group(3))
        else:
            lo, hi = int(h.group(1)), int(h.group(2))
        start = h.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        chunk = text[start:end]
        wl_m = WORD_LIMIT_RE.search(chunk)
        word_limit = wl_m.group(1) if wl_m else None
        typ = classify(chunk)
        group_id = f"q{lo}-{hi}"

        if typ == "multipleChoice":
            qs = parse_mcq(chunk, lo, hi) or parse_gapfills(chunk, lo, hi, "gapFill", word_limit)
        elif typ in ("tfng", "ynng"):
            qs = parse_statements(chunk, lo, hi, typ)
        elif typ in ("sentenceCompletion", "summaryCompletion", "noteCompletion",
                     "tableCompletion", "formCompletion", "flowChartCompletion",
                     "shortAnswer", "diagramLabel", "mapPlanLabelling",
                     "matchInfo", "matchFeatures", "matchHeadings"):
            qs = parse_gapfills(chunk, lo, hi, typ, word_limit)
        else:
            qs = parse_gapfills(chunk, lo, hi, "gapFill", word_limit)

        for q in qs:
            q["groupId"] = group_id
            if 0 < q["number"] and q["number"] not in questions:
                questions[q["number"]] = q

    # Guarantee coverage: any answer number missing a question -> gapFill fallback.
    for n in answer_nums:
        if n not in questions:
            questions[n] = {
                "number": n, "type": "gapFill", "groupId": "qfallback",
                "prompt": f"Question {n}",
            }
    return [questions[n] for n in sorted(questions)]


# ---- answer normalisation --------------------------------------------------

def norm_answer(v):
    """v2 answers are strings; split multi-letter sets into arrays."""
    s = str(v).strip()
    if re.fullmatch(r"[A-J](\s*[,/]\s*[A-J])+", s, re.I):
        return [p.strip().upper() for p in re.split(r"\s*[,/]\s*", s)]
    return s


# ---- reading ---------------------------------------------------------------

def is_prose(block: str) -> bool:
    b = block.strip()
    if re.match(r"^Questions?\s+\d", b, re.I):
        return False
    if re.match(r"^(YES|TRUE|NO|FALSE|NOT GIVEN)\b", b):
        return False
    # option/word-bank lists: many single-letter labels
    if len(re.findall(r"\b[A-J]\s", b)) >= 4 and len(b) < 400:
        return False
    return len(b) > 180


def build_reading(doc, tid):
    content = doc["content"]
    answers = {str(k): norm_answer(v) for k, v in doc["answers"].items()}
    answer_nums = {int(k) for k in answers}

    # group consecutive prose blocks into runs; take 3 longest as passages.
    runs, cur = [], []
    for block in content:
        if is_prose(block):
            cur.append(block.strip())
        else:
            if cur:
                runs.append(cur)
                cur = []
    if cur:
        runs.append(cur)
    runs.sort(key=lambda r: sum(len(x) for x in r), reverse=True)
    top = runs[:3]
    # restore reading order of the chosen runs
    top.sort(key=lambda r: content.index(next(b for b in content if b.strip() == r[0])))
    passages = []
    for i, run in enumerate(top):
        passages.append({
            "number": i + 1,
            "title": f"Passage {i + 1}",
            "bodyHtml": "".join(f"<p>{clean(p)}</p>" for p in run),
        })
    if not passages:
        passages = [{"number": 1, "title": "Passage 1",
                     "bodyHtml": "".join(f"<p>{clean(b)}</p>" for b in content)}]

    questions = parse_questions_from_text("\n".join(content), answer_nums)
    return {
        "id": tid, "variant": "academic", "source": "v2",
        "passages": passages, "questions": questions, "answerKey": answers,
    }


# ---- listening -------------------------------------------------------------

def build_listening(doc, tid, n):
    answers = {str(k): norm_answer(v) for k, v in doc["answers"].items()}
    answer_nums = {int(k) for k in answers}

    # Reconstruct ordered text from passages + question_groups.
    stream_parts = list(doc.get("passages", []))
    for g in doc.get("question_groups", []):
        stream_parts.append(g.get("text", ""))
    text = "\n".join(stream_parts)

    # Standard 4 parts by canonical ranges; pull instructions where present.
    parts = []
    for idx, (lo, hi) in enumerate([(1, 10), (11, 20), (21, 30), (31, 40)], start=1):
        m = re.search(rf"Part\s*{idx}\s*:?\s*(Questions?[^\n]*)", text, re.I)
        parts.append({
            "number": idx,
            "instructions": clean(m.group(1)) if m else "",
            "questionRange": [lo, hi],
        })

    questions = parse_questions_from_text(text, answer_nums)
    audio_present = (V2 / "audio" / f"{n}_we.mp3").exists()
    return {
        "id": tid,
        "audioUrl": None,
        "localAudioPath": f"/audio/{tid}.mp3" if audio_present else None,
        "parts": parts,
        "questions": questions,
        "answerKey": answers,
    }


# ---- main ------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--copy-audio", action="store_true")
    args = ap.parse_args()

    assert V2.exists(), f"v2 folder not found at {V2}"

    # wipe old reading + listening
    for sec in ("reading", "listening"):
        d = CONTENT / sec
        if d.exists():
            for f in d.glob("*.json"):
                f.unlink()
        d.mkdir(parents=True, exist_ok=True)

    stats = {"reading": 0, "listening": 0, "audio": 0, "skipped": []}

    # READING
    rfiles = sorted(glob(str(V2 / "reading" / "*.json")))
    if args.limit:
        rfiles = rfiles[: args.limit]
    for f in rfiles:
        doc = json.load(open(f))
        if not doc.get("answers"):
            stats["skipped"].append(f"reading {doc.get('n')}: no answers")
            continue
        n = int(doc["n"])
        tid = f"{n:04d}"
        out = build_reading(doc, tid)
        json.dump(out, open(CONTENT / "reading" / f"{tid}.json", "w"),
                  ensure_ascii=False, indent=2)
        stats["reading"] += 1

    # LISTENING
    lfiles = sorted(glob(str(V2 / "listening_structured" / "*.json")))
    if args.limit:
        lfiles = lfiles[: args.limit]
    PUBLIC_AUDIO.mkdir(parents=True, exist_ok=True)
    for f in lfiles:
        doc = json.load(open(f))
        if not doc.get("answers"):
            stats["skipped"].append(f"listening {doc.get('n')}: no answers")
            continue
        n = int(doc["n"])
        tid = f"{n:04d}"
        out = build_listening(doc, tid, n)
        json.dump(out, open(CONTENT / "listening" / f"{tid}.json", "w"),
                  ensure_ascii=False, indent=2)
        stats["listening"] += 1
        if args.copy_audio:
            src = V2 / "audio" / f"{n}_we.mp3"
            if src.exists():
                shutil.copy(src, PUBLIC_AUDIO / f"{tid}.mp3")
                stats["audio"] += 1

    print(f"Reading written:   {stats['reading']}")
    print(f"Listening written: {stats['listening']}")
    print(f"Audio copied:      {stats['audio']}")
    if stats["skipped"]:
        print(f"Skipped {len(stats['skipped'])}: {stats['skipped'][:10]}")


if __name__ == "__main__":
    main()
