#!/usr/bin/env python3
"""
Builds content/*.json files from the scraped HTML + DOCX in ../Tests/.

This is a one-shot ETL: run once when content changes. Outputs:

    content/reading/{NNNN}.json   ReadingTest
    content/listening/{NNNN}.json ListeningTest
    content/writing/{NNNN}.json   WritingTest
    content/speaking/{NNNN}.json  SpeakingTest
    content/index.json            Catalog

The parser is tolerant: when a question group can't be classified, it falls
back to type "unsupported" and stores the raw HTML so the UI can still render
something. Successfully classified questions emit a clean typed JSON.

Usage:
    python3 scripts/build_content.py           # full build
    python3 scripts/build_content.py --limit 5 # parse only 5 tests of each section
"""

import argparse
import json
import os
import re
import shutil
import sys
from glob import glob
from pathlib import Path
from typing import Any

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:
    print("Installing beautifulsoup4...", file=sys.stderr)
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install",
                           "beautifulsoup4", "lxml", "python-docx",
                           "--break-system-packages", "-q"])
    from bs4 import BeautifulSoup, NavigableString, Tag

try:
    from docx import Document
except ImportError:
    Document = None  # speaking parser will skip if unavailable

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT.parent / "Tests"
CONTENT_DIR = ROOT / "content"
PUBLIC_DIR = ROOT / "public"


# ---------- helpers ----------------------------------------------------------

ADS_SELECTORS = [
    "script", "ins.adsbygoogle", ".addtoany_share_save_container",
    "div[id^='container-']", "input[type='hidden']", "button[id^='bg-showmore']",
]


def clean(soup_or_str: Any) -> str:
    """Return the trimmed text content; collapse whitespace."""
    if isinstance(soup_or_str, str):
        s = soup_or_str
    else:
        s = soup_or_str.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", s).strip()


def strip_ads(soup: BeautifulSoup) -> None:
    for sel in ADS_SELECTORS:
        for el in soup.select(sel):
            el.decompose()


def pad_id(n: int) -> str:
    return f"{n:04d}"


# ---------- answer-key extraction --------------------------------------------

def extract_answer_key(html: str) -> dict[str, str | list[str]]:
    """
    The HTML pages embed answers in <div id="bg-showmore-hidden-..."> as a
    series of `N. answer<br>` lines. Return {"1": "300", "2": "sunshade", ...}.
    """
    soup = BeautifulSoup(html, "lxml")
    holder = soup.find("div", id=re.compile(r"^bg-showmore-hidden-"))
    if not holder:
        return {}
    raw = holder.get_text("\n", strip=True)
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    out: dict[str, str | list[str]] = {}
    for line in raw.split("\n"):
        m = re.match(r"^\s*(\d+)\s*[.):]\s*(.+?)\s*$", line)
        if not m:
            continue
        n, ans = m.group(1), m.group(2)
        # multi-letter answers like "B, C" or "B C" or "B/C"
        if re.match(r"^([A-H](\s*[,/]\s*[A-H])+)$", ans):
            parts = re.split(r"\s*[,/]\s*", ans)
            out[n] = [p.upper() for p in parts]
        else:
            out[n] = ans
    return out


# ---------- question parsing -------------------------------------------------

