"""Filing PDF reader (BE-4): download a filing PDF, extract text page by page, cache it.

- Only exchange archive hosts are fetched (the URL comes from filing records, but a server that
  downloads any URL it is handed is an SSRF [server-side request forgery] risk).
- The page text is cached under `.cache/pages/<fingerprint>.json` (fingerprint = SHA-1 of the
  URL), so each PDF is downloaded and parsed once. The PDF itself is not kept.
- Pages are parsed one at a time and closed, to stay inside Render's ~512 MB.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

import config

_DOUBLED = re.compile(r"([A-Za-z])\1([A-Za-z])\2([A-Za-z])\3")  # "RReevv": letters drawn twice
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Referer": "https://www.nseindia.com/",
}


def fingerprint(url: str) -> str:
    """Short stable id for a URL, used as the cache file name."""
    return hashlib.sha1(url.strip().encode("utf-8")).hexdigest()[:16]


def _pages_path(url: str) -> Path:
    return Path(config.CACHE_DIR) / "pages" / f"{fingerprint(url)}.json"


def check_url(url: str) -> None:
    """Raise ValueError unless the URL is an https link on an allowed exchange archive host."""
    u = urlparse(url or "")
    if u.scheme != "https" or (u.hostname or "").lower() not in config.PDF_ALLOWED_HOSTS:
        raise ValueError(f"Not an exchange filing link: {url[:80]!r}")
    if not u.path.lower().endswith(".pdf"):
        raise ValueError("The filing link is not a PDF.")


def download_pdf(url: str) -> bytes:
    """Download a filing PDF (timeout, one retry, size cap). Raises RuntimeError on failure."""
    check_url(url)
    errors: list[str] = []
    for attempt in range(1 + config.RETRIES):
        try:
            r = requests.get(url, headers=_HEADERS, timeout=config.PDF_TIMEOUT_S, stream=True)
            r.raise_for_status()
            buf = io.BytesIO()
            for chunk in r.iter_content(64 * 1024):
                buf.write(chunk)
                if buf.tell() > config.PDF_MAX_BYTES:
                    raise RuntimeError(f"PDF larger than {config.PDF_MAX_BYTES // 2**20} MB")
            data = buf.getvalue()
            if not data.startswith(b"%PDF"):
                raise RuntimeError("the reply is not a PDF")
            return data
        except Exception as exc:  # network, HTTP block, oversize
            errors.append(f"attempt {attempt + 1}: {exc}")
            time.sleep(1)
    raise RuntimeError(f"Could not download the filing PDF. {'; '.join(errors)}")


def extract_pages(pdf_bytes: bytes) -> list[str]:
    """Text of every page, in order (page 1 = index 0). An image-only page gives ''."""
    import pdfplumber  # imported here: only the card path needs it, and it is slow to import

    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            try:
                text = page.extract_text() or ""
                if len(_DOUBLED.findall(text)) > 15:
                    # Some PDFs draw every letter twice, slightly offset ("RReevveennuuee").
                    # Merge only on such pages and with a tight tolerance: a wide one also merges
                    # real repeated digits ("2,672.77" -> "2,672.7"), a silent error.
                    text = page.dedupe_chars(tolerance=2, extra_attrs=()).extract_text() or ""
                pages.append(text)
            except Exception:  # one broken page should not lose the document
                pages.append("")
            finally:
                page.close()
    return pages


def load_pages(url: str) -> list[str] | None:
    """Cached page text for a URL, or None."""
    path = _pages_path(url)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))["pages"]
    except (ValueError, KeyError):
        return None


def get_pages(url: str) -> list[str]:
    """Page texts of a filing PDF: from the cache, else downloaded and parsed (then cached)."""
    cached = load_pages(url)
    if cached is not None:
        return cached
    pages = extract_pages(download_pdf(url))
    path = _pages_path(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"url": url, "pages": pages}), encoding="utf-8")
    return pages
