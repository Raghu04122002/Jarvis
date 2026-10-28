"""Headline collection for news / "today" questions.

A plain web search for "today's top news" mostly returns home pages, section
pages and daily round-ups, whose titles are page titles rather than headlines
and whose text is full of photo captions. This module turns that into a list of
real article headlines:

1. Results that are individual articles are kept as they are.
2. Hub / round-up pages are mined for the headlines they show, and each
   headline is matched to its own article with a second search.
3. Every article is dated - from the search result, its URL, or the page itself
   (meta tags, JSON-LD, ``<time>``). Articles older than 48h are dropped;
   articles whose date can't be found are kept and labelled "date unknown".
4. Photo captions and page titles never become headlines.
5. If that still leaves fewer than ``min_items`` headlines or ``min_outlets``
   outlets, a second search query is tried, and the result says how many were
   found and why.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import weakref
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from html import unescape
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx

from jarvis.services.search_grounding import (
    GroundedResult,
    extract_date,
    fresh_cutoff,
    parse_published,
    source_name,
)

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT = 8.0
_MAX_PAGE_BYTES = 1_500_000
# Waits (seconds) before retrying a rate-limited search. Ollama's free tier
# limits bursts, so searches also run one at a time.
_RATE_LIMIT_BACKOFF: tuple[float, ...] = (3.0, 8.0)
# Reports are cached briefly so asking again doesn't burn search quota.
_CACHE_TTL = 600.0
# Per backend instance, so switching provider in Settings never serves the old
# provider's results; a replaced backend's cache is dropped with it.
_cache: weakref.WeakKeyDictionary[Any, dict[tuple[str, date, int], tuple[float, NewsReport]]] = (
    weakref.WeakKeyDictionary()
)
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


# --- protocols ------------------------------------------------------------------------


class _Result(Protocol):
    title: str
    url: str
    snippet: str
    published: str
    content: str


@dataclass(frozen=True)
class Page:
    """A fetched page: raw HTML when the site allowed it, else extracted text."""

    html: str = ""
    text: str = ""
    title: str = ""


class _Backend(Protocol):
    async def search(self, query: str, max_results: int = 5) -> list[Any]: ...

    async def fetch_page(self, url: str) -> Page | None: ...


async def fetch_html(url: str) -> Page | None:
    """GET a page directly. None on any error, non-200 or non-HTML response."""
    try:
        async with httpx.AsyncClient(
            headers=_BROWSER_HEADERS, follow_redirects=True, timeout=_FETCH_TIMEOUT
        ) as client:
            async with client.stream("GET", url) as resp:
                if resp.status_code != 200:
                    logger.debug("fetch %s -> HTTP %s", url, resp.status_code)
                    return None
                if "html" not in resp.headers.get("content-type", "html"):
                    return None
                chunks: list[bytes] = []
                size = 0
                async for chunk in resp.aiter_bytes():
                    chunks.append(chunk)
                    size += len(chunk)
                    if size >= _MAX_PAGE_BYTES:
                        break
                html = b"".join(chunks).decode(resp.encoding or "utf-8", errors="replace")
                return Page(html=html)
    except (httpx.HTTPError, UnicodeError) as exc:
        logger.debug("fetch %s failed: %s", url, exc)
        return None


# --- URL / title classification ---------------------------------------------------------

_HUB_SEGMENT_RE = re.compile(
    r"^(hub|hubs|tag|tags|topic|topics|section|sections|category|categories|author|authors|"
    r"live-news|latest|latest-news|search|video|videos|programs?|shows?|podcasts?|"
    r"newsletters?|home|index|top|headlines|digest|e)$",
    re.I,
)
_ROUNDUP_RE = re.compile(
    r"\b(?:morning|evening|daily|weekly|news|world)\s+(?:briefing|brief|digest|edition|roundup|"
    r"wrap|summary)\b|\btop (?:stories|news|headlines)\b|\bheadlines for\b|\bthings to know\b|"
    r"\bearly edition\b|\bfull episode\b|\bnews summary\b|\bin focus\b|\blive updates?\b|"
    r"\bliveblog\b|\bbreaking news\b|\bwhat to know\b|\bnews in brief\b|\bnews today\b",
    re.I,
)


def is_article_url(url: str) -> bool:
    """True for a single article's URL; False for home, section, tag or date pages."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("news.google.") or host.endswith("news.google.com"):
        return False
    segs = [s for s in parsed.path.split("/") if s]
    if not segs:
        return False
    if any(_HUB_SEGMENT_RE.match(s) for s in segs[:2]):
        return False
    if "liveblog" in parsed.path.lower():
        return False
    if all(re.fullmatch(r"\d+", s) for s in segs):  # /2026/10/27
        return False
    slug = max(segs, key=lambda s: s.count("-") + s.count("_"))
    words = slug.count("-") + slug.count("_")
    has_id = bool(re.search(r"\d{5,}|[0-9a-f]{16,}", parsed.path))
    return words >= 3 or (words >= 2 and has_id)


