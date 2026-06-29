#!/usr/bin/env python3
"""youtube_transcript.py — discover YouTube discussions + fetch captions.

Uses youtube-transcript-api (https://github.com/jdepoix/youtube-transcript-api).
Install in field-sources venv:
  python3 -m venv .venv && .venv/bin/pip install youtube-transcript-api

Video discovery: YouTube search results page (no API key).
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
UA_BROWSER = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
VIDEO_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")
YOUTUBE_URL_RE = re.compile(
    r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
    re.I,
)


def _bootstrap_ytt_import() -> bool:
    """Prefer field-sources/.venv site-packages for youtube_transcript_api."""
    if "youtube_transcript_api" in sys.modules:
        return True
    candidates = []
    venv_lib = SKILL / ".venv" / "lib"
    if venv_lib.is_dir():
        candidates.extend(sorted(venv_lib.glob("python*/site-packages"), reverse=True))
    for site in candidates:
        s = str(site)
        if site.is_dir() and s not in sys.path:
            sys.path.insert(0, s)
            try:
                import youtube_transcript_api  # noqa: F401
                return True
            except ImportError:
                sys.path.remove(s)
    try:
        import youtube_transcript_api  # noqa: F401
        return True
    except ImportError:
        return False


def video_id_from_url(url: str) -> str | None:
    m = YOUTUBE_URL_RE.search(url or "")
    return m.group(1) if m else None


def _walk_yt_nodes(obj, hits: list[dict], seen: set[str], limit: int) -> None:
    if len(hits) >= limit:
        return
    if isinstance(obj, dict):
        if "videoId" in obj and VIDEO_ID_RE.match(obj.get("videoId") or ""):
            vid = obj["videoId"]
            if vid not in seen:
                title = ""
                if isinstance(obj.get("title"), dict):
                    runs = obj["title"].get("runs") or []
                    title = "".join(r.get("text", "") for r in runs if isinstance(r, dict))
                elif isinstance(obj.get("title"), str):
                    title = obj["title"]
                channel = ""
                owner = obj.get("ownerText") or obj.get("shortBylineText") or {}
                if isinstance(owner, dict):
                    runs = owner.get("runs") or []
                    channel = "".join(r.get("text", "") for r in runs if isinstance(r, dict))
                hits.append({"video_id": vid, "title": title.strip(), "channel": channel.strip()})
                seen.add(vid)
        for v in obj.values():
            _walk_yt_nodes(v, hits, seen, limit)
    elif isinstance(obj, list):
        for item in obj:
            _walk_yt_nodes(item, hits, seen, limit)


def search_youtube_videos(query: str, *, max_hits: int = 15, timeout: int = 25) -> list[dict]:
    """Search YouTube for videos matching query; return video_id, title, channel."""
    q = urllib.parse.quote(query.strip())
    # EgIQAQ%3D%3D → type=video
    url = f"https://www.youtube.com/results?search_query={q}&sp=EgIQAQ%253D%253D"
    req = urllib.request.Request(url, headers={
        "User-Agent": UA_BROWSER,
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            html = r.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    hits: list[dict] = []
    seen: set[str] = set()

    m = re.search(r"var ytInitialData = (\{.*?\});</script>", html, re.S)
    if m:
        try:
            data = json.loads(m.group(1))
            _walk_yt_nodes(data, hits, seen, max_hits)
        except Exception:
            pass

    if len(hits) < max_hits:
        for vid in re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html):
            if vid in seen:
                continue
            hits.append({"video_id": vid, "title": "", "channel": ""})
            seen.add(vid)
            if len(hits) >= max_hits:
                break

    return hits[:max_hits]


def fetch_transcript(
    video_id: str,
    *,
    languages: list[str] | None = None,
    max_chars: int = 14000,
) -> str:
    """Return plain-text transcript or empty string if unavailable."""
    if not VIDEO_ID_RE.match(video_id or ""):
        return ""
    if not _bootstrap_ytt_import():
        return ""

    languages = languages or ["en"]
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        ytt = YouTubeTranscriptApi()
        try:
            fetched = ytt.fetch(video_id, languages=languages)
            parts = [s.text for s in fetched]
        except TypeError:
            # Older package signature
            raw = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
            parts = [x.get("text", "") for x in raw]
        text = re.sub(r"\s+", " ", " ".join(parts)).strip()
        return text[:max_chars]
    except Exception:
        return ""


def fetch_youtube_discourse(
    query: str,
    *,
    max_hits: int = 10,
    languages: list[str] | None = None,
    max_transcript_chars: int = 12000,
    search_pool: int | None = None,
    pause_s: float = 0.35,
) -> list[dict]:
    """Search + transcript fetch for practitioner YouTube discussions."""
    pool = search_pool or max(max_hits * 2, 16)
    videos = search_youtube_videos(query, max_hits=pool)
    out: list[dict] = []
    languages = languages or ["en"]

    for v in videos:
        if len(out) >= max_hits:
            break
        vid = v["video_id"]
        transcript = fetch_transcript(vid, languages=languages, max_chars=max_transcript_chars)
        if len(transcript) < 180:
            continue
        title = v.get("title") or f"YouTube {vid}"
        out.append({
            "video_id": vid,
            "url": f"https://www.youtube.com/watch?v={vid}",
            "title": title,
            "channel": v.get("channel") or "",
            "summary": transcript[:800],
            "transcript": transcript,
        })
        if pause_s:
            time.sleep(pause_s)

    return out


def selftest() -> int:
    vids = search_youtube_videos("AI agent memory", max_hits=3)
    assert vids, "expected youtube search hits"
    assert VIDEO_ID_RE.match(vids[0]["video_id"])
    if _bootstrap_ytt_import():
        text = fetch_transcript(vids[0]["video_id"], max_chars=500)
        assert len(text) > 50, "expected transcript text"
    print("youtube_transcript selftest OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest())