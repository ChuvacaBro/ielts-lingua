#!/usr/bin/env python3
"""
Derive an authoritative image→question-range placement from the Wayback archive
(the source page shows each diagram/map directly under its question header), and
reconcile it with the locally-downloaded images.

For every test that currently has images in public/{section}-img/{id}/:
  - fetch the latest archive snapshot,
  - walk the content in order, pairing each real <img> with the most recent
    "Questions N-M" header,
  - if the archive's real-image count matches what we have locally, keep the
    local files and just record each one's [lo,hi] range (same order);
  - otherwise re-download the real images from the archive (R2 fall-back by
    order) so the set and its placement are consistent.

Output: scripts/image_placement.json  {section: {id: [[filename,[lo,hi]], …]}}

Usage:  python3 scripts/build_image_placement.py [reading|listening|all]
"""
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
OUT = ROOT / "scripts" / "image_placement.json"
UA = {"User-Agent": "Mozilla/5.0"}
IMG_RE = re.compile(r"\.(png|jpe?g|webp)(\?|$)", re.I)


def get(url, timeout=50, tries=4):
    last = None
    for i in range(tries):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=timeout).read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            last = e
        except Exception as e:
            last = e
        time.sleep(1.5 * (i + 1))
    raise last


def latest_snapshot(kind, n):
    cdx = (f"http://web.archive.org/cdx/search/cdx?url=practicepteonline.com/"
           f"ielts-{kind}-test-{n}/&output=json&filter=statuscode:200&limit=-1")
    rows = json.loads(get(cdx, 40).decode())
    return rows[-1][1] if len(rows) > 1 else None


def to_abs(src):
    src = re.sub(r"^/web/\d+\w*/", "", src.strip())
    if src.startswith("//"):
        return "https:" + src
    if src.startswith("/"):
        return "https://practicepteonline.com" + src
    return src


def archive_images(kind, n):
    """Ordered [(abs_url, (lo,hi) | None)] of real content images on the page."""
    ts = latest_snapshot(kind, n)
    if not ts:
        return ts, []
    raw = get(f"https://web.archive.org/web/{ts}id_/"
              f"https://practicepteonline.com/ielts-{kind}-test-{n}/").decode("utf-8", "replace")
    col = BeautifulSoup(raw, "html.parser").select_one("div.col-lg-8") \
        or BeautifulSoup(raw, "html.parser").find(class_="entry-content")
    if not col:
        return ts, []
    cur, out, seen = None, [], set()
    for el in col.descendants:
        nm = getattr(el, "name", None)
        if nm in ("p", "h2", "h3", "h4", "li"):
            t = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
            m = re.search(r"Questions?\s+(\d+)\s*[-–—]\s*(\d+)", t, re.I)
            if m:
                cur = (int(m.group(1)), int(m.group(2)))
        elif nm == "img":
            src = (el.get("data-lazy-src") or el.get("data-src") or el.get("src") or "")
            if not src.startswith("data:") and IMG_RE.search(src):
                absu = to_abs(src)
                if absu not in seen:
                    seen.add(absu)
                    out.append((absu, cur))
    return ts, out


def download(absu, page_ts):
    try:
        d = get(f"https://web.archive.org/web/{page_ts}im_/{absu}")
        if len(d) > 800:
            return d
    except Exception:
        pass
    try:
        rows = json.loads(get(f"http://web.archive.org/cdx/search/cdx?url={absu}"
                              f"&output=json&filter=statuscode:200&limit=-1", 40).decode())
        if len(rows) > 1:
            d = get(f"https://web.archive.org/web/{rows[-1][1]}im_/{absu}")
            if len(d) > 800:
                return d
    except Exception:
        pass
    return None


def local_files(section, tid):
    d = PUBLIC / f"{section}-img" / tid
    if not d.exists():
        return []
    return sorted(p.name for p in d.iterdir()
                  if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"))


def process(kind, tid):
    n = int(tid)
    local = local_files(kind, tid)
    try:
        ts, imgs = archive_images(kind, n)
    except Exception as e:
        return tid, {"status": f"error: {e}", "placement": None}
    real = [(u, r) for (u, r) in imgs]  # keep all; ranges may be None (header img)
    if not real:
        return tid, {"status": "no-archive-images", "placement": None}

    dest = PUBLIC / f"{kind}-img" / tid
    placement = []
    if len(real) == len(local):
        # trust local files, attach archive ranges in order
        for fname, (_u, rng) in zip(local, real):
            placement.append([fname, list(rng) if rng else None])
        return tid, {"status": "aligned", "placement": placement}

    # counts differ: rebuild the image set from the archive
    dest.mkdir(parents=True, exist_ok=True)
    saved = 0
    for i, (absu, rng) in enumerate(real, 1):
        data = download(absu, ts)
        ext = (IMG_RE.search(absu).group(1) or "png").lower().replace("jpeg", "jpg")
        fname = f"image_{i}.{ext}"
        if data:
            (dest / fname).write_bytes(data)
            saved += 1
        elif i <= len(local):  # fall back to the i-th local file (re-order)
            src = dest / local[i - 1]
            if src.exists() and local[i - 1] != fname:
                (dest / fname).write_bytes(src.read_bytes())
            fname = local[i - 1] if not (dest / fname).exists() else fname
        else:
            continue
        placement.append([fname, list(rng) if rng else None])
    return tid, {"status": f"rebuilt({saved}/{len(real)})", "placement": placement}


def main():
    kinds = ["reading", "listening"]
    if len(sys.argv) > 1 and sys.argv[1] in kinds:
        kinds = [sys.argv[1]]
    manifest = json.loads(OUT.read_text()) if OUT.exists() else {}
    for kind in kinds:
        manifest.setdefault(kind, {})
        ids = sorted(p.name for p in (PUBLIC / f"{kind}-img").iterdir()
                     if (PUBLIC / f"{kind}-img" / p.name).is_dir()) \
            if (PUBLIC / f"{kind}-img").exists() else []
        todo = [t for t in ids if t not in manifest[kind]]
        print(f"{kind}: {len(todo)} tests", flush=True)
        done = 0
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = {ex.submit(process, kind, t): t for t in todo}
            for fut in as_completed(futs):
                tid, res = fut.result()
                manifest[kind][tid] = res
                done += 1
                print(f"  [{done}/{len(todo)}] {kind} {tid}: {res['status']} "
                      f"({len(res['placement'] or [])} placed)", flush=True)
                if done % 15 == 0:
                    OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        print(f"{kind} DONE → {OUT}", flush=True)


if __name__ == "__main__":
    main()