def is_roundup(title: str) -> bool:
    """Daily round-ups ("Morning Briefing", "7 things to know") aren't single stories."""
    return bool(_ROUNDUP_RE.search(title))


_SEP_RE = re.compile(r"\s+[|–—·:-]\s+")


def clean_title(title: str) -> str:
    """Drop a trailing site name: "Story text - The Outlet" -> "Story text"."""
    title = " ".join(unescape(title).split())
    parts = _SEP_RE.split(title)
    if len(parts) > 1:
        head, tail = parts[0], parts[1:]
        if all(len(p.split()) <= 5 for p in tail) and len(head.split()) >= 3:
            return head.strip()
    return title.strip()


_DAY = r"(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day"
_MON = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
_CAPTION_RE = re.compile(
    r"\((?:AP|AFP|Reuters|Getty|EPA|Bloomberg)\b[^)]*\)|\b(?:AP Photo|Getty Images|via Getty|"
    r"file photo|photo by|photograph(?:ed)? by|pictured|illustration of|hide caption|"
    r"image credit|credit:)|^(?:photo|image|video|watch|listen|gallery)\b|"
    rf"\b{_DAY},? {_MON}[a-z]*\.? \d{{1,2}}, \d{{4}}",
    re.I,
)
_NOT_HEADLINE_RE = re.compile(
    r"^(?:home|news|world|politics|business|video|videos|latest|opinion|sports?|summary|"
    r"sources|global|local editions?|segments? from this episode|culture & life|"
    r"business & technology)$|\b(?:subscribe|sign up|newsletter|cookies?|log ?in|"
    r"advertisement|listen to|read more|click here)\b",
    re.I,
)


def looks_like_headline(text: str) -> bool:
    """A story headline: not a caption, page title, section name or round-up."""
    text = text.strip()
    if text.endswith(("…", "...")):  # cut off by the search engine
        return False
    words = text.split()
    if not 4 <= len(words) <= 25 or len(text) > 180:
        return False
    if " | " in text or _CAPTION_RE.search(text) or _NOT_HEADLINE_RE.search(text):
        return False
    if is_roundup(text):
        return False
    # Captions are full descriptive sentences ending in a period; headlines aren't.
    if text.endswith(".") and len(words) > 14:
        return False
    return not re.fullmatch(r"[\W\d\s]+|.*\b\d{4}\s*$", text)


# --- page metadata ---------------------------------------------------------------------

_META_RE = re.compile(r"<meta\b[^>]*>", re.I)
_ATTR_RE = re.compile(r'([\w:.-]+)\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)')
_LD_RE = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.I | re.S
)
_TIME_RE = re.compile(r"<time\b[^>]*\bdatetime=[\"']([^\"']+)[\"']", re.I)
_H1_RE = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")

_DATE_META = {
    "article:published_time",
    "og:article:published_time",
    "datepublished",
    "pubdate",
    "publishdate",
    "publish-date",
    "publish_date",
    "date",
    "dc.date",
    "dc.date.issued",
    "dcterms.created",
    "sailthru.date",
    "parsely-pub-date",
    "article.published",
    "og:updated_time",
    "article:modified_time",
}
_TITLE_META = ("og:title", "twitter:title", "headline", "sailthru.title")


