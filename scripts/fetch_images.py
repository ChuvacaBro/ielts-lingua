#!/usr/bin/env python3
"""
Download diagram/map/plan images for reading & listening tests from the
Wayback Machine (the live source practicepteonline.com is offline).

For each test JSON in content/{reading,listening}/ we:
  - find the latest 200 snapshot of the source page,
  - extract real <img> URLs from the question content area (skipping lazy
    placeholders / tracking pixels),
  - download each image (trying the page snapshot first, then any archived
    capture of the image URL),
  - save to public/{section}-img/{id}/image_{k}.{ext},
  - record everything in scripts/images_manifest.json.

Idempotent: tests already present in the manifest are skipped. Run again to
fill gaps.

Usage:  python3 scripts/fetch_images.py [reading|listening|all] [--limit N]
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
MANIFEST = ROOT / "scripts" / "images_manifest.json"
UA = {"User-Agent": "Mozilla/5.0"}
IMG_RE = re.compile(r"\.(png|jpe?g|webp)(\?|$)", re.I)


def get(url, timeout=50, tries=4):
    last = None
    for i in range(tries):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=timeout
            ).read()
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
    src = re.sub(r"^/web/\d+\w*/", "", src)
    if src.startswith("//"):
        return "https:" + src
    if src.startswith("/"):
        return "https://practicepteonline.com" + src
    return src


def content_images(html):
    soup = BeautifulSoup(html, "html.parser")
    col = soup.select_one("div.col-lg-8") or soup.find(class_="entry-content")
    if not col:
        return []
    seen, out = set(), []
    for im in col.find_all("img"):
        url = ""
        for attr in ("data-lazy-src", "data-src", "src"):
            v = im.get(attr) or ""
            if not v.startswith("data:") and IMG_RE.search(v):
                url = v
                break
        if url:
            absu = to_abs(url)
            if absu not in seen:
                seen.add(absu)
                out.append(absu)
    return out


def download_image(absu, page_ts):
    """Try the page snapshot first, then any archived capture of the image."""
    try:
        return get(f"https://web.archive.org/web/{page_ts}im_/{absu}")
    except Exception:
        pass
    try:
        cdx = (f"http://web.archive.org/cdx/search/cdx?url={absu}"
               f"&output=json&filter=statuscode:200&limit=-1")
        rows = json.loads(get(cdx, 40).decode())
        if len(rows) > 1:
            ts = rows[-1][1]
            return get(f"https://web.archive.org/web/{ts}im_/{absu}")
    except Exception:
        pass
    return None


def process(kind, tid):
    n = int(tid)
    dest = PUBLIC / f"{kind}-img" / tid
    try:
        page_ts = latest_snapshot(kind, n)
        if not page_ts:
            return tid, {"status": "no-snapshot", "images": []}
        html = get(f"https://web.archive.org/web/{page_ts}id_/"
                   f"https://practicepteonline.com/ielts-{kind}-test-{n}/").decode(
            "utf-8", "replace")
        urls = content_images(html)
        if not urls:
            return tid, {"status": "no-images", "images": []}
        dest.mkdir(parents=True, exist_ok=True)
        saved = []
        for k, absu in enumerate(urls, 1):
            data = download_image(absu, page_ts)
            if not data or len(data) < 1000:
                continue
            ext = (IMG_RE.search(absu).group(1) or "png").lower().replace("jpeg", "jpg")
            fname = f"image_{k}.{ext}"
            (dest / fname).write_bytes(data)
            saved.append({"file": fname, "src": absu, "bytes": len(data)})
        return tid, {"status": "ok" if saved else "dl-failed", "images": saved}
    except Exception as e:
        return tid, {"status": f"error: {e}", "images": []}


def main():
    kinds = ["reading", "listening"]
    arg = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "all"
    if arg in kinds:
        kinds = [arg]
    limit = 0
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    for kind in kinds:
        manifest.setdefault(kind, {})
        ids = sorted(p.stem for p in (ROOT / "content" / kind).glob("*.json"))

        def has_local(t):
            d = PUBLIC / f"{kind}-img" / t
            return d.exists() and any(d.iterdir())

        todo = [t for t in ids if t not in manifest[kind] and not has_local(t)]
        if limit:
            todo = todo[:limit]
        print(f"{kind}: {len(todo)} tests to process ({len(ids)} total)", flush=True)
        done = 0
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = {ex.submit(process, kind, t): t for t in todo}
            for fut in as_completed(futs):
                tid, res = fut.result()
                manifest[kind][tid] = res
                done += 1
                if res["images"] or res["status"] not in ("no-images",):
                    print(f"  [{done}/{len(todo)}] {kind} {tid}: {res['status']} "
                          f"({len(res['images'])} imgs)", flush=True)
                if done % 25 == 0:
                    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        with_imgs = sum(1 for v in manifest[kind].values() if v["images"])
        print(f"{kind} DONE: {with_imgs} tests with images → {MANIFEST}", flush=True)


if __name__ == "__main__":
    main()
