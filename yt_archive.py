#!/usr/bin/env python3
"""Turn a YouTube channel into a searchable Markdown knowledge base.

  python yt_archive.py channel @somechannel --out archive/           # long videos + shorts
  python yt_archive.py channel @somechannel --out archive/ --kinds videos --limit 50
  python yt_archive.py docs --out archive/                           # fetch public Google Docs linked in descriptions

For every video: title, URL, full description, resource links (Google Docs/Drive,
Notion, Dropbox, Coda) and the timestamped transcript, one .md file each, plus
index.json and 00_INDEX.md. Re-runs skip files that are already complete, so a
1,000+ video channel can be archived across several sessions.

Respect creators' rights: archives are for personal study, do not republish them.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

URL_RE = re.compile(r'https?://[^\s<>"{}|\^`]+')
RESOURCE_HOSTS = ("docs.google.com", "drive.google.com", "notion", "dropbox", "coda.io")
GDOC_RE = re.compile(r"https://docs\.google\.com/document/d/([a-zA-Z0-9_-]+)")


def resource_links(text: str) -> list[str]:
    return list(dict.fromkeys(u for u in URL_RE.findall(text or "") if any(h in u for h in RESOURCE_HOSTS)))


def safe_name(title: str, limit: int = 50) -> str:
    return "".join(c for c in title if c.isalnum() or c in " _-").strip()[:limit]


def channel_url(handle: str, kind: str) -> str:
    base = handle if handle.startswith("http") else f"https://www.youtube.com/{handle if handle.startswith('@') else '@' + handle}"
    return f"{base.rstrip('/')}/{kind}"


def write_video_md(path: Path, item: dict, description: str, transcript: str) -> None:
    lines = [f"# {item['title']}\n", f"- **Type:** {item['type']}", f"- **URL:** {item['url']}",
             f"- **Transcript:** {item['status']}"]
    if item["links"]:
        lines.append(f"- **Resource links ({len(item['links'])}):**")
        lines += [f"  - {u}" for u in item["links"]]
    lines += ["\n---\n", "## Description\n", f"```text\n{description}\n```" if description else "*(none)*",
              "\n---\n", "## Transcript\n", transcript or "*(no captions available)*"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def archive_kind(handle: str, kind: str, out: Path, limit: int | None, delay: float) -> list[dict]:
    import yt_dlp
    from youtube_transcript_api import YouTubeTranscriptApi

    target = out / kind.upper()
    target.mkdir(parents=True, exist_ok=True)
    with yt_dlp.YoutubeDL({"extract_flat": "in_playlist", "skip_download": True, "quiet": True}) as ydl:
        entries = (ydl.extract_info(channel_url(handle, kind), download=False) or {}).get("entries", [])[: limit or None]
    print(f"{kind}: {len(entries)} items")

    api, info_dl, items = YouTubeTranscriptApi(), yt_dlp.YoutubeDL({"skip_download": True, "quiet": True, "no_warnings": True}), []
    for idx, entry in enumerate(entries, 1):
        vid = entry.get("id")
        if not vid:
            continue
        title = entry.get("title") or vid
        url = f"https://www.youtube.com/watch?v={vid}"
        path = target / f"{idx:04d}_{safe_name(title)}_{vid}.md"
        item = {"num": idx, "type": kind, "title": title, "url": url, "id": vid, "file": f"{target.name}/{path.name}",
                "status": "", "links": []}
        if path.exists() and path.stat().st_size > 500:
            item["status"] = "cached"
            items.append(item)
            continue

        time.sleep(delay)
        try:
            description = info_dl.extract_info(url, download=False).get("description") or ""
        except Exception:
            description = ""
        item["links"] = resource_links(description)
        try:
            transcript = "\n".join(f"[{int(s.start // 60):02d}:{int(s.start % 60):02d}] {s.text}" for s in api.fetch(vid))
            item["status"] = "ok"
        except Exception:
            transcript, item["status"] = "", "missing"
        write_video_md(path, item, description, transcript)
        items.append(item)
        print(f"[{idx}/{len(entries)}] {item['status']:<7} {title[:60]}")
    return items


def write_index(out: Path, items: list[dict], handle: str) -> None:
    (out / "index.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = [f"# Archive: {handle}\n", f"**{len(items)} items**\n", "| # | Type | Title | Transcript | Links | File |",
            "|---|---|---|---|---|---|"]
    rows += [f"| {i} | {it['type']} | [{it['title']}]({it['url']}) | {it['status']} | {len(it['links']) or '-'} | [{it['file']}]({it['file'].replace(' ', '%20')}) |"
             for i, it in enumerate(items, 1)]
    (out / "00_INDEX.md").write_text("\n".join(rows) + "\n", encoding="utf-8")


def fetch_docs(out: Path) -> None:
    """Exports every public Google Doc linked anywhere in the archive as plain text."""
    ids = sorted({m for md in out.rglob("*.md") for m in GDOC_RE.findall(md.read_text(encoding="utf-8", errors="ignore"))})
    docs = out / "DOCS"
    docs.mkdir(exist_ok=True)
    print(f"{len(ids)} Google Docs referenced")
    for doc_id in ids:
        dest = docs / f"gdoc_{doc_id}.txt"
        if dest.exists() and dest.stat().st_size > 100:
            continue
        try:
            req = urllib.request.Request(f"https://docs.google.com/document/d/{doc_id}/export?format=txt",
                                         headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                dest.write_text(resp.read().decode("utf-8", errors="ignore"), encoding="utf-8")
            print(f"ok   {doc_id}")
        except Exception as exc:  # private docs return 401/403
            print(f"skip {doc_id}: {exc}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("channel")
    c.add_argument("handle", help="@handle or channel URL")
    c.add_argument("--out", type=Path, default=Path("archive"))
    c.add_argument("--kinds", nargs="+", default=["videos", "shorts"], choices=["videos", "shorts", "streams"])
    c.add_argument("--limit", type=int, help="max items per kind")
    c.add_argument("--delay", type=float, default=0.5, help="seconds between requests")
    d = sub.add_parser("docs")
    d.add_argument("--out", type=Path, default=Path("archive"))
    args = ap.parse_args()

    if args.cmd == "channel":
        items = [it for kind in args.kinds for it in archive_kind(args.handle, kind, args.out, args.limit, args.delay)]
        write_index(args.out, items, args.handle)
        print(f"Done: {len(items)} items -> {args.out}")
    else:
        fetch_docs(args.out)


if __name__ == "__main__":
    main()