def _meta_tags(html: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for tag in _META_RE.findall(html):
        attrs = {k.lower(): v.strip("\"'") for k, v in _ATTR_RE.findall(tag)}
        key = (attrs.get("property") or attrs.get("name") or attrs.get("itemprop") or "").lower()
        if key and "content" in attrs and key not in out:
            out[key] = unescape(attrs["content"])
    return out


def _walk_ld(node: Any) -> list[dict[str, Any]]:
    if isinstance(node, list):
        return [d for n in node for d in _walk_ld(n)]
    if isinstance(node, dict):
        found = [node]
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in node:
                found += _walk_ld(node[key])
        return found
    return []


def _ld_objects(html: str) -> list[dict[str, Any]]:
    objs: list[dict[str, Any]] = []
    for raw in _LD_RE.findall(html):
        try:
            objs += _walk_ld(json.loads(raw.strip()))
        except ValueError:
            continue
    return objs


def page_date(html: str) -> date | None:
    """Publication date from meta tags, JSON-LD or the first ``<time>`` element."""
    meta = _meta_tags(html)
    # Published dates first; modified dates only as a last resort.
    for key in sorted(_DATE_META, key=lambda k: "modified" in k or "updated" in k):
        if key in meta:
            d = parse_published(meta[key])
            if d:
                return d
    for obj in _ld_objects(html):
        for key in ("datePublished", "dateCreated", "uploadDate"):
            value = obj.get(key)
            if isinstance(value, str) and (d := parse_published(value)):
                return d
    m = _TIME_RE.search(html)
    if m and (d := parse_published(m.group(1))):
        return d
    return None


def page_headline(html: str) -> str:
    """The article's own headline: og:title, JSON-LD headline, then <h1>."""
    meta = _meta_tags(html)
    for key in _TITLE_META:
        if meta.get(key):
            return clean_title(meta[key])
    for obj in _ld_objects(html):
        value = obj.get("headline")
        if isinstance(value, str) and value.strip():
            return clean_title(value)
    m = _H1_RE.search(html)
    return clean_title(unescape(_TAG_RE.sub("", m.group(1)))) if m else ""


# --- hub pages ----------------------------------------------------------------------------

_MD_HEADING_RE = re.compile(r"^\s*#{1,4}\s+(.+?)\s*#*\s*$", re.M)
_MD_LINK_RE = re.compile(r"\[([^\]\n]{10,200})\]\((https?://[^)\s]+)\)")


def hub_headlines(content: str) -> list[tuple[str, str]]:
    """Headlines a hub page shows, as ``(headline, article_url or "")``."""
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for text, url in _MD_LINK_RE.findall(content):
        text = clean_title(text)
        if is_article_url(url) and looks_like_headline(text) and text.lower() not in seen:
            seen.add(text.lower())
            found.append((text, url))
    for text in _MD_HEADING_RE.findall(content):
        text = clean_title(_MD_LINK_RE.sub(r"\1", text))
        if looks_like_headline(text) and text.lower() not in seen:
            seen.add(text.lower())
            found.append((text, ""))
    return found


# --- matching -------------------------------------------------------------------------------

_WORD_RE = re.compile(r"[a-z0-9]+")
_SMALL = frozenset("a an the of to in on for and or but at by with as is are was from".split())


def _words(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower()) if w not in _SMALL and len(w) > 2}


def same_story(a: str, b: str, threshold: float = 0.5) -> bool:
    """True if two headlines share most of the shorter one's content words."""
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return False
    return len(wa & wb) / min(len(wa), len(wb)) >= threshold


# --- collection -------------------------------------------------------------------------------


@dataclass
class _Candidate:
    title: str
    url: str
    snippet: str = ""
    published: str = ""


@dataclass
class NewsReport:
    items: list[GroundedResult]
    stats: Counter[str] = field(default_factory=Counter)
    note: str = ""


