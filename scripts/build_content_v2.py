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
from datetime import datetime, timezone
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

# Source MP3s are named "{n}_we.mp3". Prefer v2/audio, fall back to the
# scraper's output dir at the repo root (ielts-crack/audio).
AUDIO_SRC = V2 / "audio"
if not (AUDIO_SRC.exists() and any(AUDIO_SRC.glob("*.mp3"))):
    for cand in (ROOT.parent / "audio", ROOT.parent.parent / "audio"):
        if cand.exists() and any(cand.glob("*.mp3")):
            AUDIO_SRC = cand
            break
print("AUDIO_SRC", AUDIO_SRC)

PUBLIC = ROOT / "public"
IMAGE_QTYPES = {"diagramLabel", "mapPlanLabelling", "flowChartCompletion", "tableCompletion"}
IMAGE_CUE = re.compile(
    r"label the (diagram|map|plan)|the (diagram|map|plan) below|on the (diagram|map|plan)|"
    r"map the places|flow[- ]?chart|complete the (diagram|flow)",
    re.I,
)


def local_images(section: str, tid: str) -> list[str]:
    """Web paths of any downloaded images for a test, sorted by image_N."""
    d = PUBLIC / f"{section}-img" / tid
    if not d.exists():
        return []
    files = sorted(p.name for p in d.iterdir()
                   if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"))
    return [f"/{section}-img/{tid}/{f}" for f in files]


# Authoritative image→question-range placement scraped from the archive.
IMG_PLACEMENT = {}
_pl_path = ROOT / "scripts" / "image_placement.json"
if _pl_path.exists():
    IMG_PLACEMENT = json.loads(_pl_path.read_text())


def attach_images(section: str, tid: str, questions: list, groups: list, group_key: str):
    """Attach a test's images to the right passage/part. Prefer the archive
    placement (each image's true question range); fall back to an order-based
    heuristic across the image-needing groups."""
    images = local_images(section, tid)
    if not images or not groups:
        return

    placement = (IMG_PLACEMENT.get(section, {}).get(tid) or {}).get("placement")
    if placement:
        have = {p.rsplit("/", 1)[-1]: p for p in images}
        for fname, rng in placement:
            path = have.get(fname)
            if not path:
                continue
            if rng:
                tgt = next((g for g in groups
                            if g[group_key][0] <= rng[0] <= g[group_key][1]), None)
            else:
                tgt = None
            tgt = tgt or groups[0]
            tgt.setdefault("images", []).append(path)
        return

    def score(g):
        lo, hi = g[group_key]
        best = 0
        for q in questions:
            if lo <= q["number"] <= hi:
                if q.get("type") in ("mapPlanLabelling", "diagramLabel"):
                    return 2
                blob = " ".join(str(q.get(k, "")) for k in ("instructions", "prompt", "stem"))
                if re.search(r"label the (map|diagram|plan)|the (map|diagram|plan) below",
                             blob, re.I):
                    best = 2
                elif q.get("type") in IMAGE_QTYPES:
                    best = max(best, 1)
        return best

    scored = [(g, score(g)) for g in groups]
    targets = [g for g, s in scored if s >= 2] or [g for g, s in scored if s >= 1]
    if not targets:
        targets = [max(groups, key=score)]

    if len(targets) == 1:
        targets[0]["images"] = list(images)
        return
    # one image per target in order; any extras append to the last target
    buckets = {id(g): [] for g in targets}
    for i, img in enumerate(images):
        buckets[id(targets[min(i, len(targets) - 1)])].append(img)
    for g in targets:
        if buckets[id(g)]:
            g["images"] = buckets[id(g)]

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
HEADER_RE = re.compile(r"Questions?\s+(\d+)\s*(?:and|to|or|through|[-–—~,&])\s*(\d+)|Question\s+(\d+)", re.I)


def classify(text: str):
    for typ, rx in INSTRUCTION_CUES.items():
        if rx.search(text):
            return typ
    return None


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def norm_blanks(s: str) -> str:
    """Dotted blank lines ('………', '....') → a single '____' placeholder."""
    return re.sub(r"(?:\.{2,}|…+)(?:\s*\.{2,}|\s*…+)*", " ____ ", s)


def tidy_prompt(s: str) -> str:
    s = clean(s)
    s = re.sub(r"^[\s.):,;…-]+", "", s)        # stray leading punctuation
    # trailing rubric clause that ran into the last item ("… Write NO MORE THAN …")
    s = re.sub(r"\s*(?:Write|Choose|Answer)\s+(?:NO MORE THAN|ONE WORD|FIVE|THREE|TWO)\b.*$", "", s, flags=re.I)
    s = re.sub(r"____(?:\s*[.,;:]+)+", "____", s)    # drop punctuation glued to a blank
    s = re.sub(r"(?:\s*____){2,}", " ____", s)       # collapse repeated blanks
    return s.strip()


def parse_mcq(chunk: str, lo: int, hi: int):
    """Extract MC questions. Each numbered item ('1 stem A … B … C … D …') is
    split first, then its options. Items are delimited by 'N ' markers (this
    dataset rarely uses 'N.'), so reuse split_items rather than a monolithic
    regex. Returns only the items that look like MCQs; caller falls back."""
    items = split_items(chunk, lo, hi)
    out = []
    for n in range(lo, hi + 1):
        it = items.get(n)
        if not it or not it["after"]:
            continue
        opts, ostart = parse_letter_options(it["after"])
        if len(opts) < 2:
            continue
        stem = clean(it["after"][:ostart])
        out.append({
            "number": n, "type": "multipleChoice",
            "stem": stem or f"Question {n}",
            "options": [{"letter": o["letter"], "text": o["text"]} for o in opts],
        })
    return out


# A question marker: an optionally-parenthesised 1–2 digit number sitting on a
# token boundary. The leading `(?<!\d)` stops us matching the interior of long
# runs like phone numbers ("01273512634") or years.
ITEM_MARK = re.compile(r"(?<!\d)(\()?\s*(\d{1,2})\s*(\))?(?=[.\s):]|$)")
# A line that is pure rubric/instruction, never per-item content.
INSTR_LINE = re.compile(
    r"^\s*(Questions?\s+\d|Part\s+\d|You should spend|Complete\b|Write\b|Choose\b|"
    r"Answer the\b|Label\b|Match\b|Do the following|In boxes|Use the information|NB\b)",
    re.I,
)
# Self-references to question/answer-sheet numbers ("Questions 25-26",
# "in boxes 25 and 26") — NOT per-item markers; ignore them when locating items.
REF_RE = re.compile(
    r"(?:in\s+)?(?:boxes?|questions?|passages?|sections?|paragraphs?|lines?)\s+\d+"
    r"(?:\s*(?:and|or|to|[-–,&])\s*\d+)?",
    re.I,
)
# Instruction that runs inline (no newline) up to a recognisable end cue.
HEADER_SENT = re.compile(
    r"^\s*Questions?\s+.*?"
    r"(for each answer\.?|write:?|below[.:]?|following[^.]*\.|letters?\s+[A-J](?:\s*[-–]\s*[A-J])?)",
    re.I,
)


def strip_header(chunk: str, lo: int | None = None, hi: int | None = None) -> str:
    """Drop leading rubric lines ('Questions N–M', 'Complete the notes…',
    'Write NO MORE THAN…') so they never leak into per-item prompts — they
    already live on the part's `instructions`. A rubric line that also carries
    the group's items (the scraper often flattens them onto one line) is kept,
    so the items survive."""
    lines = chunk.split("\n")
    i = 0
    while i < len(lines) and INSTR_LINE.match(lines[i]):
        if lo is not None:
            rest = REF_RE.sub(" ", lines[i])  # ignore "Questions/boxes N–M" self-refs
            if first_item_offset(rest, lo, hi) >= 0:
                break
        i += 1
    body = "\n".join(lines[i:]) if i else chunk
    # Same-line rubric (instruction and items share one line, no newline).
    m = HEADER_SENT.match(body)
    return body[m.end():] if m else body


def split_items(chunk: str, lo: int, hi: int) -> dict:
    """Locate each question number lo..hi in order and return, per number, the
    text immediately before it (the label, for inline `(N)` blanks) and after it
    (the statement/sentence, for leading `N.` items)."""
    body = norm_blanks(strip_header(chunk, lo, hi))
    expected = lo
    marks = []  # (n, start, end, is_paren)
    for m in ITEM_MARK.finditer(body):
        if int(m.group(2)) == expected:
            marks.append((expected, m.start(), m.end(), bool(m.group(1))))
            expected += 1
            if expected > hi:
                break

    out: dict[int, dict] = {}
    for i, (n, s, e, paren) in enumerate(marks):
        prev_end = marks[i - 1][2] if i > 0 else 0
        next_start = marks[i + 1][1] if i + 1 < len(marks) else len(body)
        after = clean(body[e:next_start])
        after = re.sub(r"^[.):\s]+", "", after)                 # leftover "." after "1."
        after = re.sub(r"\s*Part\s+\d+\s*:?\s*$", "", after, flags=re.I)  # trailing part header
        out[n] = {"before": clean(body[prev_end:s]), "after": after, "paren": paren}
    return out


def _label_tail(text: str, limit: int = 120) -> str:
    """Keep the trailing, most-relevant part of a label/lead-in."""
    if len(text) <= limit:
        return text
    cut = text[-limit:]
    sp = cut.find(" ")
    return "… " + (cut[sp + 1:] if sp != -1 else cut)


def strip_letter_bank(s: str):
    """A word-bank ('A air B ash C earth …') can leak into the first item's
    prompt. Split it off: returns (label_without_bank, [options]) when a
    sequential A,B,C… run of ≥3 short options leads the text, else (s, [])."""
    t = s.lstrip()
    expected, idx = 0, 0
    opts = []
    while True:
        letter = chr(ord("A") + expected)
        m = re.match(rf"{letter}\s+", t[idx:])
        if not m:
            break
        start = idx + m.end()
        nxt = chr(ord("A") + expected + 1)
        # Prefer the next sequential letter as the delimiter (handles multi-word
        # capitalised options like names); only for the LAST option fall back to
        # a bullet / blank / capitalised label start.
        mn = re.search(rf"\s+(?={nxt}\s)", t[start:])
        if mn:
            end = start + mn.start()
        else:
            m2 = re.search(r"\s*[•\n]|\s+____|\s+(?=[A-Z][a-z]{2,}\s)", t[start:])
            end = start + (m2.start() if m2 else len(t) - start)
        opts.append({"letter": letter, "text": clean(t[start:end])})
        idx = end
        expected += 1
        sk = re.match(r"\s+", t[idx:])
        if sk:
            idx += sk.end()
        if not re.match(rf"{chr(ord('A') + expected)}\s", t[idx:]):
            break
    if expected >= 3:
        return t[idx:].lstrip(" .–-•:"), opts
    return s, []


def trim_tail(s: str) -> str:
    """The last item in a group runs to the chunk end and can absorb the next
    passage's prose. Cut at a lettered-paragraph run ('A … B … C …') and, when
    that fires, also drop a trailing sentence/title that leaked in."""
    s = clean(s)
    opts, opt_start = parse_letter_options(s)
    overflow = opt_start > 0 and len(opts) >= 3
    if overflow:
        s = clean(s[:opt_start])
    if overflow or len(s) > 180:
        m = re.search(r"[.?!]\s+\S", s)
        if m:
            s = s[: m.start() + 1]
    return s.strip()


def parse_statements(chunk: str, lo: int, hi: int, typ: str):
    items = split_items(chunk, lo, hi)
    out = []
    for n in range(lo, hi + 1):
        it = items.get(n)
        statement = tidy_prompt(trim_tail(it["after"])) if it else ""
        out.append({"number": n, "type": typ, "statement": statement or f"Statement {n}"})
    return out


def parse_gapfills(chunk: str, lo: int, hi: int, typ: str, word_limit):
    items = split_items(chunk, lo, hi)
    out = []
    for n in range(lo, hi + 1):
        it = items.get(n)
        if not it:
            prompt = f"Question {n}"
        elif it["paren"]:
            # inline blank: label precedes the (N) marker
            prompt = tidy_prompt(_label_tail(it["before"]) + " ____")
        else:
            # leading-number item: the sentence/question follows the marker
            prompt = tidy_prompt(trim_tail(it["after"])) or tidy_prompt(_label_tail(it["before"]) + " ____")
        q = {"number": n, "type": typ, "prompt": prompt}
        if word_limit:
            q["wordLimit"] = word_limit
        out.append(q)
    return out


LETTER_MARK = re.compile(r"(?<![A-Za-z(])([A-J])[.)\s]")
BANK_TYPES = {"gapFill", "summaryCompletion", "matchFeatures", "matchHeadings",
              "matchEndings", "matchInfo"}
# Marker for an answer whose question was never published in the source page
# (confirmed absent from all archive snapshots). Such tests are hidden.
SOURCE_MISSING_NOTE = ("This question was not included in the source text; "
                       "only its answer is available (shown in review).")


def is_incomplete(out: dict) -> bool:
    """True if any question is a source-missing placeholder."""
    return any(
        q.get("groupId") == "qfallback"
        or (q.get("instructions") or "") == SOURCE_MISSING_NOTE
        for q in out["questions"]
    )


_IMG_NEED_CUE = re.compile(r"label the (map|diagram|plan)|the (map|diagram|plan) below|"
                           r"map the places", re.I)


def missing_options(out: dict, group_key: str) -> bool:
    """True if a question can't be answered because its options aren't shown: a
    match-features/endings question with no bank, or a multiple-choice question
    with image-less, mostly-blank options."""
    questions = out["questions"]
    for g in out[group_key]:
        lo, hi = g["questionRange"]
        for q in questions:
            if not (lo <= q["number"] <= hi):
                continue
            if q.get("type") in ("matchFeatures", "matchEndings") and not q.get("bank"):
                return True
            opts = q.get("options") or []
            if (q.get("type") == "multipleChoice" and opts and not g.get("images")
                    and sum(1 for o in opts if not o.get("text", "").strip()) >= max(2, len(opts) // 2)):
                return True
    return False


def missing_image(out: dict, group_key: str) -> bool:
    """True if a group needs an image but has none, so its questions can't be
    answered: a diagram/map/plan-labelling question, or a multiple-choice
    question whose options are images (all option texts blank)."""
    questions = out["questions"]
    for g in out[group_key]:
        lo, hi = g["questionRange"]
        if g.get("images"):
            continue
        for q in questions:
            if not (lo <= q["number"] <= hi):
                continue
            blob = " ".join(str(q.get(k, "")) for k in ("instructions", "prompt", "stem"))
            if q.get("type") in ("mapPlanLabelling", "diagramLabel") or _IMG_NEED_CUE.search(blob):
                return True
            opts = q.get("options")
            if (q.get("type") == "multipleChoice" and opts
                    and all(not o.get("text", "").strip() for o in opts)):
                return True
    return False


def parse_letter_options(text: str):
    """Parse a sequential 'A … B … C …' option list. Returns (options, start)
    where start is the char offset of 'A' (or -1 if there is no real list)."""
    marks = []
    for m in LETTER_MARK.finditer(text):
        if m.group(1) == chr(ord("A") + len(marks)):
            marks.append((m.group(1), m.start(), m.end()))
    if len(marks) < 3:
        return [], -1
    opts = []
    for i, (letter, _s, e) in enumerate(marks):
        nxt = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        opts.append({"letter": letter, "text": clean(text[e:nxt])})
    return opts, marks[0][1]


ROMANS = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
          "xi", "xii", "xiii", "xiv", "xv", "xvi", "xvii", "xviii"]


def _cut_heading_junk(text: str) -> str:
    """Trim example/paragraph-item text that leaks into a heading."""
    text = re.split(
        r"\s+Example\b|"
        r"\s+(?:\d{1,2}[.)]?\s+)?(?:Section|Paragraph)\s+(?:[A-Z](?![a-z])|\d{1,2})\b",
        text, flags=re.I)[0]
    if len(text) > 140:
        cut = re.search(r"[.?!]\s", text)
        text = text[: cut.start() + 1] if cut else text[:140]
    return re.sub(r"\s+\d+\.?\s*$", "", text).strip()


def parse_roman_headings(chunk: str):
    """Parse a 'List of Headings: i … ii … iii …' block into [{number, text}]."""
    # Pick the heading-list anchor that actually starts the list (immediately
    # followed by 'i'), not the rubric phrase "from the list of headings below".
    anchors = list(re.finditer(r"(?:list of|paragraph)\s+headings", chunk, re.I))
    seg = chunk
    for a in anchors:
        if re.match(r"\s*[:\-–—]?\s*i[.)\s]", chunk[a.end():], re.I):
            seg = chunk[a.end():]
            break
    else:
        if anchors:
            seg = chunk[anchors[-1].end():]
    marks = []
    pos = 0
    for rom in ROMANS:
        # the trailing lookahead rejects range references like "i – ix" / "i to ix"
        mm = re.compile(rf"(?<![A-Za-z]){rom}(?![A-Za-z])[.)]?\s+(?![–\-]|(?:to|or)\s)",
                        re.I).search(seg, pos)
        if not mm:
            break
        marks.append((rom, mm.start(), mm.end()))
        pos = mm.end()
    headings = []
    for j, (rom, _s, e) in enumerate(marks):
        nxt = marks[j + 1][1] if j + 1 < len(marks) else len(seg)
        headings.append({"number": rom, "text": _cut_heading_junk(clean(seg[e:nxt]))})
    return headings


def parse_match_headings(chunk: str, lo: int, hi: int):
    headings = parse_roman_headings(chunk)
    if len(headings) < 2:  # letter-labelled headings ("Headings A x B y …")
        m = (re.search(r"Paragraph Headings", chunk, re.I)
             or re.search(r"List of Headings", chunk, re.I))
        seg = chunk[m.end():] if m else chunk
        opts, _ = parse_letter_options(seg)
        headings = [{"number": o["letter"], "text": _cut_heading_junk(o["text"])} for o in opts]
    # Paragraph labels can be letters (A-H) or numbers (1-7).
    m = re.search(r"paragraphs?\s+([A-Za-z]|\d+)\s*[-–—]\s*([A-Za-z]|\d+)", chunk)
    labels = None
    if m:
        a, b = m.group(1), m.group(2)
        if a.isdigit() and b.isdigit():
            labels = [str(x) for x in range(int(a), int(b) + 1)]
        elif len(a) == 1 and len(b) == 1 and a.isalpha() and b.isalpha():
            labels = [chr(c) for c in range(ord(a.upper()), ord(b.upper()) + 1)]
    out = []
    for i, n in enumerate(range(lo, hi + 1)):
        pl = labels[i] if labels and i < len(labels) else chr(ord("A") + i)
        out.append({"number": n, "type": "matchHeadings",
                    "paragraphLetter": pl, "headings": headings})
    return out, headings


def first_item_offset(body: str, lo: int, hi: int) -> int:
    expected = lo
    for m in ITEM_MARK.finditer(body):
        if int(m.group(2)) == expected:
            return m.start()
    return -1


def group_meta(chunk: str, lo: int, hi: int):
    """Shared rubric + option bank for a question group (so list/diagram/
    choose-letter questions that have no per-item text still make sense)."""
    body = strip_header(chunk, lo, hi)
    rubric = re.sub(r"^\s*Questions?\s+\d+\s*(?:and|to|[-–,&]\s*\d+)?\s*", "",
                    clean(chunk[: len(chunk) - len(body)]), flags=re.I).strip()
    opts, opt_start = parse_letter_options(body)
    # The last option often swallows trailing prose (no letter to bound it):
    # trim each option at its first sentence end when long.
    def _opt(s):
        s = clean(s)
        if len(s) > 180:
            m = re.search(r"\.\s", s)
            s = s[: m.start() + 1] if m else s[:180]
        return s
    opts = [{"letter": o["letter"], "text": _opt(o["text"])} for o in opts]
    # Long "options" are really lettered passage paragraphs (A, B, C…) that the
    # chunk ran into — not a real answer bank. We still use their start as the
    # cut-off so they don't leak into the instruction text.
    bank = [] if (opts and max(len(o["text"]) for o in opts) > 220) else opts
    item_start = first_item_offset(body, lo, hi)
    cut = min([x for x in (opt_start, item_start, len(body)) if x >= 0])
    asking = clean(body[:cut])
    if len(asking) > 300:  # safety net against runaway passage prose
        asking = asking[:300].rsplit(" ", 1)[0] + "…"
    instruction = clean(f"{rubric} {asking}")
    return instruction, bank


def parse_questions_from_text(text: str, answer_nums: set[int]):
    """
    Walk a text stream, segment on Questions N-M headers, classify each chunk,
    and emit typed questions. Guarantee every answer number is covered.
    """
    # Real group headers are capitalised ("Questions 11-15"); lowercase
    # "…next to questions 11-15" is a back-reference and must not split items.
    headers = [h for h in HEADER_RE.finditer(text) if h.group(0)[:1] == "Q"]
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

        match_headings = None
        if typ == "multipleChoice":
            qs = parse_mcq(chunk, lo, hi) or parse_gapfills(chunk, lo, hi, "gapFill", word_limit)
        elif typ == "matchHeadings":
            qs, match_headings = parse_match_headings(chunk, lo, hi)
        elif typ in ("tfng", "ynng"):
            qs = parse_statements(chunk, lo, hi, typ)
        elif typ in ("sentenceCompletion", "summaryCompletion", "noteCompletion",
                     "tableCompletion", "formCompletion", "flowChartCompletion",
                     "shortAnswer", "diagramLabel", "mapPlanLabelling",
                     "matchInfo", "matchFeatures", "matchHeadings"):
            qs = parse_gapfills(chunk, lo, hi, typ, word_limit)
        else:
            qs = parse_gapfills(chunk, lo, hi, "gapFill", word_limit)

        # Backfill numbers the primary parser missed (e.g. a summary group whose
        # chunk was misclassified because a header-less question polluted it):
        # give them a best-effort prompt from the chunk so they still inherit the
        # group's instruction below instead of becoming context-less fallbacks.
        covered = {q["number"] for q in qs}
        missing = [n for n in range(lo, hi + 1) if n not in covered]
        if missing:
            bf_type = typ if typ in (
                "sentenceCompletion", "summaryCompletion", "noteCompletion",
                "tableCompletion", "formCompletion", "flowChartCompletion",
                "shortAnswer", "diagramLabel", "mapPlanLabelling",
            ) else "gapFill"
            qs += [q for q in parse_gapfills(chunk, lo, hi, bf_type, word_limit)
                   if q["number"] in missing]

        instruction, opts = group_meta(chunk, lo, hi)
        # A word-bank ('A air B ash …') that leaked into a prompt: strip it out
        # and reuse it as the group's bank (covers flow-chart/box completions).
        inline_bank = []
        for q in qs:
            key = "prompt" if "prompt" in q else ("statement" if "statement" in q else None)
            if not key:
                continue
            label, b = strip_letter_bank(q[key])
            if b:
                inline_bank = b
                q[key] = label or f"Question {q['number']}"
        bank = inline_bank or opts  # inline bank is cleanly delimited; prefer it
        # Match-headings: the roman-numeral list IS the answer bank and feeds the
        # dropdown; show only the rubric (not the list) as the instruction.
        if match_headings is not None:
            bank = [{"letter": h["number"], "text": h["text"]} for h in match_headings]
            cut = re.search(r"List of Headings", instruction or "", re.I)
            if cut:
                instruction = instruction[: cut.start()].strip()
        for q in qs:
            q["groupId"] = group_id
            if instruction:
                q["instructions"] = instruction
            # Attach the A–J option bank to types whose answers ARE letters / a
            # word list (choose-letters, summary-with-list, matching, flow-box);
            # an inline bank is reliable enough to attach to any type.
            if bank and (match_headings is not None or inline_bank
                         or q["type"] in BANK_TYPES) and "bank" not in q:
                q["bank"] = bank
            if 0 < q["number"] and q["number"] not in questions:
                questions[q["number"]] = q

    # Coverage guarantee: an answer number with no parsed group means that
    # question was never published in the source page (confirmed absent from all
    # archive snapshots too). Keep it answerable but say so.
    for n in answer_nums:
        if n not in questions:
            questions[n] = {
                "number": n, "type": "gapFill", "groupId": "qfallback",
                "prompt": f"Question {n}",
                "instructions": SOURCE_MISSING_NOTE,
            }
    # Any question still left as a bare context-less placeholder (e.g. a group
    # header with an empty body) gets the same honest note.
    for q in questions.values():
        text = q.get("prompt") or q.get("statement") or ""
        if re.fullmatch(r"(Question|Statement) \d+", text) and not (
            q.get("instructions") or q.get("bank")
        ):
            q["instructions"] = SOURCE_MISSING_NOTE
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

    joined = "\n".join(content)
    questions = parse_questions_from_text(joined, answer_nums)
    max_q = max([q["number"] for q in questions] + list(answer_nums), default=40)

    # Map each passage to its question range, mirroring the original 3-part
    # layout: a passage owns the questions whose group headers fall after its
    # text starts and before the next passage's text.
    groups = sorted(
        (h.start(), int(h.group(3) or h.group(1)))
        for h in HEADER_RE.finditer(joined)
        if h.group(0)[:1] == "Q"
    )

    def first_q_after(offset):
        for off, lo in groups:
            if off >= offset:
                return lo
        return None

    p_offsets = [joined.find(run[0][:40]) for run in top]
    bounds = [first_q_after(o) for o in p_offsets]
    if bounds and bounds[0] not in (None, 1):
        bounds[0] = 1  # passage 1 always starts at question 1
    # Fall back to an even split if positional mapping is unreliable.
    if len(top) != 3 or any(b is None for b in bounds) or bounds != sorted(bounds) or len(set(bounds)) != len(bounds):
        step = max_q / max(len(top), 1)
        bounds = [round(i * step) + 1 for i in range(len(top))]

    passages = []
    for i, run in enumerate(top):
        lo = bounds[i]
        hi = (bounds[i + 1] - 1) if i + 1 < len(bounds) else max_q
        passages.append({
            "number": i + 1,
            "title": f"Passage {i + 1}",
            "questionRange": [lo, hi],
            "bodyHtml": "".join(f"<p>{clean(p)}</p>" for p in run),
        })
    if not passages:
        passages = [{"number": 1, "title": "Passage 1", "questionRange": [1, max_q],
                     "bodyHtml": "".join(f"<p>{clean(b)}</p>" for b in content)}]

    # Safety net: the last item of a group can absorb the following passage's
    # prose. We know the passage texts here, so cut a question's text wherever a
    # passage body begins inside it.
    prefixes = []
    for p in passages:
        body = clean(re.sub(r"<[^>]+>", " ", p["bodyHtml"]))
        if len(body) > 30:
            prefixes.append(body[:35])
    for q in questions:
        key = "statement" if "statement" in q else "prompt"
        t = q.get(key) or ""
        for pref in prefixes:
            i = t.find(pref[:25])
            if i > 12:
                t = clean(t[:i])
        t = re.sub(r"\s+Cambridge IELTS Tests.*$", "", t)  # cross-test boilerplate
        if t and t != (q.get(key) or ""):
            q[key] = t

    attach_images("reading", tid, questions, passages, "questionRange")
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
    attach_images("listening", tid, questions, parts, "questionRange")
    audio_present = (AUDIO_SRC / f"{n}_we.mp3").exists()
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

    stats = {"reading": 0, "listening": 0, "audio": 0,
             "hidden_no_audio": 0, "hidden_incomplete": 0,
             "hidden_missing_image": 0, "hidden_no_options": 0, "skipped": []}
    hidden = {"reading": [], "listening": []}  # {id, reasons, missing} report

    # READING
    rfiles = sorted(glob(str(V2 / "reading" / "*.json")))
    if args.limit:
        rfiles = rfiles[: args.limit]
    cat_reading, cat_listening = [], []
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
        # Hide tests with source-missing questions or a diagram/map question whose
        # image we can't serve. JSON stays on disk so they return once fixed.
        reasons = []
        if is_incomplete(out):
            reasons.append("source-missing-questions"); stats["hidden_incomplete"] += 1
        if missing_image(out, "passages"):
            reasons.append("missing-image"); stats["hidden_missing_image"] += 1
        if missing_options(out, "passages"):
            reasons.append("no-options"); stats["hidden_no_options"] += 1
        if reasons:
            missing = [q["number"] for q in out["questions"]
                       if (q.get("instructions") or "") == SOURCE_MISSING_NOTE]
            hidden["reading"].append({"id": tid, "reasons": reasons, "missing": missing})
            continue
        cat_reading.append({"id": tid, "flags": {"questions": len(out["questions"])}})

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
        # Hide a listening test if it has no audio OR has source-missing question
        # groups. JSON stays on disk so it returns to the catalog once fixed.
        reasons = []
        if not out["localAudioPath"]:
            reasons.append("no-audio"); stats["hidden_no_audio"] += 1
        if is_incomplete(out):
            reasons.append("source-missing-questions"); stats["hidden_incomplete"] += 1
        if missing_image(out, "parts"):
            reasons.append("missing-image"); stats["hidden_missing_image"] += 1
        if missing_options(out, "parts"):
            reasons.append("no-options"); stats["hidden_no_options"] += 1
        if reasons:
            missing = [q["number"] for q in out["questions"]
                       if (q.get("instructions") or "") == SOURCE_MISSING_NOTE]
            hidden["listening"].append({"id": tid, "reasons": reasons, "missing": missing})
        else:
            cat_listening.append({
                "id": tid,
                "flags": {"hasAudio": True, "hasAudioUrl": bool(out["audioUrl"])},
            })
        if args.copy_audio:
            src = AUDIO_SRC / f"{n}_we.mp3"
            if src.exists():
                shutil.copy(src, PUBLIC_AUDIO / f"{tid}.mp3")
                stats["audio"] += 1

    # Rebuild the catalog for reading+listening; keep writing+speaking as-is.
    index_path = CONTENT / "index.json"
    existing = json.load(open(index_path)) if index_path.exists() else {}
    catalog = {
        "reading": sorted(cat_reading, key=lambda e: e["id"]),
        "listening": sorted(cat_listening, key=lambda e: e["id"]),
        "writing": existing.get("writing", []),
        "speaking": existing.get("speaking", []),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }
    json.dump(catalog, open(index_path, "w"), ensure_ascii=False, indent=2)

    # Report of hidden tests (the "mark"): which ids, why, and which questions.
    hidden["generatedAt"] = datetime.now(timezone.utc).isoformat()
    json.dump(hidden, open(CONTENT / "_hidden.json", "w"), ensure_ascii=False, indent=2)

    print(f"Reading written:   {stats['reading']}")
    print(f"Listening written: {stats['listening']}")
    print(f"Audio copied:      {stats['audio']}")
    print(f"Hidden — no audio: {stats['hidden_no_audio']}, "
          f"incomplete (source-missing): {stats['hidden_incomplete']}, "
          f"missing-image: {stats['hidden_missing_image']}, "
          f"no-options: {stats['hidden_no_options']}")
    print(f"Hidden tests: reading {len(hidden['reading'])}, "
          f"listening {len(hidden['listening'])} → content/_hidden.json")
    print(f"Catalog: reading {len(cat_reading)}, listening {len(cat_listening)}, "
          f"writing {len(catalog['writing'])}, speaking {len(catalog['speaking'])}")
    if stats["skipped"]:
        print(f"Skipped {len(stats['skipped'])}: {stats['skipped'][:10]}")


if __name__ == "__main__":
    main()