GROUP_HEADER_RE = re.compile(
    r"Questions?\s+(\d+)\s*(?:–|-|to|–|and)\s*(\d+)?",
    re.I,
)
INSTRUCTION_CUES = {
    # Order matters: more specific cues first.
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
    "matchEndings": re.compile(r"sentence\s+(beginnings|halves)|complete each sentence", re.I),
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


def classify(instruction_text: str) -> str | None:
    for typ, rx in INSTRUCTION_CUES.items():
        if rx.search(instruction_text):
            return typ
    return None


def parse_mcq(block_html: str, q_start: int) -> list[dict]:
    """Parse a multiple-choice block. Returns one MCQ dict per question found."""
    soup = BeautifulSoup(block_html, "lxml")
    text = soup.get_text("\n")
    questions: list[dict] = []
    # split into "11. stem ... A ... B ... C" chunks.
    pat = re.compile(
        r"(\d+)\.\s*(.+?)\n\s*A[.)\s]\s*(.+?)\n\s*B[.)\s]\s*(.+?)\n\s*C[.)\s]\s*(.+?)(?=\n\s*\d+\.\s|$)",
        re.S,
    )
    for m in pat.finditer(text):
        n = int(m.group(1))
        if n < q_start:
            continue
        questions.append({
            "number": n,
            "type": "multipleChoice",
            "stem": clean(m.group(2)),
            "options": [
                {"letter": "A", "text": clean(m.group(3))},
                {"letter": "B", "text": clean(m.group(4))},
                {"letter": "C", "text": clean(m.group(5))},
            ],
        })
    return questions


def parse_statements(block_html: str, q_range: tuple[int, int], typ: str) -> list[dict]:
    """Parse TFNG/YNNG-style numbered statements `1 <stmt>` to `8 <stmt>`."""
    soup = BeautifulSoup(block_html, "lxml")
    text = soup.get_text("\n")
    lo, hi = q_range
    items: list[dict] = []
    pat = re.compile(r"(?<![A-Za-z])(\d+)[\s.)]+([^\n]+)")
    for m in pat.finditer(text):
        n = int(m.group(1))
        if lo <= n <= hi:
            items.append({
                "number": n,
                "type": typ,
                "statement": clean(m.group(2)),
            })
    return items


def parse_gap_fills(block_html: str, q_range: tuple[int, int], typ: str,
                    word_limit: str | None) -> list[dict]:
    """Generic gap-fill: render the block text and replace `(N)<input>` with
    a token <<BLANK:N>>. The whole block becomes the `prompt`. We split per
    question by anchor.
    """
    soup = BeautifulSoup(block_html, "lxml")
    # replace inputs with token using prior number heuristic
    txt = soup.get_text(" ", strip=True)
    txt = re.sub(r"\s+", " ", txt)
    lo, hi = q_range
    qs: list[dict] = []
    for n in range(lo, hi + 1):
        # find "(N)" or "N." pattern; capture ~120 chars of context around it
        m = re.search(rf"\(?\b{n}\)?[.:\s]", txt)
        if not m:
            continue
        start = max(0, m.start() - 60)
        end = min(len(txt), m.start() + 120)
        snippet = txt[start:end].strip()
        qs.append({
            "number": n,
            "type": typ,
            "prompt": snippet,
            **({"wordLimit": word_limit} if word_limit else {}),
        })
    return qs


def parse_match_headings(block_html: str, q_range: tuple[int, int],
                         passage_letters_hint: list[str]) -> list[dict]:
    """Headings list + paragraph letters."""
    soup = BeautifulSoup(block_html, "lxml")
    text = soup.get_text("\n")
    headings: list[dict] = []
    for m in re.finditer(r"(?<![a-z])(i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii|xiii|xiv|xv)\.?\s+([^\n]+)", text):
        headings.append({"number": m.group(1), "text": clean(m.group(2))})
    qs: list[dict] = []
    lo, hi = q_range
    # paragraph letter for each question — fall back to A, B, C, ...
    letters = passage_letters_hint or [chr(65 + i) for i in range(hi - lo + 1)]
    for idx, n in enumerate(range(lo, hi + 1)):
        qs.append({
            "number": n,
            "type": "matchHeadings",
            "paragraphLetter": letters[idx] if idx < len(letters) else "",
            "headings": headings,
        })
    return qs


# ---------- passage extraction (Reading) ------------------------------------

PASSAGE_HEADER_RE = re.compile(
    r"READING PASSAGE\s+(\d+)|Passage\s+(\d+)", re.I
)


def split_reading_into_passages(soup: BeautifulSoup) -> list[dict]:
    """
    Reading HTML usually contains 3 passages followed by question blocks.
    We split where we see Questions 1-… , 14-… , 27-… (the canonical IELTS
    question ranges). Everything before "Questions 1" is passage 1.
    """
    html = str(soup)
    # find anchor positions for question blocks 1, 14, 27
    anchors: list[int] = []
    for n in (1, 14, 27):
        m = re.search(rf"Questions?\s+{n}\b", html)
        if m:
            anchors.append(m.start())
    passages: list[dict] = []
    if not anchors:
        return passages
    # 3 chunks: before q1, between q-blocks
    starts = [0] + anchors[:-1]
    ends = anchors
    if len(anchors) >= 2:
        # passage 2 sits between q-blocks? actually in this corpus passages
        # are bunched together at the top. Use a simpler approach: take
        # everything before Questions 1 as the entire 3 passages, then try
        # to split on bold/h2 titles.
        pass
    full_body = html[:anchors[0]]
    body_soup = BeautifulSoup(full_body, "lxml")
    titles = body_soup.find_all(["h2", "h3"])
    if len(titles) >= 3:
        # Split by titles found in the body
        sections: list[tuple[str, str]] = []
        for i, t in enumerate(titles[:3]):
            title_text = clean(t)
            after = "".join(str(s) for s in t.next_siblings)
            # bound by next title
            sections.append((title_text, after))
        # crude: just take the full body for passage 1, leave others empty
        for i in range(3):
            passages.append({
                "number": i + 1,
                "title": sections[i][0] if i < len(sections) else f"Passage {i + 1}",
                "bodyHtml": full_body if i == 0 else "",
            })
    else:
        # one big passage; UI shows whole body for passage 1
        passages.append({
            "number": 1,
            "title": clean(body_soup.find("h2") or body_soup.find("h3") or "Passage 1"),
            "bodyHtml": full_body,
        })
    return passages


# ---------- top-level parsers ------------------------------------------------

def parse_reading_html(html: str, test_id: str) -> dict | None:
    soup = BeautifulSoup(html, "lxml")
    strip_ads(soup)
    answer_key = extract_answer_key(html)
    passages = split_reading_into_passages(soup)
    questions = parse_question_blocks(soup, source="reading")
    if not answer_key or not questions:
        return None
    return {
        "id": test_id,
        "variant": "academic",
        "source": "html",
        "passages": passages,
        "questions": questions,
        "answerKey": answer_key,
    }


def parse_listening_html(html: str, test_id: str) -> dict | None:
    soup = BeautifulSoup(html, "lxml")
    audio_tag = soup.find("audio")
    audio_url = None
    if audio_tag and audio_tag.get("src"):
        src = audio_tag["src"]
        audio_url = "https:" + src if src.startswith("//") else src
    strip_ads(soup)
    answer_key = extract_answer_key(html)
    if not answer_key:
        return None
    # 4 parts each spanning a question range. Identify part boundaries by
    # "Part 1: Questions A-B" headers.
    text = soup.get_text("\n", strip=True)
    parts: list[dict] = []
    for m in re.finditer(r"Part\s+(\d)\s*:?\s*Questions?\s+(\d+)\s*[\-–to]+\s*(\d+)", text):
        parts.append({
            "number": int(m.group(1)),
            "instructions": "",
            "questionRange": [int(m.group(2)), int(m.group(3))],
        })
    if len(parts) < 4:
        # fallback: assume canonical 1-10, 11-20, 21-30, 31-40
        parts = [
            {"number": 1, "instructions": "", "questionRange": [1, 10]},
            {"number": 2, "instructions": "", "questionRange": [11, 20]},
            {"number": 3, "instructions": "", "questionRange": [21, 30]},
            {"number": 4, "instructions": "", "questionRange": [31, 40]},
        ]
    questions = parse_question_blocks(soup, source="listening")
    return {
        "id": test_id,
        "audioUrl": audio_url,
        "localAudioPath": f"/audio/{test_id}.mp3",
        "parts": parts,
        "questions": questions,
        "answerKey": answer_key,
    }


def parse_writing_html(html: str, test_id: str) -> dict | None:
    soup = BeautifulSoup(html, "lxml")
    strip_ads(soup)
    text = soup.get_text("\n", strip=True)
    t1 = re.search(r"Task\s*1\s*:?\s*(.+?)(?=Task\s*2\s*:|$)", text, re.S | re.I)
    t2 = re.search(r"Task\s*2\s*:?\s*(.+?)(?=$)", text, re.S | re.I)
    img = soup.find("img")
    img_url = None
    if img and img.get("src"):
        src = img["src"]
        img_url = "https:" + src if src.startswith("//") else src
    if not t1 or not t2:
        return None
    return {
        "id": test_id,
        "task1": {
            "prompt": clean(t1.group(1)).split("Write at least")[0].strip(),
            "imageUrl": img_url,
            "minWords": 150,
        },
        "task2": {
            "prompt": clean(t2.group(1)).split("Write at least")[0].strip(),
            "minWords": 250,
        },
    }


def parse_speaking_docx(path: Path, test_id: str) -> dict | None:
    if Document is None:
        return None
    doc = Document(path)
    paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    if not paras:
        return None
    topic = paras[0].rstrip(":").strip()
    part1 = part2 = part3 = ""
    for p in paras:
        low = p.lower()
        if low.startswith("speaking part 1") or low.startswith("part 1"):
            part1 = p.split(":", 1)[1].strip() if ":" in p else p
        elif low.startswith("speaking part 2") or low.startswith("part 2"):
            part2 = p.split(":", 1)[1].strip() if ":" in p else p
        elif low.startswith("speaking part 3") or low.startswith("part 3"):
            part3 = p.split(":", 1)[1].strip() if ":" in p else p
    return {
        "id": test_id,
        "topic": topic,
        "part1": {"questions": [part1] if part1 else []},
        "part2": {
            "cueCard": part2 or f"Describe {topic.lower()}.",
            # Template bullet points (user approved this).
            "bulletPoints": [
                "what it is",
                "when or where you experienced it",
                "what makes it special",
                "and explain why you remember it",
            ],
            "prepSeconds": 60,
            "answerSeconds": 120,
        },
        "part3": {"questions": [part3] if part3 else []},
    }


def parse_question_blocks(soup: BeautifulSoup, source: str) -> list[dict]:
    """
    Walk the HTML linearly; whenever we hit text matching "Questions N-M"
    along with an instruction phrase, we collect the chunk up to the next
    "Questions N-M" header and route to a type-specific parser.
    """
    # Get the body text + structure preserved as a list of <p> blocks.
    blocks = []
    for el in soup.find_all(["p", "figure", "ul", "ol"]):
        blocks.append(str(el))
    joined = "\n".join(blocks)

    # Find all "Questions N-M" headers + their instruction text together.
    headers = list(re.finditer(
        r"Questions?\s+(\d+)\s*(?:and|–|-|to|–|,)\s*(\d+)",
        joined, re.I,
    ))
    questions: list[dict] = []
    for i, h in enumerate(headers):
        lo, hi = int(h.group(1)), int(h.group(2))
        start = h.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(joined)
        chunk = joined[start:end]
        # word limit
        wl_m = WORD_LIMIT_RE.search(chunk)
        word_limit = wl_m.group(1) if wl_m else None
        # classify
        typ = classify(chunk)
        group_id = f"q{lo}-{hi}"
        if typ == "multipleChoice":
            qs = parse_mcq(chunk, lo)
        elif typ in ("tfng", "ynng"):
            qs = parse_statements(chunk, (lo, hi), typ)
        elif typ == "matchHeadings":
            qs = parse_match_headings(chunk, (lo, hi), [])
        elif typ in ("sentenceCompletion", "summaryCompletion", "noteCompletion",
                     "tableCompletion", "formCompletion", "flowChartCompletion",
                     "shortAnswer", "diagramLabel", "mapPlanLabelling"):
            qs = parse_gap_fills(chunk, (lo, hi), typ, word_limit)
        else:
            # Fall back to gap-fill (most common) if we see input boxes; else unsupported
            if "<input" in chunk:
                qs = parse_gap_fills(chunk, (lo, hi), "gapFill", word_limit)
            else:
                qs = [{
                    "number": lo,
                    "type": "unsupported",
                    "rawHtml": chunk[:3000],
                }]
        for q in qs:
            q["groupId"] = group_id
            if word_limit and "wordLimit" not in q and "gapFill" in (q.get("type") or ""):
                q["wordLimit"] = word_limit
        questions.extend(qs)
    # de-dupe by number, prefer first
    seen: dict[int, dict] = {}
    for q in questions:
        n = q.get("number")
        if isinstance(n, int) and n not in seen:
            seen[n] = q
    return [seen[n] for n in sorted(seen)]


# ---------- main -------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="Limit the number of tests parsed per section (for smoke tests).")
    ap.add_argument("--copy-images", action="store_true",
                    help="Also copy associated images into public/.")
    args = ap.parse_args()

    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    for sub in ("reading", "listening", "writing", "speaking"):
        (CONTENT_DIR / sub).mkdir(exist_ok=True)

    catalog: dict[str, list[dict]] = {"reading": [], "listening": [], "writing": [], "speaking": []}
    failures: list[str] = []

    # Reading
    print("Parsing Reading HTML…")
    rd_paths = sorted(glob(str(TESTS_DIR / "Readings/html/ielts-reading-test-*")))
    if args.limit:
        rd_paths = rd_paths[: args.limit]
    for p in rd_paths:
        n = int(re.search(r"test-(\d+)", p).group(1))
        tid = pad_id(n)
        html = (Path(p) / "extracted_content.html").read_text(errors="replace")
        try:
            test = parse_reading_html(html, tid)
        except Exception as e:
            failures.append(f"reading {n}: {e}")
            continue
        if not test:
            failures.append(f"reading {n}: no key or no questions")
            continue
        (CONTENT_DIR / "reading" / f"{tid}.json").write_text(
            json.dumps(test, ensure_ascii=False, indent=2)
        )
        catalog["reading"].append({
            "id": tid,
            "flags": {
                "questions": len(test["questions"]),
                "hasImage": (TESTS_DIR / f"Readings/img/ielts-reading-test-{n}").exists(),
            },
        })
        if args.copy_images:
            src = TESTS_DIR / f"Readings/img/ielts-reading-test-{n}"
            if src.exists():
                dst = PUBLIC_DIR / f"reading-img/{tid}"
                shutil.copytree(src, dst, dirs_exist_ok=True)
    print(f"  Reading: {len(catalog['reading'])}/{len(rd_paths)} parsed")

    # Listening
    print("Parsing Listening HTML…")
    ls_paths = sorted(glob(str(TESTS_DIR / "Listenings/html/ielts-listening-test-*")))
    if args.limit:
        ls_paths = ls_paths[: args.limit]
    for p in ls_paths:
        n = int(re.search(r"test-(\d+)", p).group(1))
        tid = pad_id(n)
        html = (Path(p) / "extracted_content.html").read_text(errors="replace")
        try:
            test = parse_listening_html(html, tid)
        except Exception as e:
            failures.append(f"listening {n}: {e}")
            continue
        if not test:
            failures.append(f"listening {n}: no key")
            continue
        (CONTENT_DIR / "listening" / f"{tid}.json").write_text(
            json.dumps(test, ensure_ascii=False, indent=2)
        )
        catalog["listening"].append({
            "id": tid,
            "flags": {
                "hasAudioUrl": bool(test.get("audioUrl")),
                "hasImage": (TESTS_DIR / f"Listenings/img/ielts-listening-test-{n}").exists(),
            },
        })
        if args.copy_images:
            src = TESTS_DIR / f"Listenings/img/ielts-listening-test-{n}"
            if src.exists():
                dst = PUBLIC_DIR / f"listening-img/{tid}"
                shutil.copytree(src, dst, dirs_exist_ok=True)
    print(f"  Listening: {len(catalog['listening'])}/{len(ls_paths)} parsed")

    # Writing
    print("Parsing Writing HTML…")
    wr_paths = sorted(glob(str(TESTS_DIR / "Writings/html/ielts-writing-test-*")))
    if args.limit:
        wr_paths = wr_paths[: args.limit]
    for p in wr_paths:
        n = int(re.search(r"test-(\d+)", p).group(1))
        tid = pad_id(n)
        html = (Path(p) / "extracted_content.html").read_text(errors="replace")
        try:
            test = parse_writing_html(html, tid)
        except Exception as e:
            failures.append(f"writing {n}: {e}")
            continue
        if not test:
            failures.append(f"writing {n}: missing task1/task2")
            continue
        (CONTENT_DIR / "writing" / f"{tid}.json").write_text(
            json.dumps(test, ensure_ascii=False, indent=2)
        )
        catalog["writing"].append({
            "id": tid,
            "flags": {
                "hasTask1Image": bool(test["task1"].get("imageUrl")),
            },
        })
        if args.copy_images:
            src = TESTS_DIR / f"Writings/img/ielts-writing-test-{n}"
            if src.exists():
                dst = PUBLIC_DIR / f"writing-img/{tid}"
                shutil.copytree(src, dst, dirs_exist_ok=True)
    print(f"  Writing: {len(catalog['writing'])}/{len(wr_paths)} parsed")

    # Speaking (DOCX)
    print("Parsing Speaking DOCX…")
    sp_paths = sorted(glob(str(TESTS_DIR / "Speaking/docx/Speaking-*.docx")),
                      key=lambda p: int(re.search(r"-(\d+)\.docx", p).group(1)))
    if args.limit:
        sp_paths = sp_paths[: args.limit]
    for p in sp_paths:
        n = int(re.search(r"-(\d+)\.docx", p).group(1))
        tid = pad_id(n)
        try:
            test = parse_speaking_docx(Path(p), tid)
        except Exception as e:
            failures.append(f"speaking {n}: {e}")
            continue
        if not test:
            failures.append(f"speaking {n}: empty doc")
            continue
        (CONTENT_DIR / "speaking" / f"{tid}.json").write_text(
            json.dumps(test, ensure_ascii=False, indent=2)
        )
        catalog["speaking"].append({"id": tid, "flags": {"topic": test["topic"]}})
    print(f"  Speaking: {len(catalog['speaking'])}/{len(sp_paths)} parsed")

    # Catalog + failures
    from datetime import datetime, timezone
    catalog_doc = {**catalog, "generatedAt": datetime.now(timezone.utc).isoformat()}
    (CONTENT_DIR / "index.json").write_text(json.dumps(catalog_doc, ensure_ascii=False, indent=2))

    if failures:
        (ROOT / "scripts" / "parse-failures.log").write_text("\n".join(failures))
        print(f"\n  {len(failures)} failures logged to scripts/parse-failures.log")

    print("Done.")


if __name__ == "__main__":
    main()