def _source(url: str) -> str:
    return source_name(url)


def _diverse(items: list[GroundedResult], limit: int) -> list[GroundedResult]:
    """Round-robin across outlets so one site can't fill the whole list."""
    by_source: dict[str, list[GroundedResult]] = {}
    for it in items:
        by_source.setdefault(it.source, []).append(it)
    out: list[GroundedResult] = []
    while len(out) < limit and any(by_source.values()):
        for src in list(by_source):
            if by_source[src] and len(out) < limit:
                out.append(by_source[src].pop(0))
    return out


def _retry_after(resp: httpx.Response) -> float | None:
    """Seconds until the provider accepts requests again, if it says."""
    try:
        return float(resp.headers.get("retry-after", ""))
    except ValueError:
        return None


def _note(
    report: NewsReport, min_items: int, min_outlets: int, reset_in: float | None = None
) -> str:
    n = len(report.items)
    outlets = len({i.source for i in report.items})
    if n >= min_items and outlets >= min_outlets:
        return ""
    s = report.stats
    reasons = []
    if s["old"]:
        reasons.append(f"{s['old']} older than 48 hours")
    if s["hub"]:
        reasons.append(f"{s['hub']} home/section/round-up pages (not single articles)")
    if s["not_headline"]:
        reasons.append(f"{s['not_headline']} photo captions or page titles")
    if s["unmatched"]:
        reasons.append(f"{s['unmatched']} headlines with no matching article page")
    if s["rate_limited"]:
        if reset_in is not None and reset_in > max(_RATE_LIMIT_BACKOFF):
            mins = max(1, round(reset_in / 60))
            reasons.append(
                f"the web search limit for this hour has been reached (resets in about {mins} min)"
            )
        else:
            reasons.append(f"{s['rate_limited']} searches rate-limited by the search provider")
    why = f" Left out: {'; '.join(reasons)}." if reasons else ""
    return (
        f"Only {n} recent headline{'s' if n != 1 else ''} from {outlets} "
        f"outlet{'s' if outlets != 1 else ''} found.{why}"
    )


