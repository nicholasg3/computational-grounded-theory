#!/usr/bin/env python3
"""gather.py — tiered field-source harvest for qualitative IS research.

Loads references/tier-registry.json and writes scored corpus rows to:
  ethnography/<slug>/tier_corpus.jsonl   (this run)
  ethnography/<slug>/field_corpus.jsonl  (merged append)

  python3 gather.py <slug>
  python3 gather.py <slug> --tiers 1,2,3
  python3 gather.py <slug> --dry-run
  python3 gather.py <slug> --no-snowball
  python3 gather.py <slug> --snowball-depth 2
  python3 gather.py --selftest
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
REGISTRY_PATH = SKILL / "references" / "tier-registry.json"

try:
    from fulltext import enrich_corpus, enrich_row, arxiv_id_from_url, arxiv_pdf_url
except ImportError:
    enrich_corpus = enrich_row = arxiv_id_from_url = arxiv_pdf_url = None  # type: ignore

try:
    from youtube_transcript import fetch_youtube_discourse, video_id_from_url
except ImportError:
    fetch_youtube_discourse = video_id_from_url = None  # type: ignore

# strategic-publishing root (sibling under ai-agents-workspace)
def _default_sp_root() -> Path:
    candidates = [
        SKILL.parents[2] / "ai-agents-workspace" / "Projects-for-agents" / "strategic-publishing",
        Path.home() / "code" / "ai-agents-workspace" / "Projects-for-agents" / "strategic-publishing",
        Path.cwd(),
    ]
    for p in candidates:
        if (p / "topics").is_dir() and (p / "ethnography").is_dir():
            return p
    return candidates[0]


SP_ROOT = _default_sp_root()
RETWEET_ANALYZED = SP_ROOT.parent / "retweet-library" / "analyzed"
MAILTO = "1nicholasgarcia@gmail.com"
OPENALEX = "https://api.openalex.org/works"
SEMANTIC_SCHOLAR = "https://api.semanticscholar.org/graph/v1/paper/search"

UA = f"FieldSources/1.0 (tiered-gather; mailto:{MAILTO})"
QUERY_STOP = set(
    "the a an of for and or to in on with how why what who when where this that "
    "is are be as by from into".split()
)
HN_ALGOLIA = "https://hn.algolia.com/api/v1"
PULLPUSH_REDDIT = "https://api.pullpush.io/reddit/search/submission"
STACKEXCHANGE_API = "https://api.stackexchange.com/2.3"
SEC_EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"
TOPIC_RE = re.compile(
    r"\b(agent|memory|rule|prompt|weight|policy|orchestrat|rout|ensemble|"
    r"multi-?model|experiential|governance|audit|workflow|llm|context)\w*\b",
    re.I,
)
MANUAL_TIER_MAP = {
    "keynotes": 1,
    "proceedings": 1,
    "linkedin": 2,
    "hedge_fund": 2,
    "interviews": 4,
    "podcasts": 4,
    "transcripts": 4,
}
DEFAULT_SNOWBALL = {
    "enabled": True,
    "max_depth": 1,
    "max_per_seed": 8,
    "max_total": 80,
    "min_seed_relevance": 3,
    "follow_citations": True,
    "follow_links": True,
    "prefer_oa_citations": False,
    "skip_domains": [
        "twitter.com", "x.com", "facebook.com", "instagram.com", "youtube.com",
        "youtu.be", "linkedin.com", "t.co", "bit.ly", "goo.gl", "mailto:",
        "subscribe", "unsubscribe", "feedburner.com", "doubleclick.net",
    ],
}
URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.I)
DOI_RE = re.compile(r"(?:doi[:\s]*)?(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.I)
ARXIV_RE = re.compile(r"arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5}(?:v\d+)?)", re.I)
OPENALEX_ID_RE = re.compile(r"openalex\.org/(W\d+)", re.I)
SCHOLARLY_ADAPTERS = frozenset({
    "arxiv", "openalex_oa", "semantic_scholar_oa", "snowball_citation",
})
LINK_ADAPTERS = frozenset({
    "rss", "substack_rss", "hn", "reddit", "stackoverflow", "youtube", "signals",
    "retweet_library", "snowball_link",
})


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_registry():
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def _get_json(url, timeout=25):
    return json.loads(_get(url, timeout=timeout))


def _strip_html(html):
    t = re.sub(r"<script[^>]*>.*?</script>", " ", html or "", flags=re.I | re.S)
    t = re.sub(r"<style[^>]*>.*?</style>", " ", t, flags=re.I | re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _truncate(s, n=500):
    s = re.sub(r"\s+", " ", (s or "")).strip()
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"


def _topic_terms(slug, root: Path):
    terms = set()
    for p in (root / "grounded" / slug / "theory.json", root / "topics" / "selected" / f"{slug}.md"):
        if p.exists():
            terms.update(re.findall(r"[a-z]{4,}", p.read_text(encoding="utf-8", errors="replace").lower()))
    return terms


def _topic_query(slug, root: Path, extra_terms: str = "") -> str:
    """Build an OpenAlex/Semantic Scholar query from the topic brief."""
    parts = []
    brief = root / "topics" / "selected" / f"{slug}.md"
    if brief.exists():
        text = brief.read_text(encoding="utf-8", errors="replace")
        wt = re.search(r"\*\*Working title:\*\*\s*(.+)", text)
        if wt:
            parts.append(wt.group(1).strip())
        thesis = re.search(r"^## Thesis.*?\n(.*?)(?=^## |\Z)", text, re.S | re.M | re.I)
        if thesis and thesis.group(1).strip():
            parts.append(thesis.group(1).strip()[:220])
        if not parts:
            for line in text.splitlines():
                s = line.strip().lstrip("- ").strip()
                if s and not s.startswith("#") and len(s) > 20:
                    parts.append(s[:180])
                    break
    if not parts:
        parts.append(slug.replace("-", " "))
    if extra_terms:
        parts.append(extra_terms.strip())
    q = " ".join(parts)
    return re.sub(r"\s+", " ", q)[:320]


def _reconstruct_abstract(inv):
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def _work_venue(work):
    loc = work.get("primary_location") or {}
    src = loc.get("source") or {}
    return src.get("display_name") or loc.get("raw_source_name") or ""


def _oa_pdf_url(work, doi: str) -> str:
    """Resolve best OA PDF: OpenAlex → Unpaywall → Semantic Scholar."""
    loc = work.get("best_oa_location") or {}
    for cand in (
        loc.get("pdf_url"),
        loc.get("url_for_pdf") if isinstance(loc.get("url_for_pdf"), str) else None,
    ):
        if cand:
            return cand
    if doi:
        try:
            d = _get_json(f"https://api.unpaywall.org/v2/{doi}?email={MAILTO}", timeout=15)
            uloc = d.get("best_oa_location") or {}
            return uloc.get("url_for_pdf") or uloc.get("url") or ""
        except Exception:
            pass
        try:
            d = _get_json(
                "https://api.semanticscholar.org/graph/v1/paper/DOI:"
                + urllib.parse.quote(doi)
                + "?fields=openAccessPdf",
                timeout=15,
            )
            return (d.get("openAccessPdf") or {}).get("url") or ""
        except Exception:
            pass
    return ""


def _openalex_work_to_item(w, *, require_oa: bool = False):
    loc = w.get("best_oa_location") or {}
    is_oa = bool(loc.get("is_oa") or w.get("open_access", {}).get("is_oa"))
    if require_oa and not is_oa:
        return None
    doi = (w.get("doi") or "").replace("https://doi.org/", "")
    abstract = _reconstruct_abstract(w.get("abstract_inverted_index"))[:1200]
    pdf_url = _oa_pdf_url(w, doi) if is_oa else ""
    landing = (
        pdf_url
        or loc.get("landing_page_url")
        or (f"https://doi.org/{doi}" if doi else w.get("id", ""))
    )
    venue = _work_venue(w)
    title = (w.get("display_name") or "(untitled)").strip()
    year = w.get("publication_year")
    wtype = w.get("type") or "article"
    summary = _truncate(abstract or title)
    if venue:
        summary = f"[{venue}] {summary}" if not year else f"[{venue} {year}] {summary}"
    oa_id = w.get("id") or ""
    if oa_id and not oa_id.startswith("http"):
        oa_id = f"https://openalex.org/{oa_id}"
    return {
        "title": title,
        "url": landing,
        "summary": summary,
        "source_type": "openalex_oa",
        "tier": 3,
        "voice": "academic",
        "doi": doi,
        "year": year,
        "venue": venue,
        "work_type": wtype,
        "pdf_url": pdf_url,
        "access": "OA" if is_oa else "paywalled",
        "openalex_id": oa_id,
    }


def fetch_openalex_oa(
    query: str,
    *,
    oa_filter: str = "is_oa:true",
    types: list | None = None,
    per_page: int = 25,
    from_year: int | None = None,
):
    """Harvest open-access scholarly works (articles, proceedings, preprints, reviews)."""
    filters = [oa_filter]
    if types and "type:" not in oa_filter:
        filters.append("type:" + "|".join(types))
    if from_year:
        filters.append(f"from_publication_date:{from_year}-01-01")
    url = (
        f"{OPENALEX}?"
        + urllib.parse.urlencode({
            "search": query,
            "filter": ",".join(filters),
            "per_page": per_page,
            "sort": "relevance_score:desc",
            "mailto": MAILTO,
        })
    )
    data = _get_json(url, timeout=40)
    out = []
    for w in data.get("results") or []:
        it = _openalex_work_to_item(w, require_oa=True)
        if it:
            out.append(it)
    return out


def _openalex_fetch_work(doi: str = "", openalex_id: str = ""):
    if doi:
        url = f"https://api.openalex.org/works/doi:{urllib.parse.quote(doi)}?mailto={MAILTO}"
    elif openalex_id:
        wid = openalex_id.rsplit("/", 1)[-1]
        url = f"https://api.openalex.org/works/{wid}?mailto={MAILTO}"
    else:
        return None
    try:
        return _get_json(url, timeout=25)
    except Exception:
        return None


def _openalex_fetch_works_by_ids(openalex_ids: list[str]):
    if not openalex_ids:
        return []
    short = [i.rsplit("/", 1)[-1] for i in openalex_ids]
    url = (
        f"{OPENALEX}?"
        + urllib.parse.urlencode({
            "filter": "ids.openalex:" + "|".join(short[:50]),
            "per_page": min(len(short), 50),
            "mailto": MAILTO,
        })
    )
    try:
        return _get_json(url, timeout=35).get("results") or []
    except Exception:
        return []


def _semantic_scholar_references(doi: str, limit: int = 12):
    if not doi:
        return []
    try:
        data = _get_json(
            "https://api.semanticscholar.org/graph/v1/paper/DOI:"
            + urllib.parse.quote(doi)
            + "?fields=references.title,references.externalIds,references.url,references.year",
            timeout=25,
        )
    except Exception:
        return []
    out = []
    for ref in (data.get("references") or [])[:limit]:
        if not ref:
            continue
        rdoi = (ref.get("externalIds") or {}).get("DOI") or ""
        title = (ref.get("title") or "").strip()
        if not title and not rdoi:
            continue
        out.append({
            "title": title or f"DOI:{rdoi}",
            "url": ref.get("url") or (f"https://doi.org/{rdoi}" if rdoi else ""),
            "summary": _truncate(title),
            "doi": rdoi,
            "year": ref.get("year"),
            "tier": 3,
            "voice": "academic",
            "access": "unknown",
        })
    return out


def _extract_dois(text: str) -> list[str]:
    seen, out = set(), []
    for m in DOI_RE.finditer(text or ""):
        d = m.group(1).rstrip(").,;")
        if d.lower() not in seen:
            seen.add(d.lower())
            out.append(d)
    return out


def _extract_urls(text: str, skip_domains: list[str]) -> list[str]:
    seen, out = set(), []
    for m in URL_RE.finditer(text or ""):
        u = m.group(0).rstrip(").,;\"'")
        low = u.lower()
        if any(s in low for s in skip_domains):
            continue
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def _link_should_skip(url: str, skip_domains: list[str]) -> bool:
    low = (url or "").lower()
    return not url.startswith("http") or any(s in low for s in skip_domains)


def _fetch_link_preview(url: str):
    """Best-effort title + excerpt for an outbound blog/paper link."""
    try:
        html = _get(url, timeout=18)
    except Exception:
        return None
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = _strip_html(title_m.group(1)) if title_m else ""
    desc_m = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.I,
    )
    if not desc_m:
        desc_m = re.search(
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
            html, re.I,
        )
    body = _strip_html(desc_m.group(1)) if desc_m else ""
    if not body:
        body = _strip_html(re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S))[:1200]
    if not title and not body:
        return None
    return {"title": title or url, "summary": _truncate(body or title, 800), "url": url}


def _corpus_index(corpus: list) -> tuple[set[str], set[str]]:
    urls, dois = set(), set()
    for row in corpus:
        if row.get("url"):
            urls.add(row["url"].rstrip("/"))
        if row.get("doi"):
            dois.add(row["doi"].lower())
    return urls, dois


def _snowball_citations_from_seed(seed: dict, cfg: dict) -> list[dict]:
    items = []
    text = f"{seed.get('title', '')} {seed.get('text', '')} {seed.get('summary', '')}"
    dois = []
    if seed.get("doi"):
        dois.append(seed["doi"])
    dois.extend(_extract_dois(text))
    seen_doi = set()
    for doi in dois:
        if doi.lower() in seen_doi:
            continue
        seen_doi.add(doi.lower())
        work = _openalex_fetch_work(doi=doi)
        ref_ids = []
        if work:
            ref_ids = work.get("referenced_works") or []
        if ref_ids:
            for w in _openalex_fetch_works_by_ids(ref_ids[: cfg["max_per_seed"]]):
                it = _openalex_work_to_item(w, require_oa=cfg.get("prefer_oa_citations", False))
                if it:
                    items.append(it)
        elif cfg.get("follow_citations"):
            items.extend(_semantic_scholar_references(doi, limit=cfg["max_per_seed"]))
        if len(items) >= cfg["max_per_seed"]:
            break

    # arXiv IDs embedded in text
    for ax in ARXIV_RE.findall(text)[:3]:
        try:
            import xml.etree.ElementTree as ET
            qurl = f"http://export.arxiv.org/api/query?id_list={ax}"
            root = ET.fromstring(_get(qurl, timeout=20))
            ns = {"a": "http://www.w3.org/2005/Atom"}
            entry = root.find("a:entry", ns)
            if entry is None:
                continue
            title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
            summary = (entry.findtext("a:summary", default="", namespaces=ns) or "").strip()
            link = f"https://arxiv.org/abs/{ax}"
            items.append({
                "title": title,
                "url": link,
                "summary": _truncate(summary),
                "tier": 3,
                "voice": "academic",
                "access": "OA",
                "work_type": "preprint",
            })
        except Exception:
            continue
        if len(items) >= cfg["max_per_seed"]:
            break
    return items[: cfg["max_per_seed"]]


def _snowball_links_from_seed(seed: dict, cfg: dict) -> list[dict]:
    text = seed.get("text") or seed.get("summary") or ""
    urls = _extract_urls(text, cfg.get("skip_domains", []))
    if seed.get("url"):
        urls = [u for u in urls if u.rstrip("/") != seed["url"].rstrip("/")]
    items = []
    for url in urls[: cfg["max_per_seed"]]:
        if _link_should_skip(url, cfg.get("skip_domains", [])):
            continue
        preview = _fetch_link_preview(url)
        if preview:
            items.append({
                "title": preview["title"],
                "url": preview["url"],
                "summary": preview["summary"],
                "tier": seed.get("tier", 1),
                "voice": seed.get("voice", "field"),
                "access": "web",
            })
        time.sleep(0.2)
    return items


def snowball_expand(
    corpus: list,
    quotes: list,
    topic_terms: set,
    session: str,
    cfg: dict,
    stats: dict,
    min_relevance: int,
):
    """Theoretical sampling via citation/link snowball from relevant seeds."""
    if not cfg.get("enabled", True):
        return 0

    added = 0
    seen_urls, seen_dois = _corpus_index(corpus)
    frontier = [
        r for r in corpus
        if r.get("relevance", 0) >= cfg.get("min_seed_relevance", 3)
        and not str(r.get("id", "")).startswith("snow_")
    ]

    for hop in range(1, int(cfg.get("max_depth", 1)) + 1):
        if added >= cfg.get("max_total", 80):
            break
        new_rows = []
        for seed in frontier:
            if added >= cfg.get("max_total", 80):
                break
            seed_adapter = seed.get("adapter", "")
            candidates = []

            if cfg.get("follow_citations") and (
                seed.get("doi")
                or seed_adapter in SCHOLARLY_ADAPTERS
                or seed.get("work_type")
            ):
                try:
                    candidates.extend(
                        ("citation", it) for it in _snowball_citations_from_seed(seed, cfg)
                    )
                except Exception as e:
                    stats["warnings"].append(f"snowball/citation/{seed.get('id')}: {e}")

            if cfg.get("follow_links") and (
                seed_adapter in LINK_ADAPTERS
                or seed.get("source_type") in ("substack", "engineering_blog", "practitioner_substack")
                or "http" in (seed.get("text") or "")
            ):
                try:
                    candidates.extend(
                        ("link", it) for it in _snowball_links_from_seed(seed, cfg)
                    )
                except Exception as e:
                    stats["warnings"].append(f"snowball/link/{seed.get('id')}: {e}")

            per_seed = 0
            for kind, it in candidates:
                if added >= cfg.get("max_total", 80) or per_seed >= cfg.get("max_per_seed", 8):
                    break
                url = (it.get("url") or "").rstrip("/")
                doi = (it.get("doi") or "").lower()
                if url and url in seen_urls:
                    continue
                if doi and doi in seen_dois:
                    continue
                rel = _relevance(f"{it.get('title', '')} {it.get('summary', '')}", topic_terms)
                if rel < min_relevance:
                    continue
                stype = "snowball_citation" if kind == "citation" else "snowball_link"
                row = {
                    "id": _make_id(f"snow_{kind}", doi or url or it.get("title", "")),
                    "captured_at": session,
                    "tier": it.get("tier", seed.get("tier", 3)),
                    "source_channel": "snowball",
                    "source_type": stype,
                    "adapter": "snowball",
                    "status": "live",
                    "url": it.get("url", ""),
                    "title": it.get("title", ""),
                    "text": f"{it.get('title', '')}. {it.get('summary', '')}",
                    "relevance": rel,
                    "voice": it.get("voice", seed.get("voice", "field")),
                    "snowball_from": seed.get("id"),
                    "snowball_hop": hop,
                    "snowball_kind": kind,
                    "snowball_via": doi or url,
                }
                for k in ("doi", "year", "venue", "work_type", "pdf_url", "access", "openalex_id"):
                    if it.get(k):
                        row[k] = it[k]
                new_rows.append(row)
                if url:
                    seen_urls.add(url)
                if doi:
                    seen_dois.add(doi)
                per_seed += 1
                added += 1

        for row in new_rows:
            _append_row(corpus, quotes, row, row["text"], topic_terms)
            stats["by_tier"][str(row["tier"])] = stats["by_tier"].get(str(row["tier"]), 0) + 1
            stats["by_adapter"]["snowball"] = stats["by_adapter"].get("snowball", 0) + 1

        if not new_rows:
            break
        frontier = new_rows

    stats["snowball_added"] = added
    return added


def fetch_semantic_scholar_oa(query: str, limit: int = 20):
    """Semantic Scholar search — returns works with openAccessPdf when available."""
    url = (
        f"{SEMANTIC_SCHOLAR}?"
        + urllib.parse.urlencode({
            "query": query,
            "limit": limit,
            "fields": "title,abstract,year,externalIds,openAccessPdf,venue,publicationTypes",
        })
    )
    data = _get_json(url, timeout=30)
    out = []
    for p in data.get("data") or []:
        oa = p.get("openAccessPdf") or {}
        pdf_url = oa.get("url") or ""
        if not pdf_url:
            continue
        doi = (p.get("externalIds") or {}).get("DOI") or ""
        venue = p.get("venue") or ""
        title = (p.get("title") or "(untitled)").strip()
        abstract = _truncate(p.get("abstract") or "")
        year = p.get("year")
        summary = abstract or title
        if venue:
            summary = f"[{venue}] {summary}"
        out.append({
            "title": title,
            "url": pdf_url,
            "summary": summary,
            "source_type": "semantic_scholar_oa",
            "tier": 3,
            "voice": "academic",
            "doi": doi,
            "year": year,
            "venue": venue,
            "work_type": ",".join(p.get("publicationTypes") or []),
            "pdf_url": pdf_url,
            "access": "OA",
        })
    return out


def _download_oa_pdf(pdf_url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(pdf_url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=45) as r:
            data = r.read()
        if data[:4] != b"%PDF":
            return False
        dest.write_bytes(data)
        return True
    except Exception:
        return False


def _relevance(text, topic_terms):
    t = text or ""
    score = 0
    if TOPIC_RE.search(t):
        score += 4
    for term in topic_terms:
        if term in t.lower():
            score += 1
    return score


def _make_id(prefix, url_or_title):
    h = hashlib.sha1((url_or_title or prefix).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{h}"


def _quote_candidates(text, source_id, source_type, url, site, voice, tier, topic_terms):
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
            "author_voice": voice,
            "tier": tier,
        })
    return quotes


def parse_rss(xml, source_type, tier, voice):
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
        if title or body:
            items.append({
                "title": title,
                "url": link,
                "summary": _truncate(body or title),
                "source_type": source_type,
                "tier": tier,
                "voice": voice,
            })
    return items


def fetch_arxiv(query, max_results=25, tier=3):
    url = (
        "http://export.arxiv.org/api/query?"
        + urllib.parse.urlencode({
            "search_query": query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": max_results,
        })
    )
    xml = _get(url, timeout=40)
    out = []
    for entry in re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL):
        title = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
        link = re.search(r"<id>(.*?)</id>", entry)
        summ = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
        if title and link:
            abs_url = link.group(1).strip()
            ax = arxiv_id_from_url(abs_url) if arxiv_id_from_url else ""
            pdf_url = arxiv_pdf_url(ax) if ax and arxiv_pdf_url else ""
            out.append({
                "title": title.group(1).strip().replace("\n", " "),
                "url": abs_url,
                "summary": _truncate(summ.group(1) if summ else ""),
                "source_type": "arxiv",
                "tier": tier,
                "voice": "academic",
                "pdf_url": pdf_url,
                "access": "OA",
            })
    return out


def _pullpush_reddit_search(params, timeout=45):
    url = PULLPUSH_REDDIT + "?" + urllib.parse.urlencode(params)
    return _get_json(url, timeout=timeout).get("data", [])


def fetch_reddit(
    query="AI agent memory",
    subreddits=None,
    since_days=365,
    min_score=10,
    max_hits=30,
):
    """Reddit practitioner discourse via PullPush archive (reddit.com JSON often 403)."""
    cutoff = int((datetime.now(timezone.utc) - timedelta(days=since_days)).timestamp())
    out = []
    seen = set()

    def ingest(hit):
        title = (hit.get("title") or "").strip()
        if not title:
            return
        score = int(hit.get("score") or 0)
        if score < min_score:
            return
        created = int(hit.get("created_utc") or 0)
        if created and created < cutoff and score < max(min_score * 3, 50):
            return
        post_id = hit.get("id") or ""
        if post_id in seen:
            return
        seen.add(post_id)
        selftext = (hit.get("selftext") or "").strip()
        if selftext in ("[removed]", "[deleted]"):
            selftext = ""
        permalink = hit.get("permalink") or ""
        if permalink.startswith("/"):
            link = f"https://www.reddit.com{permalink}"
        else:
            link = hit.get("url") or permalink
        sub = hit.get("subreddit") or ""
        summary = _truncate(f"{score} pts · r/{sub} · {title}. {selftext}")
        out.append({
            "title": title,
            "url": link,
            "summary": summary,
            "source_type": "reddit",
            "tier": 1,
            "voice": "practitioner",
            "reddit_id": post_id,
            "subreddit": sub,
            "score": score,
        })

    per_sub = max(5, max_hits // max(len(subreddits or [""]), 1))
    try:
        for hit in _pullpush_reddit_search({
            "q": query,
            "size": max_hits,
            "sort": "desc",
            "sort_type": "score",
        }):
            ingest(hit)
            if len(out) >= max_hits:
                break
    except Exception:
        pass

    for sub in subreddits or []:
        if len(out) >= max_hits:
            break
        try:
            for hit in _pullpush_reddit_search({
                "subreddit": sub,
                "q": query,
                "size": per_sub,
                "sort": "desc",
                "sort_type": "score",
            }):
                ingest(hit)
                if len(out) >= max_hits:
                    break
        except Exception:
            continue
        time.sleep(0.5)

    return out[:max_hits]


def fetch_stackoverflow(
    query="agent memory LLM",
    tags=None,
    min_score=3,
    max_hits=25,
    site="stackoverflow",
):
    """Stack Overflow / Stack Exchange practitioner Q&A via API 2.3."""
    tag_sets = [tags] if tags else [None]
    if tags and len(tags) > 1:
        tag_sets = [[t] for t in tags] + [None]

    out = []
    seen_q = set()
    for tag_group in tag_sets:
        if len(out) >= max_hits:
            break
        params = {
            "order": "desc",
            "sort": "votes",
            "q": query,
            "site": site,
            "pagesize": min(max_hits, 100),
            "filter": "withbody",
        }
        if tag_group:
            params["tagged"] = ";".join(tag_group)
        url = f"{STACKEXCHANGE_API}/search/advanced?" + urllib.parse.urlencode(params)
        try:
            data = _get_json(url, timeout=30)
        except Exception:
            continue
        for item in data.get("items", []):
            score = int(item.get("score") or 0)
            if score < min_score:
                continue
            qid = item.get("question_id") or item.get("id")
            if qid in seen_q:
                continue
            seen_q.add(qid)
            title = html.unescape(item.get("title") or "")
            body = html.unescape(re.sub(r"<[^>]+>", " ", item.get("body") or ""))
            body = re.sub(r"\s+", " ", body).strip()
            link = item.get("link") or f"https://stackoverflow.com/questions/{qid}"
            tags_list = item.get("tags") or []
            summary = _truncate(f"{score} votes · {title}. {body}")
            out.append({
                "title": title,
                "url": link,
                "summary": summary,
                "source_type": "stackoverflow",
                "tier": 1,
                "voice": "practitioner",
                "question_id": qid,
                "tags": tags_list,
                "score": score,
            })
            if len(out) >= max_hits:
                break
        time.sleep(0.2)
    return out


def fetch_hn(since_days=7, query="AI", min_points=40, max_hits=30):
    cutoff = int((datetime.now(timezone.utc) - timedelta(days=since_days)).timestamp())
    url = (
        f"{HN_ALGOLIA}/search_by_date?"
        + urllib.parse.urlencode({
            "tags": "story",
            "query": query,
            "numericFilters": f"created_at_i>{cutoff},points>{min_points}",
            "hitsPerPage": max_hits,
        })
    )
    data = _get_json(url)
    out = []
    for h in data.get("hits", []):
        title = h.get("title") or h.get("story_title") or ""
        link = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        out.append({
            "title": title,
            "url": link,
            "summary": _truncate(f"{h.get('points', 0)} pts · {title}"),
            "source_type": "hn",
            "tier": 1,
            "voice": "practitioner",
        })
    return out


def load_signals(root: Path, topic_terms, min_relevance=2):
    signals_dir = root / "inbox" / "signals"
    rows = []
    if not signals_dir.exists():
        return rows
    for path in sorted(signals_dir.glob("*.jsonl"), reverse=True)[:14]:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                s = json.loads(line)
            except Exception:
                continue
            blob = f"{s.get('title', '')}. {s.get('summary', '')}"
            rel = _relevance(blob, topic_terms)
            if rel < min_relevance:
                continue
            src = s.get("source") or "signal"
            tier = {"arxiv": 3, "substack": 1, "hn": 1, "rss": 4}.get(src, 2)
            rows.append({
                "title": s.get("title", ""),
                "url": s.get("url", ""),
                "summary": _truncate(s.get("summary", "")),
                "source_type": src,
                "tier": tier,
                "voice": "practitioner" if src in ("hn", "substack") else "field",
                "signal_id": s.get("id"),
            })
    return rows


def load_retweet_library():
    rows = []
    if not RETWEET_ANALYZED.exists():
        return rows
    for p in sorted(RETWEET_ANALYZED.glob("*.md")):
        if p.name.endswith(".bak"):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        lines = text.splitlines()
        title = next((ln.lstrip("# ").strip() for ln in lines if ln.strip().startswith("#")), p.name)
        m = re.search(r"Source:\s*(https?://\S+)", text)
        url = m.group(1) if m else f"retweet-library://{p.name}"
        summary = ""
        for ln in lines:
            s = ln.strip()
            if s and not s.startswith(("#", ">", "-", "|", "*", "**Object")):
                summary = s
                break
        rows.append({
            "title": title,
            "url": url,
            "summary": _truncate(summary or title),
            "source_type": "x-retweet-library",
            "tier": 1,
            "voice": "practitioner",
        })
    return rows


def fetch_sec_edgar(query="artificial intelligence", max_results=10):
    """Public SEC full-text search — earnings 8-K and exhibit filings."""
    url = (
        "https://efts.sec.gov/LATEST/search-index?"
        + urllib.parse.urlencode({
            "q": f'"{query}"',
            "dateRange": "custom",
            "startdt": (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d"),
            "enddt": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "forms": "8-K",
        })
    )
    try:
        data = _get_json(url, timeout=30)
    except Exception:
        return []
    out = []
    for hit in (data.get("hits") or {}).get("hits", [])[:max_results]:
        src = hit.get("_source") or {}
        title = src.get("display_names", [""])[0] if src.get("display_names") else ""
        form = (src.get("form") or ["8-K"])[0]
        filed = (src.get("file_date") or [""])[0]
        cik = (src.get("ciks") or [""])[0]
        adsh = src.get("adsh", "")
        link = f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}" if cik and adsh else ""
        out.append({
            "title": f"{title} — {form} ({filed})".strip(" —"),
            "url": link or f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}",
            "summary": _truncate(f"SEC {form} filing mentioning {query}"),
            "source_type": "earnings_call",
            "tier": 4,
            "voice": "institutional",
        })
    return out


def load_manual_intake(slug, root: Path, tier_filter: set[int]):
    base = root / "ethnography" / slug / "manual_intake"
    rows = []
    if not base.is_dir():
        return rows
    for path in sorted(base.rglob("*")):
        if path.suffix.lower() not in (".md", ".txt", ".html"):
            continue
        rel = path.relative_to(base)
        st = rel.parts[0] if len(rel.parts) > 1 else "manual"
        tier = MANUAL_TIER_MAP.get(st, 1)
        if tier not in tier_filter:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")[:8000]
        src_m = re.search(r"Source:\s*(https?://\S+)", text)
        rows.append({
            "title": path.stem.replace("-", " "),
            "url": src_m.group(1) if src_m else f"file://{path}",
            "summary": _truncate(text, 800),
            "source_type": st,
            "tier": tier,
            "voice": "practitioner",
            "full_text": text,
        })
    return rows


def _append_row(corpus, quotes, row, quotes_text, topic_terms):
    corpus.append(row)
    quotes.extend(_quote_candidates(
        quotes_text, row["id"], row["source_type"], row["url"],
        row["source_channel"], row["voice"], row["tier"], topic_terms,
    ))


def _scholarly_row(session, tier_n, stype, spec, it, rel, voice, status):
    row = {
        "id": _make_id(f"t{tier_n}_{stype}", it.get("doi") or it["url"] or it["title"]),
        "captured_at": session,
        "tier": tier_n,
        "source_channel": stype,
        "source_type": stype,
        "adapter": spec.get("adapter", ""),
        "status": status,
        "url": it["url"],
        "title": it["title"],
        "text": f"{it['title']}. {it['summary']}",
        "relevance": rel,
        "voice": voice,
        "access": it.get("access", "OA"),
    }
    for k in ("doi", "year", "venue", "work_type", "pdf_url", "openalex_id"):
        if it.get(k):
            row[k] = it[k]
    return row


def _snowball_config(reg: dict, depth_override: int | None = None) -> dict:
    cfg = dict(DEFAULT_SNOWBALL)
    cfg.update(reg.get("snowball") or {})
    if depth_override is not None:
        cfg["max_depth"] = depth_override
    return cfg


def gather(
    slug,
    tiers=None,
    root=None,
    min_relevance=2,
    dry_run=False,
    download_pdfs=False,
    download_fulltext=True,
    snowball=True,
    snowball_depth=None,
):
    root = root or SP_ROOT
    tiers = tiers or [1, 2, 3, 4]
    tier_set = set(tiers)
    reg = _load_registry()
    topic_terms = _topic_terms(slug, root)
    session = _now()
    corpus = []
    quotes = []
    stats = {"by_tier": {}, "by_adapter": {}, "warnings": []}

    def bump(key, bucket):
        bucket[key] = bucket.get(key, 0) + 1

    for tier_key, tier_def in reg["tiers"].items():
        tier_n = int(tier_key)
        if tier_n not in tier_set:
            continue
        for stype, spec in tier_def.get("source_types", {}).items():
            adapter = spec.get("adapter", "")
            voice = spec.get("voice", "field")
            status = spec.get("status", "manual")

            if adapter in ("rss", "substack_rss"):
                for feed in spec.get("feeds", []):
                    try:
                        xml = _get(feed)
                        items = parse_rss(xml, stype, tier_n, voice)
                        for it in items:
                            rel = _relevance(f"{it['title']} {it['summary']}", topic_terms)
                            if rel < min_relevance:
                                continue
                            row = {
                                "id": _make_id(f"t{tier_n}_{stype}", it["url"] or it["title"]),
                                "captured_at": session,
                                "tier": tier_n,
                                "source_channel": stype,
                                "source_type": stype,
                                "adapter": adapter,
                                "status": status,
                                "url": it["url"],
                                "title": it["title"],
                                "text": f"{it['title']}. {it['summary']}",
                                "relevance": rel,
                                "voice": voice,
                            }
                            _append_row(corpus, quotes, row, row["text"], topic_terms)
                            bump(str(tier_n), stats["by_tier"])
                            bump(adapter, stats["by_adapter"])
                    except Exception as e:
                        stats["warnings"].append(f"{feed}: {e}")
                        print(f"  [warn] {feed}: {e}", file=sys.stderr)
                    time.sleep(0.25)

            elif adapter == "arxiv":
                try:
                    for it in fetch_arxiv(spec.get("query", "cat:cs.AI"), tier=tier_n):
                        rel = _relevance(f"{it['title']} {it['summary']}", topic_terms)
                        if rel < min_relevance:
                            continue
                        row = {
                            "id": _make_id("t3_arxiv", it["url"]),
                            "captured_at": session,
                            "tier": tier_n,
                            "source_channel": "arxiv",
                            "source_type": "arxiv",
                            "adapter": "arxiv",
                            "status": status,
                            "url": it["url"],
                            "title": it["title"],
                            "text": f"{it['title']}. {it['summary']}",
                            "relevance": rel,
                            "voice": "academic",
                            "access": "OA",
                        }
                        if it.get("pdf_url"):
                            row["pdf_url"] = it["pdf_url"]
                        _append_row(corpus, quotes, row, row["text"], topic_terms)
                        bump(str(tier_n), stats["by_tier"])
                        bump("arxiv", stats["by_adapter"])
                except Exception as e:
                    stats["warnings"].append(f"arxiv: {e}")
                    print(f"  [warn] arxiv: {e}", file=sys.stderr)

            elif adapter == "openalex_oa":
                query = (
                    _topic_query(slug, root, spec.get("extra_terms", ""))
                    if spec.get("query_from_topic", True)
                    else spec.get("query", slug.replace("-", " "))
                )
                try:
                    items = fetch_openalex_oa(
                        query,
                        oa_filter=spec.get("oa_filter", "is_oa:true"),
                        types=spec.get("types"),
                        per_page=spec.get("per_page", 25),
                        from_year=spec.get("from_year"),
                    )
                    for it in items:
                        rel = _relevance(f"{it['title']} {it['summary']}", topic_terms)
                        if rel < min_relevance:
                            continue
                        row = _scholarly_row(session, tier_n, stype, spec, it, rel, voice, status)
                        _append_row(corpus, quotes, row, row["text"], topic_terms)
                        bump(str(tier_n), stats["by_tier"])
                        bump("openalex_oa", stats["by_adapter"])
                    time.sleep(0.5)
                except Exception as e:
                    stats["warnings"].append(f"openalex_oa/{stype}: {e}")
                    print(f"  [warn] openalex_oa/{stype}: {e}", file=sys.stderr)

            elif adapter == "semantic_scholar_oa":
                query = (
                    _topic_query(slug, root, spec.get("extra_terms", ""))
                    if spec.get("query_from_topic", True)
                    else spec.get("query", slug.replace("-", " "))
                )
                try:
                    for it in fetch_semantic_scholar_oa(query, limit=spec.get("limit", 20)):
                        rel = _relevance(f"{it['title']} {it['summary']}", topic_terms)
                        if rel < min_relevance:
                            continue
                        row = _scholarly_row(session, tier_n, stype, spec, it, rel, voice, status)
                        _append_row(corpus, quotes, row, row["text"], topic_terms)
                        bump(str(tier_n), stats["by_tier"])
                        bump("semantic_scholar_oa", stats["by_adapter"])
                    time.sleep(0.5)
                except Exception as e:
                    stats["warnings"].append(f"semantic_scholar_oa: {e}")
                    print(f"  [warn] semantic_scholar_oa: {e}", file=sys.stderr)

            elif adapter == "hn":
                try:
                    for it in fetch_hn(
                        since_days=spec.get("since_days", 7),
                        query=spec.get("query", "AI"),
                        min_points=spec.get("min_points", 40),
                        max_hits=spec.get("max_hits", 30),
                    ):
                        rel = _relevance(f"{it['title']} {it['summary']}", topic_terms)
                        if rel < min_relevance:
                            continue
                        row = {
                            "id": _make_id("t1_hn", it["url"]),
                            "captured_at": session,
                            "tier": tier_n,
                            "source_channel": "hn",
                            "source_type": stype,
                            "adapter": "hn",
                            "status": status,
                            "url": it["url"],
                            "title": it["title"],
                            "text": f"{it['title']}. {it['summary']}",
                            "relevance": rel,
                            "voice": voice,
                        }
                        _append_row(corpus, quotes, row, row["text"], topic_terms)
                        bump(str(tier_n), stats["by_tier"])
                        bump("hn", stats["by_adapter"])
                except Exception as e:
                    stats["warnings"].append(f"hn: {e}")

            elif adapter == "reddit":
                try:
                    for it in fetch_reddit(
                        query=spec.get("query", "AI agent memory"),
                        subreddits=spec.get("subreddits"),
                        since_days=spec.get("since_days", 365),
                        min_score=spec.get("min_score", 10),
                        max_hits=spec.get("max_hits", 30),
                    ):
                        rel = _relevance(f"{it['title']} {it['summary']}", topic_terms)
                        if rel < min_relevance:
                            continue
                        row = {
                            "id": _make_id("t1_reddit", it.get("reddit_id") or it["url"]),
                            "captured_at": session,
                            "tier": tier_n,
                            "source_channel": "reddit",
                            "source_type": stype,
                            "adapter": "reddit",
                            "status": status,
                            "url": it["url"],
                            "title": it["title"],
                            "text": f"{it['title']}. {it['summary']}",
                            "relevance": rel,
                            "voice": voice,
                        }
                        if it.get("subreddit"):
                            row["subreddit"] = it["subreddit"]
                        if it.get("score") is not None:
                            row["score"] = it["score"]
                        _append_row(corpus, quotes, row, row["text"], topic_terms)
                        bump(str(tier_n), stats["by_tier"])
                        bump("reddit", stats["by_adapter"])
                except Exception as e:
                    stats["warnings"].append(f"reddit: {e}")
                    print(f"  [warn] reddit: {e}", file=sys.stderr)

            elif adapter == "stackoverflow":
                try:
                    for it in fetch_stackoverflow(
                        query=spec.get("query", "agent memory LLM"),
                        tags=spec.get("tags"),
                        min_score=spec.get("min_score", 3),
                        max_hits=spec.get("max_hits", 25),
                        site=spec.get("site", "stackoverflow"),
                    ):
                        rel = _relevance(f"{it['title']} {it['summary']}", topic_terms)
                        if rel < min_relevance:
                            continue
                        row = {
                            "id": _make_id("t1_so", str(it.get("question_id") or it["url"])),
                            "captured_at": session,
                            "tier": tier_n,
                            "source_channel": "stackoverflow",
                            "source_type": stype,
                            "adapter": "stackoverflow",
                            "status": status,
                            "url": it["url"],
                            "title": it["title"],
                            "text": f"{it['title']}. {it['summary']}",
                            "relevance": rel,
                            "voice": voice,
                        }
                        if it.get("tags"):
                            row["tags"] = it["tags"]
                        if it.get("score") is not None:
                            row["score"] = it["score"]
                        _append_row(corpus, quotes, row, row["text"], topic_terms)
                        bump(str(tier_n), stats["by_tier"])
                        bump("stackoverflow", stats["by_adapter"])
                    time.sleep(0.3)
                except Exception as e:
                    stats["warnings"].append(f"stackoverflow: {e}")
                    print(f"  [warn] stackoverflow: {e}", file=sys.stderr)

            elif adapter == "youtube":
                if fetch_youtube_discourse is None:
                    stats["warnings"].append(
                        "youtube: youtube_transcript.py missing — "
                        "run: python3 -m venv .venv && .venv/bin/pip install youtube-transcript-api"
                    )
                else:
                    try:
                        langs = spec.get("languages") or ["en"]
                        for it in fetch_youtube_discourse(
                            query=spec.get("query", "AI agent memory LLM"),
                            max_hits=spec.get("max_hits", 10),
                            languages=langs,
                            max_transcript_chars=spec.get("max_transcript_chars", 12000),
                        ):
                            blob = f"{it['title']}. {it.get('transcript') or it.get('summary', '')}"
                            rel = _relevance(blob, topic_terms)
                            if rel < min_relevance:
                                continue
                            row = {
                                "id": _make_id("t1_yt", it.get("video_id") or it["url"]),
                                "captured_at": session,
                                "tier": tier_n,
                                "source_channel": "youtube",
                                "source_type": stype,
                                "adapter": "youtube",
                                "status": status,
                                "url": it["url"],
                                "title": it["title"],
                                "text": _truncate(blob, spec.get("max_transcript_chars", 12000)),
                                "relevance": rel,
                                "voice": voice,
                                "video_id": it.get("video_id"),
                            }
                            if it.get("channel"):
                                row["channel"] = it["channel"]
                            if it.get("transcript"):
                                row["transcript"] = it["transcript"]
                            _append_row(corpus, quotes, row, row["text"], topic_terms)
                            bump(str(tier_n), stats["by_tier"])
                            bump("youtube", stats["by_adapter"])
                    except Exception as e:
                        stats["warnings"].append(f"youtube: {e}")
                        print(f"  [warn] youtube: {e}", file=sys.stderr)

            elif adapter == "signals":
                for it in load_signals(root, topic_terms, min_relevance=min_relevance):
                    if it["tier"] not in tier_set:
                        continue
                    row = {
                        "id": _make_id("sig", it.get("signal_id") or it["url"]),
                        "captured_at": session,
                        "tier": it["tier"],
                        "source_channel": it["source_type"],
                        "source_type": it["source_type"],
                        "adapter": "signals",
                        "status": status,
                        "url": it["url"],
                        "title": it["title"],
                        "text": f"{it['title']}. {it['summary']}",
                        "relevance": _relevance(f"{it['title']} {it['summary']}", topic_terms),
                        "voice": it["voice"],
                    }
                    _append_row(corpus, quotes, row, row["text"], topic_terms)
                    bump(str(it["tier"]), stats["by_tier"])
                    bump("signals", stats["by_adapter"])

            elif adapter == "retweet_library":
                for it in load_retweet_library():
                    rel = _relevance(f"{it['title']} {it['summary']}", topic_terms)
                    if rel < min_relevance:
                        continue
                    row = {
                        "id": _make_id("rt", it["url"]),
                        "captured_at": session,
                        "tier": tier_n,
                        "source_channel": "x-retweet-library",
                        "source_type": stype,
                        "adapter": "retweet_library",
                        "status": status,
                        "url": it["url"],
                        "title": it["title"],
                        "text": f"{it['title']}. {it['summary']}",
                        "relevance": rel,
                        "voice": voice,
                    }
                    _append_row(corpus, quotes, row, row["text"], topic_terms)
                    bump(str(tier_n), stats["by_tier"])
                    bump("retweet_library", stats["by_adapter"])

            elif adapter == "sec_edgar":
                try:
                    for it in fetch_sec_edgar(query=spec.get("query", "artificial intelligence")):
                        rel = _relevance(f"{it['title']} {it['summary']}", topic_terms)
                        if rel < min_relevance:
                            continue
                        row = {
                            "id": _make_id("sec", it["url"]),
                            "captured_at": session,
                            "tier": tier_n,
                            "source_channel": "sec_edgar",
                            "source_type": stype,
                            "adapter": "sec_edgar",
                            "status": status,
                            "url": it["url"],
                            "title": it["title"],
                            "text": f"{it['title']}. {it['summary']}",
                            "relevance": rel,
                            "voice": voice,
                        }
                        _append_row(corpus, quotes, row, row["text"], topic_terms)
                        bump(str(tier_n), stats["by_tier"])
                        bump("sec_edgar", stats["by_adapter"])
                except Exception as e:
                    stats["warnings"].append(f"sec_edgar: {e}")

    for it in load_manual_intake(slug, root, tier_set):
        rel = _relevance(f"{it['title']} {it.get('summary', '')}", topic_terms)
        if rel < min_relevance:
            continue
        row = {
            "id": _make_id("manual", it["url"]),
            "captured_at": session,
            "tier": it["tier"],
            "source_channel": it["source_type"],
            "source_type": it["source_type"],
            "adapter": "manual_intake",
            "status": "manual",
            "url": it["url"],
            "title": it["title"],
            "text": it.get("full_text") or it["summary"],
            "relevance": rel,
            "voice": it["voice"],
        }
        _append_row(corpus, quotes, row, row["text"], topic_terms)
        bump(str(it["tier"]), stats["by_tier"])
        bump("manual_intake", stats["by_adapter"])

    sb_cfg = _snowball_config(reg, snowball_depth)
    if not snowball:
        sb_cfg["enabled"] = False
    snowball_added = snowball_expand(
        corpus, quotes, topic_terms, session, sb_cfg, stats, min_relevance,
    )

    if dry_run:
        return {
            "slug": slug,
            "corpus": len(corpus),
            "tiers": list(tier_set),
            "dry_run": True,
            "snowball_added": snowball_added,
            "stats": stats,
        }

    pdf_downloads = 0
    fulltext_enriched = 0
    eth = root / "ethnography" / slug
    eth.mkdir(parents=True, exist_ok=True)
    pdf_dir = eth / "oa_papers"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    if download_fulltext and enrich_corpus:
        fetcher = None
        fetcher_path = SP_ROOT.parent / "retweet-library" / "papers" / "fetch_pdf.py"
        if fetcher_path.exists():
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("fetch_pdf", fetcher_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                fetcher = mod
            except Exception:
                pass
        fulltext_enriched = enrich_corpus(
            corpus, pdf_dir, fetcher=fetcher, max_papers=50,
        )
        for row in corpus:
            if row.get("local_pdf"):
                pdf_downloads += 1

    tier_path = eth / "tier_corpus.jsonl"
    with tier_path.open("w", encoding="utf-8") as f:
        for row in corpus:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    field_path = eth / "field_corpus.jsonl"
    existing_urls = set()
    merged = []
    if field_path.exists():
        for line in field_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                o = json.loads(line)
                merged.append(o)
                if o.get("url"):
                    existing_urls.add(o["url"])
            except Exception:
                continue
    for row in corpus:
        if row.get("url") and row["url"] in existing_urls:
            continue
        merged.append(row)
        if row.get("url"):
            existing_urls.add(row["url"])
    with field_path.open("w", encoding="utf-8") as f:
        for row in merged:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    if download_pdfs and not download_fulltext:
        for row in corpus:
            pdf_url = row.get("pdf_url")
            if not pdf_url or row.get("local_pdf"):
                continue
            safe = re.sub(r"[^\w.-]+", "-", (row.get("title") or "paper")[:50]).strip("-").lower()
            year = row.get("year") or "nd"
            dest = pdf_dir / f"{year}-{safe}.pdf"
            if dest.exists() or _download_oa_pdf(pdf_url, dest):
                pdf_downloads += 1
                row["local_pdf"] = str(dest)
        with tier_path.open("w", encoding="utf-8") as f:
            for row in corpus:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    pq_path = eth / "practitioner_quotes.csv"
    fieldnames = ["quote", "source_id", "source_type", "site", "url", "relevance", "author_voice", "tier"]
    existing = []
    if pq_path.exists():
        with pq_path.open(newline="", encoding="utf-8") as f:
            existing = list(csv.DictReader(f))
    seen = {r.get("quote", "")[:80] for r in existing}
    for q in sorted(quotes, key=lambda x: -x["relevance"]):
        if q["quote"][:80] in seen:
            continue
        seen.add(q["quote"][:80])
        existing.append({k: q.get(k, "") for k in fieldnames})
    with pq_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in sorted(existing, key=lambda x: -int(x.get("relevance") or 0))[:200]:
            w.writerow(r)

    intake = eth / "manual_intake"
    for sub in MANUAL_TIER_MAP:
        (intake / sub).mkdir(parents=True, exist_ok=True)

    (eth / "field_sources.json").write_text(json.dumps({
        "slug": slug,
        "tiers_gathered": sorted(tier_set),
        "corpus_rows": len(corpus),
        "merged_field_corpus": len(merged),
        "oa_pdf_downloads": pdf_downloads,
        "fulltext_enriched": fulltext_enriched,
        "snowball_added": snowball_added,
        "snowball_config": sb_cfg,
        "stats": stats,
        "gathered_at": session,
    }, indent=2) + "\n", encoding="utf-8")

    return {
        "slug": slug,
        "corpus": len(corpus),
        "merged": len(merged),
        "tiers": sorted(tier_set),
        "tier_path": str(tier_path),
        "oa_pdf_downloads": pdf_downloads,
        "fulltext_enriched": fulltext_enriched,
        "snowball_added": snowball_added,
        "stats": stats,
    }


def selftest():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "topics" / "selected").mkdir(parents=True)
        (root / "ethnography" / "test-slug" / "manual_intake" / "keynotes").mkdir(parents=True)
        (root / "topics" / "selected" / "test-slug.md").write_text(
            "Agent memory governance in production LLM workflows.\n"
        )
        (root / "ethnography" / "test-slug" / "manual_intake" / "keynotes" / "conf.md").write_text(
            "In production we externalize agent experience as prompt rules and fine-tuned weights "
            "that drift apart without governance reconciliation.\n"
        )
        fixture_search = {
            "results": [{
                "id": "https://openalex.org/W1",
                "display_name": "Agent Memory Architecture in Production LLM Workflows",
                "publication_year": 2024,
                "type": "proceedings-article",
                "doi": "https://doi.org/10.1234/example.oa",
                "open_access": {"is_oa": True},
                "best_oa_location": {
                    "is_oa": True,
                    "pdf_url": "https://example.org/paper.pdf",
                    "landing_page_url": "https://example.org/paper",
                },
                "primary_location": {"source": {"display_name": "ICIS 2024 Proceedings"}},
                "abstract_inverted_index": {
                    "Agent": [0], "memory": [1], "governance": [2],
                    "tiers": [3], "production": [4], "workflows": [5],
                },
            }]
        }
        fixture_seed_work = {
            "id": "https://openalex.org/W1",
            "referenced_works": ["https://openalex.org/W2"],
        }
        fixture_cited = {
            "results": [{
                "id": "https://openalex.org/W2",
                "display_name": "Governance tiers for agent memory in production workflows",
                "publication_year": 2023,
                "type": "article",
                "doi": "https://doi.org/10.1234/cited.oa",
                "open_access": {"is_oa": True},
                "best_oa_location": {
                    "is_oa": True,
                    "landing_page_url": "https://example.org/cited",
                },
                "abstract_inverted_index": {
                    "Agent": [0], "memory": [1], "governance": [2], "audit": [3],
                },
            }]
        }
        orig_get = globals()["_get"]
        orig_get_json = globals()["_get_json"]

        def mock_get_json(url, timeout=25):
            if "openalex.org/works/doi:" in url:
                return fixture_seed_work
            if "ids.openalex" in url:
                return fixture_cited
            if "openalex.org/works?" in url or url.endswith("/works"):
                return fixture_search
            if "openalex.org" in url:
                return fixture_search
            if "semanticscholar.org" in url:
                return {"data": []}
            return orig_get_json(url, timeout=timeout)

        def mock_get(url, timeout=25):
            if "example.com/cited" in url:
                return "<html><title>Cited agent memory governance paper</title>"
            if "example.com/agent-memory" in url:
                return "<html><title>Agent memory tiers in production</title>"
            return """<rss><channel><item>
