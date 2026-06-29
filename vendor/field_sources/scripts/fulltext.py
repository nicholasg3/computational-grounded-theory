#!/usr/bin/env python3
"""fulltext.py — download OA/arXiv PDFs and extract readable text (stdlib-first).

Used by gather.py and strategic-publishing research_pack / citations.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.parse
import urllib.request
import zlib
from io import BytesIO
from pathlib import Path

MAILTO = "1nicholasgarcia@gmail.com"
UA = f"FieldSources-FullText/1.0 (mailto:{MAILTO})"

ARXIV_ABS_RE = re.compile(
    r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5}(?:v\d+)?)", re.I,
)
ARXIV_ID_RE = re.compile(r"^([0-9]{4}\.[0-9]{4,5})(?:v\d+)?$")
MAX_FULLTEXT_CHARS = 80_000
MAX_PDF_BYTES = 25 * 1024 * 1024


def arxiv_id_from_url(url: str) -> str:
    m = ARXIV_ABS_RE.search(url or "")
    return m.group(1) if m else ""


def arxiv_pdf_url(arxiv_id: str) -> str:
    base = arxiv_id.split("v")[0] if arxiv_id else ""
    return f"https://arxiv.org/pdf/{base}.pdf" if base else ""


def arxiv_html_url(arxiv_id: str) -> str:
    base = arxiv_id.split("v")[0] if arxiv_id else ""
    return f"https://arxiv.org/html/{base}" if base else ""


def _get_bytes(url: str, timeout: int = 45) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        raise ValueError(f"PDF too large: {url}")
    return data


def _get_text(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def _strip_html(html: str) -> str:
    t = re.sub(r"<script[^>]*>.*?</script>", " ", html or "", flags=re.I | re.S)
    t = re.sub(r"<style[^>]*>.*?</style>", " ", t, flags=re.I | re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _decode_pdf_literal(raw: bytes) -> str:
    out = []
    i = 0
    while i < len(raw):
        c = raw[i]
        if c == ord("\\") and i + 1 < len(raw):
            nxt = raw[i + 1]
            if nxt in b"nrtbf()\\":
                out.append({ord("n"): "\n", ord("r"): "\r", ord("t"): "\t"}.get(nxt, chr(nxt)))
                i += 2
                continue
            if ord("0") <= nxt <= ord("7"):
                oct_digits = raw[i + 1 : i + 4]
                try:
                    out.append(chr(int(oct_digits, 8)))
                    i += 1 + len(oct_digits)
                    continue
                except ValueError:
                    pass
        out.append(chr(c))
        i += 1
    return "".join(out)


def _extract_pdf_strings(data: bytes) -> str:
    parts = []
    for m in re.finditer(rb"\((?:\\.|[^\\)])*\)", data):
        try:
            s = _decode_pdf_literal(m.group(0)[1:-1])
            if len(s) >= 3 and any(ch.isalpha() for ch in s):
                parts.append(s)
        except Exception:
            continue
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        chunk = m.group(1)
        for decompress in (lambda b: b, lambda b: zlib.decompress(b)):
            try:
                decoded = decompress(chunk)
                parts.extend(
                    _decode_pdf_literal(x.group(0)[1:-1])
                    for x in re.finditer(rb"\((?:\\.|[^\\)])*\)", decoded)
                )
            except Exception:
                continue
    text = re.sub(r"\s+", " ", " ".join(parts)).strip()
    return text


def text_quality(text: str) -> float:
    """Fraction of chars that look like readable prose (letters + common punctuation)."""
    if not text:
        return 0.0
    good = sum(1 for ch in text if ch.isalpha() or ch in " .,;:-")
    return good / max(len(text), 1)


def extract_pdf_text(data: bytes) -> str:
    if not data or data[:4] != b"%PDF":
        return ""
    via_cli = shutil.which("pdftotext")
    if via_cli:
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(data)
                tmp_path = Path(tmp.name)
            out_path = tmp_path.with_suffix(".txt")
            subprocess.run(
                [via_cli, "-q", str(tmp_path), str(out_path)],
                check=True,
                capture_output=True,
                timeout=60,
            )
            text = out_path.read_text(encoding="utf-8", errors="replace")
            tmp_path.unlink(missing_ok=True)
            out_path.unlink(missing_ok=True)
            return re.sub(r"\s+", " ", text).strip()
        except Exception:
            pass
    return _extract_pdf_strings(data)


def fetch_arxiv_html_text(arxiv_id: str) -> str:
    url = arxiv_html_url(arxiv_id)
    if not url:
        return ""
    try:
        html = _get_text(url, timeout=35)
    except Exception:
        return ""
    text = _strip_html(html)
    return text[:MAX_FULLTEXT_CHARS] if len(text) > 200 else ""


def fetch_arxiv_latex_text(arxiv_id: str) -> str:
    """Fallback: pull .tex from arXiv e-print tarball."""
    base = arxiv_id.split("v")[0]
    if not base:
        return ""
    url = f"https://arxiv.org/e-print/{base}"
    try:
        data = _get_bytes(url, timeout=60)
    except Exception:
        return ""
    try:
        with tarfile.open(fileobj=BytesIO(data), mode="r:*") as tar:
            tex_chunks = []
            for member in tar.getmembers():
                if not member.isfile() or not member.name.endswith(".tex"):
                    continue
                if len(tex_chunks) >= 3:
                    break
                f = tar.extractfile(member)
                if not f:
                    continue
                raw = f.read().decode("utf-8", errors="replace")
                raw = re.sub(r"%.*", "", raw)
                raw = re.sub(r"\\[a-zA-Z@]+(\[[^\]]*\])?(\{[^}]*\})?", " ", raw)
                raw = re.sub(r"[{}$\\\\]", " ", raw)
                raw = re.sub(r"\s+", " ", raw).strip()
                if len(raw) > 100:
                    tex_chunks.append(raw)
            return "\n\n".join(tex_chunks)[:MAX_FULLTEXT_CHARS]
    except Exception:
        return ""


def resolve_pdf_url(row: dict, fetcher=None) -> str:
    pdf = (row.get("pdf_url") or "").strip()
    if pdf:
        return pdf
    url = (row.get("url") or "").strip()
    ax = arxiv_id_from_url(url)
    if ax:
        return arxiv_pdf_url(ax)
    doi = (row.get("doi") or "").replace("https://doi.org/", "").strip()
    if fetcher and doi:
        try:
            works = fetcher.by_doi(doi)
            if works:
                for cand in fetcher.resolve_oa(works[0], doi):
                    if cand:
                        return cand
        except Exception:
            pass
    return ""


def _cache_key(row: dict) -> str:
    key = (
        row.get("doi")
        or row.get("openalex_id")
        or row.get("url")
        or row.get("title")
        or "paper"
    )
    return hashlib.sha1(str(key).encode("utf-8")).hexdigest()[:12]


def _cache_paths(pdf_dir: Path, row: dict) -> tuple[Path, Path]:
    stem = _cache_key(row)
    return pdf_dir / f"{stem}.pdf", pdf_dir / f"{stem}.txt"


def download_pdf(pdf_url: str, dest: Path) -> bool:
    try:
        data = _get_bytes(pdf_url)
        if data[:4] != b"%PDF":
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return True
    except Exception:
        return False


def get_fulltext(
    row: dict,
    pdf_dir: Path,
    *,
    fetcher=None,
    force: bool = False,
) -> dict:
    """Return {full_text, local_pdf, pdf_url, text_source} with disk cache."""
    pdf_path, txt_path = _cache_paths(pdf_dir, row)
    if not force and txt_path.exists():
        text = txt_path.read_text(encoding="utf-8", errors="replace").strip()
        if len(text) > 100:
            return {
                "full_text": text[:MAX_FULLTEXT_CHARS],
                "local_pdf": str(pdf_path) if pdf_path.exists() else "",
                "pdf_url": row.get("pdf_url") or "",
                "text_source": "cache",
            }

    pdf_url = resolve_pdf_url(row, fetcher=fetcher)
    full_text = ""
    text_source = ""
    local_pdf = ""

    ax = arxiv_id_from_url(row.get("url") or "") or (
        arxiv_id_from_url(pdf_url) if pdf_url else ""
    )
    if not ax and row.get("arxiv_id"):
        ax = str(row["arxiv_id"]).split("v")[0]

    candidates: list[tuple[str, str]] = []

    if ax:
        latex_text = fetch_arxiv_latex_text(ax)
        if len(latex_text) > 200 and text_quality(latex_text) >= 0.55:
            candidates.append(("arxiv-latex", latex_text))
        html_text = fetch_arxiv_html_text(ax)
        if len(html_text) > 200 and text_quality(html_text) >= 0.55:
            candidates.append(("arxiv-html", html_text))

    if pdf_url:
        if pdf_path.exists() or download_pdf(pdf_url, pdf_path):
            local_pdf = str(pdf_path)
            pdf_text = extract_pdf_text(pdf_path.read_bytes())
            if len(pdf_text) > 200 and text_quality(pdf_text) >= 0.45:
                candidates.append(("pdf", pdf_text))

    if candidates:
        text_source, full_text = max(candidates, key=lambda x: (text_quality(x[1]), len(x[1])))

    full_text = full_text[:MAX_FULLTEXT_CHARS]
    if len(full_text) > 100:
        txt_path.parent.mkdir(parents=True, exist_ok=True)
        txt_path.write_text(full_text + "\n", encoding="utf-8")

    return {
        "full_text": full_text,
        "local_pdf": local_pdf,
        "pdf_url": pdf_url,
        "text_source": text_source,
    }


def enrich_row(row: dict, pdf_dir: Path, *, fetcher=None, force: bool = False) -> dict:
    """Attach full_text / local_pdf to a scholarly corpus or citation row."""
    adapter = row.get("adapter") or ""
    access = (row.get("access") or "").upper()
    if adapter not in (
        "arxiv", "openalex_oa", "semantic_scholar_oa", "snowball_citation",
    ) and access not in ("OA", "OPEN") and not row.get("pdf_url"):
        ax = arxiv_id_from_url(row.get("url") or "")
        if not ax:
            return row

    ft = get_fulltext(row, pdf_dir, fetcher=fetcher, force=force)
    if ft.get("pdf_url"):
        row["pdf_url"] = ft["pdf_url"]
    if ft.get("local_pdf"):
        row["local_pdf"] = ft["local_pdf"]
    if ft.get("text_source"):
        row["text_source"] = ft["text_source"]
    full = (ft.get("full_text") or "").strip()
    if full:
        row["full_text"] = full
        abstract = (row.get("summary") or row.get("abstract") or "").strip()
        row["text"] = f"{row.get('title', '')}. {full}"
        if abstract and abstract not in full[: len(abstract) + 20]:
            row["text"] = f"{row.get('title', '')}. {abstract} {full[:12000]}"
        row["excerpt"] = full
    return row


def enrich_corpus(
    rows: list[dict],
    pdf_dir: Path,
    *,
    fetcher=None,
    max_papers: int = 40,
    force: bool = False,
) -> int:
    """Download + extract for scholarly rows; returns count enriched."""
    n = 0
    for row in rows:
        if n >= max_papers:
            break
        adapter = row.get("adapter") or ""
        if adapter not in SCHOLARLY_ADAPTERS and not row.get("pdf_url"):
            if not arxiv_id_from_url(row.get("url") or ""):
                continue
        before = len((row.get("full_text") or ""))
        enrich_row(row, pdf_dir, fetcher=fetcher, force=force)
        if len(row.get("full_text") or "") > before or (
            before == 0 and len(row.get("full_text") or "") > 200
        ):
            n += 1
    return n


SCHOLARLY_ADAPTERS = frozenset({
    "arxiv", "openalex_oa", "semantic_scholar_oa", "snowball_citation",
})