async def collect_news(
    backend: _Backend,
    query: str,
    today: date,
    *,
    limit: int = 10,
    min_items: int = 5,
    min_outlets: int = 3,
    max_lookups: int = 6,
) -> NewsReport:
    """Collect up to ``limit`` recent article headlines for a news question."""
    cutoff = fresh_cutoff(today)
    stats: Counter[str] = Counter()
    kept: list[GroundedResult] = []
    seen_urls: set[str] = set()
    key = (query.strip().lower(), today, limit)
    cache = _cache.setdefault(backend, {})
    hit = cache.get(key)
    if hit is not None and time.monotonic() - hit[0] < _CACHE_TTL:
        return hit[1]
    search_sem = asyncio.Semaphore(1)
    limited = False  # set once the provider keeps refusing; stop asking
    reset_in: list[float] = []  # provider's retry-after, when it gave one
    fetch_sem = asyncio.Semaphore(6)

    def enough() -> bool:
        return len(kept) >= limit and len({k.source for k in kept}) >= min_outlets

    async def search(q: str, n: int) -> list[Any]:
        nonlocal limited
        async with search_sem:
            for wait in (*_RATE_LIMIT_BACKOFF, None):
                if limited:
                    stats["rate_limited"] += 1
                    return []
                try:
                    return list(await backend.search(q, n))
                except httpx.HTTPStatusError as exc:
                    retry_after = _retry_after(exc.response)
                    # Short bursts are worth waiting out; a quota reset isn't.
                    quota = retry_after is not None and retry_after > max(_RATE_LIMIT_BACKOFF)
                    if exc.response.status_code == 429 and wait is not None and not quota:
                        await asyncio.sleep(wait)
                        continue
                    if exc.response.status_code == 429:
                        limited = True
                        stats["rate_limited"] += 1
                        if retry_after is not None:
                            reset_in.append(retry_after)
                    logger.warning("News search %r failed: %s", q, exc)
                    return []
                except Exception as exc:  # noqa: BLE001 - one failed search mustn't sink the rest
                    logger.warning("News search %r failed: %s", q, exc)
                    return []
            return []

    async def finish(c: _Candidate) -> GroundedResult | None:
        """Date an article and settle its headline; None if it should be dropped."""
        title = clean_title(c.title)
        d = extract_date(c.url, "", "", c.published, today=today)
        if d is None or not looks_like_headline(title):
            async with fetch_sem:
                page = await backend.fetch_page(c.url)
            if page is not None:
                if page.html:
                    d = d or page_date(page.html)
                    own = page_headline(page.html)
                    if own and looks_like_headline(own):
                        title = own
                elif page.text:
                    d = d or extract_date("", "", page.text[:1500], today=today)
                    if page.title and looks_like_headline(clean_title(page.title)):
                        title = clean_title(page.title)
        # Publishers stamp UTC, which is already "tomorrow" in the evening for
        # anyone west of Greenwich - allow one day, like extract_date does.
        if d is not None and d > today + timedelta(days=1):
            d = None
        if d is not None and d < cutoff:
            stats["old"] += 1
            return None
        if not looks_like_headline(title):
            stats["not_headline"] += 1
            return None
        return GroundedResult(
            title=title,
            url=c.url,
            snippet=" ".join(c.snippet.split())[:600],
            source=_source(c.url),
            date=d.isoformat() if d else None,
            headline=True,
        )

    async def resolve(headline: str) -> _Candidate | None:
        """Find the article page for a headline seen on a hub."""
        for r in await search(headline, 3):
            if is_article_url(r.url) and same_story(headline, r.title):
                return _Candidate(headline, r.url, r.snippet, getattr(r, "published", ""))
        stats["unmatched"] += 1
        return None

    def add(results: list[GroundedResult | None]) -> None:
        for item in results:
            if item is None or item.url in seen_urls:
                continue
            if any(same_story(item.title, k.title, 0.7) for k in kept):
                continue
            seen_urls.add(item.url)
            kept.append(item)

    queries = [query, f"news {today:%B} {today.day}, {today.year}"]
    for i, q in enumerate(queries):
        if i > 0 and len(kept) >= min_items and len({k.source for k in kept}) >= min_outlets:
            break
        articles: list[_Candidate] = []
        hub_heads: list[list[tuple[str, str]]] = []
        for r in await search(q, 10):
            if r.url in seen_urls:
                continue
            title = clean_title(r.title)
            if is_article_url(r.url) and not is_roundup(title):
                articles.append(_Candidate(r.title, r.url, r.snippet, getattr(r, "published", "")))
            else:
                stats["hub"] += 1
                heads = hub_headlines(getattr(r, "content", "") or r.snippet)
                if heads:
                    hub_heads.append(heads)
        add(list(await asyncio.gather(*(finish(c) for c in articles))))
        if enough():
            break

        # Interleave hubs so the lookups cover several outlets' front pages.
        lookups: list[tuple[str, str]] = []
        while any(hub_heads) and len(lookups) < max_lookups:
            for heads in hub_heads:
                if heads and len(lookups) < max_lookups:
                    lookups.append(heads.pop(0))
        lookups = [
            (h, u) for h, u in lookups if not any(same_story(h, k.title, 0.7) for k in kept)
        ]
        direct = [_Candidate(h, u) for h, u in lookups if u]
        found = await asyncio.gather(*(resolve(h) for h, u in lookups if not u))
        cands = direct + [c for c in found if c is not None and c.url not in seen_urls]
        add(list(await asyncio.gather(*(finish(c) for c in cands))))
        if enough():
            break

    report = NewsReport(items=_diverse(kept, limit), stats=stats)
    report.note = _note(report, min_items, min_outlets, max(reset_in, default=None))
    logger.info(
        "News search %r: %d headlines from %d outlets (%s)",
        query,
        len(report.items),
        len({i.source for i in report.items}),
        dict(stats),
    )
    if not stats["rate_limited"]:  # a throttled, partial report is worth retrying
        cache[key] = (time.monotonic(), report)
    return report