<title>Agent memory tiers in production</title>
<link>https://example.com/agent-memory</link>
<description>Teams split rules and weights. See https://example.com/cited for governance.</description>
</item></channel></rss>"""

        globals()["_get"] = mock_get
        globals()["_get_json"] = mock_get_json
        try:
            r = gather("test-slug", tiers=[1, 3], root=root, min_relevance=1)
            assert r["corpus"] >= 4, r
            assert r.get("snowball_added", 0) >= 1, r
            assert (root / "ethnography" / "test-slug" / "tier_corpus.jsonl").exists()
            rows = [
                json.loads(ln) for ln in
                (root / "ethnography" / "test-slug" / "tier_corpus.jsonl").read_text().splitlines()
                if ln.strip()
            ]
            assert any(row.get("work_type") == "proceedings-article" for row in rows), rows
            assert any(row.get("snowball_kind") == "citation" for row in rows), rows
        finally:
            globals()["_get"] = orig_get
            globals()["_get_json"] = orig_get_json
    print("field-sources gather selftest OK")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Tiered field-source gather")
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--tiers", default="1,2,3,4", help="comma-separated tier numbers")
    ap.add_argument("--root", default=str(SP_ROOT))
    ap.add_argument("--min-relevance", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--download-oa-pdfs", action="store_true",
                    help="download OA PDFs to ethnography/<slug>/oa_papers/")
    ap.add_argument("--no-fulltext", action="store_true",
                    help="skip OA/arXiv PDF download and full-text extraction")
    ap.add_argument("--no-snowball", action="store_true",
                    help="disable citation/link snowball expansion")
    ap.add_argument("--snowball-depth", type=int, default=None,
                    help="max snowball hops (default from tier-registry.json)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.slug:
        ap.error("slug required")
    tiers = [int(x.strip()) for x in args.tiers.split(",") if x.strip()]
    r = gather(
        args.slug, tiers=tiers, root=Path(args.root), min_relevance=args.min_relevance,
        dry_run=args.dry_run, download_pdfs=args.download_oa_pdfs,
        download_fulltext=not args.no_fulltext,
        snowball=not args.no_snowball, snowball_depth=args.snowball_depth,
    )
    print(json.dumps(r, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())