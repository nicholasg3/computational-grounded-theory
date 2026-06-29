#!/usr/bin/env python3
"""field_expansion.py — practitioner field data beyond preprint abstracts.

Harvests multi-modal online field evidence for digital ethnography + Charmaz GT:
  - Preserves field_sources tier_corpus / field_corpus (no wipe on expand)
  - Scout signals (HN, RSS, Substack, Reddit, Stack Overflow, X) matched to topic
  - Deep fetch: HN threads, Reddit posts/comments (PullPush), SO Q&A, Substack bodies

Artifacts: ethnography/<slug>/field_corpus.jsonl, practitioner_quotes.csv

  python3 field_expansion.py <slug>
  python3 field_expansion.py --selftest
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from field_gather.paths import project_root as _project_root

ROOT = _project_root()
SIGNALS = ROOT / "inbox" / "signals"
SELECTED = ROOT / "topics" / "selected"
ETHNO = ROOT / "ethnography"
CITATIONS = ROOT / "citations"

def _bind_root(root: Path) -> None:
    global ROOT, SIGNALS, SELECTED, ETHNO, CITATIONS
    ROOT = root
    SIGNALS = ROOT / "inbox" / "signals"
    SELECTED = ROOT / "topics" / "selected"
    ETHNO = ROOT / "ethnography"
    CITATIONS = ROOT / "citations"

UA = "StrategicPublishing/1.0 (field-expansion; research)"
TOPIC_RE = re.compile(
    r"\b(agent|memory|rule|prompt|weight|policy|orchestrat|rout|ensemble|"
    r"multi-?model|experiential|governance|audit|workflow|harness|context)\w*\b",
    re.I,
)
HN_ITEM_RE = re.compile(r"(?:item\?id=|/item/)(\d+)", re.I)
HN_ALGOLIA = "https://hn.algolia.com/api/v1"
PULLPUSH_REDDIT = "https://api.pullpush.io/reddit"
STACKEXCHANGE_API = "https://api.stackexchange.com/2.3"
REDDIT_POST_RE = re.compile(r"reddit\.com/r/\w+/comments/([a-z0-9]+)", re.I)
SO_QUESTION_RE = re.compile(r"stackoverflow\.com/questions/(\d+)", re.I)
SUBSTACK_POST_RE = re.compile(
    r"https?://([a-z0-9-]+)\.substack\.com/p/([a-z0-9-]+)", re.I,
)
SUBSTACK_CUSTOM_RE = re.compile(
    r"https?://(?:www\.)?([a-z0-9-]+)\.(?:co|com)/p/([a-z0-9-]+)", re.I,
)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fetch_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def _fetch_text(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def _strip_html(html):
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html or "", flags=re.I | re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_rss_items(xml):
    """Extract (title, link, body_text) from RSS/Atom XML."""
    items = []
    blocks = re.findall(r"<item>(.*?)</item>", xml, re.DOTALL) or \
        re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL)
    for b in blocks:
        title_m = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", b, re.DOTALL)
        link_m = re.search(r"<link[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>", b, re.DOTALL)
        if not link_m or not (link_m.group(1) or "").strip():
            href = re.search(r'<link[^>]*href="([^"]+)"', b)
            link = href.group(1) if href else ""
        else:
            link = link_m.group(1).strip()
        content_m = re.search(
            r"<content:encoded>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</content:encoded>", b, re.DOTALL,
        )
        desc_m = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", b, re.DOTALL)
        body = ""
        if content_m:
            body = _strip_html(content_m.group(1))
        elif desc_m:
            body = _strip_html(desc_m.group(1))
        title = _strip_html(title_m.group(1)) if title_m else ""
        if link:
            items.append((title, link, body))
    return items


def _substack_publication(url):
    """Resolve Substack publication handle + post slug from URL."""
    m = SUBSTACK_POST_RE.search(url)
    if m:
        return m.group(1), m.group(2)
    m = SUBSTACK_CUSTOM_RE.search(url)
    if m:
        return m.group(1), m.group(2)
    return None, None


def _fetch_substack_post(url):
    """Full post text via publication RSS (Substack standard /feed endpoint)."""
    pub, slug = _substack_publication(url)
    if not pub:
        return []
    feed_candidates = [
        f"https://{pub}.substack.com/feed",
        f"https://www.{pub}.com/feed",
        f"https://{pub}.com/feed",
    ]
    for feed_url in feed_candidates:
        try:
            xml = _fetch_text(feed_url)
        except Exception:
            continue
        for title, link, body in _parse_rss_items(xml):
            if slug in link or slug in (link or "").rstrip("/").split("/")[-1]:
                text = body or title
                if len(text) < 80:
                    continue
                return [{
                    "text": text[:8000],
                    "source_type": "substack_post",
                    "author_voice": "practitioner",
                    "url": link or url,
                    "title": title,
                }]
    return []


def _topic_terms(slug):
    terms = set()
    theory = ROOT / "grounded" / slug / "theory.json"
    if theory.exists():
        try:
            t = json.loads(theory.read_text())
            for f in ("thesis", "phenomenon", "core_category"):
                terms.update(re.findall(r"[a-z]{4,}", (t.get(f) or "").lower()))
        except Exception:
            pass
    brief = SELECTED / f"{slug}.md"
    if brief.exists():
        terms.update(re.findall(r"[a-z]{4,}", brief.read_text().lower()))
    return terms


def _relevance(text, topic_terms):
    t = text or ""
    score = 0
    if TOPIC_RE.search(t):
        score += 4
    for term in topic_terms:
        if term in t.lower():
            score += 1
    return score


def _load_all_signals():
    rows = []
    if not SIGNALS.exists():
        return rows
    for path in sorted(SIGNALS.glob("*.jsonl")):
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def _brief_urls(slug):
    brief = SELECTED / f"{slug}.md"
    urls = set()
    if brief.exists():
        for m in re.finditer(r"https?://\S+", brief.read_text()):
            urls.add(m.group(0).rstrip(").,"))
    return urls


def _load_existing_corpus(base):
    """Preserve field_sources gather output; tier_corpus is the latest run snapshot."""
    rows = []
    seen_urls = set()
    for fname in ("tier_corpus.jsonl", "field_corpus.jsonl"):
        path = base / fname
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            url = (row.get("url") or "").strip()
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            rows.append(row)
    return rows


def _fetch_reddit_thread(url):
    """Reddit post body + top comments via PullPush (reddit.com JSON often blocked)."""
    m = REDDIT_POST_RE.search(url or "")
    if not m:
        return []
    post_id = m.group(1)
    out = []
    try:
        data = _fetch_json(
            f"{PULLPUSH_REDDIT}/search/submission/?ids={post_id}",
            timeout=25,
        )
        for hit in data.get("data", [])[:1]:
            title = (hit.get("title") or "").strip()
            selftext = (hit.get("selftext") or "").strip()
            if selftext in ("[removed]", "[deleted]"):
                selftext = ""
            blob = f"{title}. {selftext}".strip()
            if len(blob) >= 40:
                out.append({
                    "text": blob[:8000],
                    "source_type": "reddit_post",
                    "author_voice": "practitioner",
                    "url": url,
                    "title": title,
                })
    except Exception:
        pass
    try:
        comments = _fetch_json(
            f"{PULLPUSH_REDDIT}/search/comment/?link_id=t3_{post_id}"
            + "&size=6&sort=desc&sort_type=score",
            timeout=25,
        )
        for ch in comments.get("data", []):
            body = (ch.get("body") or "").strip()
            if body in ("[removed]", "[deleted]") or len(body) < 40:
                continue
            out.append({
                "text": body[:4000],
                "source_type": "reddit_comment",
                "author_voice": "practitioner",
                "url": url,
            })
    except Exception:
        pass
    return out


def _fetch_stackoverflow_thread(url):
    """Stack Overflow question + top-voted answers via API 2.3."""
    m = SO_QUESTION_RE.search(url or "")
    if not m:
        return []
    qid = m.group(1)
    out = []
    try:
        qdata = _fetch_json(
            f"{STACKEXCHANGE_API}/questions/{qid}"
            + "?order=desc&sort=votes&site=stackoverflow&filter=withbody",
            timeout=20,
        )
        for item in qdata.get("items", []):
            title = html.unescape(item.get("title") or "")
            body = html.unescape(re.sub(r"<[^>]+>", " ", item.get("body") or ""))
            body = re.sub(r"\s+", " ", body).strip()
            blob = f"{title}. {body}".strip()
            if len(blob) >= 40:
                out.append({
                    "text": blob[:8000],
                    "source_type": "stackoverflow_question",
                    "author_voice": "practitioner",
                    "url": url,
                    "title": title,
                })
    except Exception:
        return out
    try:
        adata = _fetch_json(
            f"{STACKEXCHANGE_API}/questions/{qid}/answers"
            + "?order=desc&sort=votes&site=stackoverflow&pagesize=5&filter=withbody",
            timeout=20,
        )
        for ans in adata.get("items", []):
            body = html.unescape(re.sub(r"<[^>]+>", " ", ans.get("body") or ""))
            body = re.sub(r"\s+", " ", body).strip()
            if len(body) < 40:
                continue
            out.append({
                "text": body[:4000],
                "source_type": "stackoverflow_answer",
                "author_voice": "practitioner",
                "url": url,
            })
    except Exception:
        pass
    return out


def _fetch_youtube_transcript(url):
    """Full caption text via youtube-transcript-api (field-sources skill)."""
    candidates = [
        Path.home() / "code/skill-library/research/field-sources/scripts/youtube_transcript.py",
        ROOT.parent.parent / "skill-library/research/field-sources/scripts/youtube_transcript.py",
    ]
    for p in candidates:
        if not p.exists():
            continue
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("youtube_transcript", p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            vid = mod.video_id_from_url(url)
            if not vid:
                return []
            text = mod.fetch_transcript(vid, max_chars=14000)
            if len(text) < 180:
                return []
            return [{
                "text": text,
                "source_type": "youtube_transcript",
                "author_voice": "practitioner",
                "url": url,
            }]
        except Exception:
            continue
    return []


def _deep_fetch_pieces(url, source):
    """Return expanded text pieces for a practitioner URL."""
    if source == "youtube" or "youtube.com" in (url or "") or "youtu.be" in (url or ""):
        return _fetch_youtube_transcript(url)
    if source == "hn" or "ycombinator.com" in (url or ""):
        m = HN_ITEM_RE.search(url or "")
        if m:
            return _fetch_hn_thread(m.group(1))
    if source in ("reddit", "reddit_discourse") or "reddit.com" in (url or ""):
        return _fetch_reddit_thread(url)
    if source in ("stackoverflow", "stack_overflow_discourse") or "stackoverflow.com" in (url or ""):
        return _fetch_stackoverflow_thread(url)
    if source == "substack" or "substack.com" in (url or "") or SUBSTACK_CUSTOM_RE.search(url or ""):
        return _fetch_substack_post(url)
    return []


def _fetch_hn_thread(item_id):
    """HN story + top-level comments via Algolia (public API)."""
    out = []
    try:
        data = _fetch_json(f"{HN_ALGOLIA}/items/{item_id}")
    except Exception:
        return out
    story = data.get("title") or ""
    if data.get("story_text"):
        story += " " + data.get("story_text", "")
    if story.strip():
        out.append({
            "text": story.strip(),
            "source_type": "hn_story",
            "author_voice": "practitioner",
            "url": data.get("url") or f"https://news.ycombinator.com/item?id={item_id}",
        })
    children = data.get("children") or []
    for ch in children[:8]:
        if ch.get("type") != "comment":
            continue
        txt = (ch.get("text") or "").strip()
        if len(txt) < 40:
            continue
        out.append({
            "text": re.sub(r"<[^>]+>", " ", txt),
            "source_type": "hn_comment",
            "author_voice": "practitioner",
            "url": f"https://news.ycombinator.com/item?id={ch.get('id', item_id)}",
        })
    return out


def _quote_candidates(text, source_id, source_type, url, site, topic_terms):
    quotes = []
    for sent in re.split(r"(?<=[.!?])\s+", text or ""):
        sent = sent.strip()
        if len(sent) < 45:
            continue
        rel = _relevance(sent, topic_terms)
        if rel < 3:
            continue
        quotes.append({
            "quote": sent[:500],
            "source_id": source_id,
            "source_type": source_type,
            "site": site,
            "url": url,
            "relevance": rel,
            "author_voice": "practitioner" if (
                source_type.startswith("hn")
                or source_type.startswith("reddit")
                or source_type.startswith("stackoverflow")
                or source_type.startswith("youtube")
            ) else "field",
        })
    return quotes


def _append_deep_fetch(corpus, all_quotes, sid, title, url, source, session, topic_terms):
    for piece in _deep_fetch_pieces(url, source):
        corpus.append({
            "id": f"{sid}_deep",
            "captured_at": session,
            "source_channel": source if source in ("hn", "reddit", "stackoverflow", "substack", "youtube") else (
                "reddit" if "reddit.com" in url else
                "stackoverflow" if "stackoverflow.com" in url else
                "youtube" if "youtube.com" in url or "youtu.be" in url else source
            ),
            "source_type": piece["source_type"],
            "url": piece.get("url") or url,
            "title": piece.get("title") or title,
            "text": piece["text"],
            "relevance": _relevance(piece["text"], topic_terms),
        })
        ch = corpus[-1]["source_channel"]
        all_quotes.extend(
            _quote_candidates(
                piece["text"], sid, piece["source_type"],
                piece.get("url") or url, ch, topic_terms,
            )
        )


def expand(slug):
    """Harvest practitioner + multi-source field corpus."""
    base = ETHNO / slug
    base.mkdir(parents=True, exist_ok=True)
    topic_terms = _topic_terms(slug)
    brief_urls = _brief_urls(slug)
    cite_urls = set()
    cite_base = CITATIONS / slug
    if cite_base.is_dir():
        for d in cite_base.iterdir():
            mp = d / "meta.json"
            if mp.exists():
                try:
                    cite_urls.add(json.loads(mp.read_text()).get("url", ""))
                except Exception:
                    pass

    corpus = _load_existing_corpus(base)
    all_quotes = []
    session = _now()
    expanded_urls = set()
    deep_limits = {"reddit": 12, "stackoverflow": 10, "hn": 8, "substack": 6, "youtube": 6}
    deep_counts = {k: 0 for k in deep_limits}
    deep_types = frozenset({
        "hn_story", "hn_comment", "substack_post", "reddit_post", "reddit_comment",
        "stackoverflow_question", "stackoverflow_answer", "youtube_transcript",
    })

    def _deep_channel(url, source):
        if "reddit.com" in url or source in ("reddit", "reddit_discourse"):
            return "reddit"
        if "stackoverflow.com" in url or source in ("stackoverflow", "stack_overflow_discourse"):
            return "stackoverflow"
        if "ycombinator.com" in url or source == "hn":
            return "hn"
        if "substack.com" in url or SUBSTACK_CUSTOM_RE.search(url or "") or source == "substack":
            return "substack"
        if "youtube.com" in url or "youtu.be" in url or source == "youtube":
            return "youtube"
        return ""

    shallow = [
        row for row in corpus
        if row.get("source_type") not in deep_types and (row.get("url") or "").strip()
    ]
    shallow.sort(key=lambda r: -(int(r.get("relevance") or 0)))

    for row in shallow:
        url = (row.get("url") or "").strip()
        if not url or url in expanded_urls:
            continue
        source = row.get("source_channel") or row.get("source_type") or ""
        ch = _deep_channel(url, source)
        if not ch or deep_counts[ch] >= deep_limits[ch]:
            continue
        expanded_urls.add(url)
        deep_counts[ch] += 1
        _append_deep_fetch(
            corpus, all_quotes,
            row.get("id") or f"row_{len(corpus)}",
            row.get("title") or "",
            url, source, session, topic_terms,
        )

    for sig in _load_all_signals():
        url = (sig.get("url") or "").strip()
        title = sig.get("title") or ""
        summary = sig.get("summary") or ""
        source = sig.get("source") or "signal"
        blob = f"{title}. {summary}".strip()
        rel = _relevance(blob, topic_terms)
        in_topic = url in brief_urls or url in cite_urls or rel >= 4
        if not in_topic:
            continue

        sid = sig.get("id") or f"sig_{len(corpus)}"
        entry = {
            "id": sid,
            "captured_at": session,
            "source_channel": source,
            "source_type": source,
            "url": url,
            "title": title,
            "text": blob,
            "relevance": rel,
        }
        corpus.append(entry)
        all_quotes.extend(_quote_candidates(blob, sid, source, url, source, topic_terms))

        if url not in expanded_urls:
            expanded_urls.add(url)
            _append_deep_fetch(corpus, all_quotes, sid, title, url, source, session, topic_terms)

    # Dedupe quotes, rank
    seen = set()
    ranked = []
    for q in sorted(all_quotes, key=lambda x: -x["relevance"]):
        key = q["quote"][:90].lower()
        if key in seen:
            continue
        seen.add(key)
        ranked.append(q)

    deduped = []
    seen_keys = set()
    for row in corpus:
        key = ((row.get("url") or ""), row.get("source_type") or "", (row.get("text") or "")[:120])
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(row)

    corp_path = base / "field_corpus.jsonl"
    with corp_path.open("w", encoding="utf-8") as f:
        for row in deduped:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    pq_path = base / "practitioner_quotes.csv"
    with pq_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "quote", "source_id", "source_type", "site", "url", "relevance", "author_voice",
        ])
        w.writeheader()
        for q in ranked[:40]:
            w.writerow({k: q.get(k, "") for k in w.fieldnames})

    (base / "field_expansion.json").write_text(json.dumps({
        "slug": slug,
        "corpus_rows": len(deduped),
        "practitioner_quotes": len(ranked),
        "source_channels": sorted({r["source_channel"] for r in deduped}),
        "expanded_at": session,
    }, indent=2) + "\n")

    return {
        "slug": slug,
        "corpus": len(deduped),
        "quotes": len(ranked),
        "channels": sorted({r["source_channel"] for r in deduped}),
    }


def load_practitioner_quotes(slug, limit=12):
    p = ETHNO / slug / "practitioner_quotes.csv"
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))[:limit]


def selftest():
    import tempfile
    slug = "9999-01-01-field-expansion"
    with tempfile.TemporaryDirectory() as td:
        global ROOT, SIGNALS, SELECTED, ETHNO, CITATIONS
        saved = (ROOT, SIGNALS, SELECTED, ETHNO, CITATIONS)
        ROOT = Path(td)
        SIGNALS = ROOT / "inbox" / "signals"
        SELECTED = ROOT / "topics" / "selected"
        ETHNO = ROOT / "ethnography"
        CITATIONS = ROOT / "citations"
        SIGNALS.mkdir(parents=True)
        SELECTED.mkdir(parents=True)
        (SIGNALS / "t.jsonl").write_text(
            json.dumps({
                "id": "sig_hn1",
                "source": "hn",
                "url": "https://news.ycombinator.com/item?id=12345",
                "title": "Show HN: Agent memory tiers for production workflows",
                "summary": "113 pts · We split rules, cache, and weights with audit logs for governed agents.",
            }) + "\n"
            + json.dumps({
                "id": "sig_sub1",
                "source": "substack",
                "url": "https://karozieminski.substack.com/p/agent-memory-governance",
                "title": "Agent memory governance in production",
                "summary": "Teams keep prompt rules and fine-tuned weights as parallel memory stores.",
            }) + "\n"
        )
        (SELECTED / f"{slug}.md").write_text(
            "- Show HN: Agent memory tiers — https://news.ycombinator.com/item?id=12345\n"
        )
        import importlib
        import field_expansion as fe
        fe.ROOT = ROOT
        fe.SIGNALS = SIGNALS
        fe.SELECTED = SELECTED
        fe.ETHNO = ETHNO
        fe.CITATIONS = CITATIONS
        fe._fetch_hn_thread = lambda iid: [{
            "text": "In production we kept prompts as the system of record until drift became visible.",
            "source_type": "hn_comment",
            "author_voice": "practitioner",
            "url": f"https://news.ycombinator.com/item?id={iid}",
        }]
        fe._fetch_substack_post = lambda u: [{
            "text": "In production we kept prompt rules and fine-tuned weights as two memory stores that drift apart without governance.",
            "source_type": "substack_post",
            "author_voice": "practitioner",
            "url": u,
            "title": "Agent memory governance",
        }]
        r = fe.expand(slug)
        assert r["corpus"] >= 2
        assert "substack" in r["channels"]
        assert (ETHNO / slug / "field_corpus.jsonl").exists()
        ROOT, SIGNALS, SELECTED, ETHNO, CITATIONS = saved
    print("field_expansion selftest OK")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--root", type=Path, help="project root (ethnography/<slug>/")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.slug:
        ap.error("slug required")
    if args.root:
        _bind_root(_project_root(args.root))
    r = expand(args.slug)
    print(f"field_expansion {args.slug}: {r['corpus']} corpus rows, {r['quotes']} quotes, channels={r['channels']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())