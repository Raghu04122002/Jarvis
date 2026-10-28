"""Tests for the news collector: hub expansion, dating, headline vetting."""

from __future__ import annotations

from datetime import date

import pytest

from jarvis.services.chat_tools import SearchResult, WebSearchBackend
from jarvis.services.news_search import (
    Page,
    clean_title,
    collect_news,
    hub_headlines,
    is_article_url,
    looks_like_headline,
    page_date,
    page_headline,
)

TODAY = date(2026, 10, 27)


class FakeBackend(WebSearchBackend):
    """Answers queries from a dict (substring match) and pages from another."""

    def __init__(
        self,
        by_query: dict[str, list[SearchResult]],
        pages: dict[str, Page] | None = None,
    ) -> None:
        self.by_query = by_query
        self.pages = pages or {}
        self.queries: list[str] = []

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        self.queries.append(query)
        for key, results in self.by_query.items():
            if key.lower() in query.lower():
                return results[:max_results]
        return []

    async def fetch_page(self, url: str) -> Page | None:
        return self.pages.get(url)


def _r(title: str, url: str, published: str = "", content: str = "") -> SearchResult:
    return SearchResult(title, url, f"{title}.", published, content)


# --- classification ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "article"),
    [
        ("https://apnews.com/", False),
        ("https://apnews.com/hub/world-news", False),
        ("https://www.npr.org/sections/news/", False),
        ("https://www.axios.com/2026/10/27", False),
        ("https://news.google.com/topics/abc", False),
        ("https://apnews.com/article/israel-election-exit-polls-netanyahu-1f2e3d4c5b6a7980", True),
        ("https://www.axios.com/2026/10/27/israel-election-exit-polls", True),
    ],
)
def test_is_article_url(url: str, article: bool) -> None:
    assert is_article_url(url) is article


@pytest.mark.parametrize(
    ("text", "ok"),
    [
        ("Israeli exit polls: Netanyahu bloc loses, but short of clear majority", True),
        (
            "Voters wait in line at a polling station in Tel Aviv. (AP Photo/Oded Balilty)",
            False,
        ),
        ("AP Top Stories October 27", False),
        ("Morning Briefing: Oct. 27, 2026", False),
        ("Breaking News, Latest Headlines and Videos | AP News", False),
        ("World News", False),
        ("Israel says Iran launched missiles at it in first such …", False),
    ],
)
def test_looks_like_headline(text: str, ok: bool) -> None:
    assert looks_like_headline(text) is ok


def test_clean_title_drops_site_name() -> None:
    assert clean_title("Storm hits the northern coast overnight - The Outlet") == (
        "Storm hits the northern coast overnight"
    )


def test_page_date_and_headline_from_meta_and_json_ld() -> None:
    html = (
        '<meta property="article:published_time" content="2026-10-27T09:00:00Z">'
        '<script type="application/ld+json">{"@type": "NewsArticle", '
        '"headline": "Council approves new city transit plan"}</script>'
    )
    assert page_date(html) == date(2026, 10, 27)
    assert page_headline(html) == "Council approves new city transit plan"

    ld_only = (
        '<script type="application/ld+json">{"@graph": [{"datePublished": "2026-10-26"}]}</script>'
    )
    assert page_date(ld_only) == date(2026, 10, 26)


def test_hub_headlines_skip_captions_and_nav() -> None:
    content = (
        "[World News](https://apnews.com/hub/world-news)\n"
        "## Israeli exit polls: Netanyahu bloc loses its majority\n"
        "[Storm hits the northern coast overnight](https://ex.com/news/storm-hits-northern-coast)\n"
        "People gather in a square. (AP Photo/Jane Doe)\n"
    )
    heads = hub_headlines(content)
    assert ("Israeli exit polls: Netanyahu bloc loses its majority", "") in heads
    assert (
        "Storm hits the northern coast overnight",
        "https://ex.com/news/storm-hits-northern-coast",
    ) in heads
    assert all("World News" != h and "AP Photo" not in h for h, _ in heads)


# --- collector -------------------------------------------------------------------------------

_ARTICLES = [
    _r(
        "Parliament passes new budget bill after long debate",
        "https://a.com/politics/parliament-passes-new-budget-bill",
        "2026-10-27",
    ),
    _r(
        "Storm hits the northern coast overnight - B News",
        "https://b.com/world/storm-hits-the-northern-coast",
        "2026-10-26",
    ),
    _r(
        "Council approves new city transit plan",
        "https://c.com/local/council-approves-city-transit-plan",
    ),
    _r(
        "Old story about last week's flooding damage",
        "https://d.com/news/old-story-flooding-damage",
        "2026-10-20",
    ),
    _r(
        "Central bank holds interest rates steady again",
        "https://e.com/2026/10/27/central-bank-holds-rates-steady",
    ),
]


@pytest.mark.asyncio
async def test_collector_dates_filters_and_keeps_undated() -> None:
    pages = {
        # c.com has no date in the result or URL; the page has none either.
        "https://c.com/local/council-approves-city-transit-plan": Page(html="<html></html>"),
    }
    report = await collect_news(FakeBackend({"news": _ARTICLES}, pages), "today's top news", TODAY)
    by_url = {r.url: r for r in report.items}
    assert "https://d.com/news/old-story-flooding-damage" not in by_url  # older than 48h
    assert by_url["https://a.com/politics/parliament-passes-new-budget-bill"].date == "2026-10-27"
    assert by_url["https://c.com/local/council-approves-city-transit-plan"].date is None
    assert by_url["https://e.com/2026/10/27/central-bank-holds-rates-steady"].date == "2026-10-27"
    assert by_url["https://b.com/world/storm-hits-the-northern-coast"].title == (
        "Storm hits the northern coast overnight"
    )
    assert all(r.headline for r in report.items)
    assert "Only 4" in report.note and "older than 48 hours" in report.note


@pytest.mark.asyncio
async def test_utc_tomorrow_is_still_today() -> None:
    """In the US evening, UTC timestamps are already the next day."""
    item = _r(
        "Late vote count shifts the result overnight",
        "https://a.com/politics/late-vote-count-shifts-result",
        "2026-10-28T01:30:00+00:00",
    )
    report = await collect_news(FakeBackend({"news": [item]}), "news", TODAY)
    assert report.items[0].date == "2026-10-28"


@pytest.mark.asyncio
async def test_page_supplies_date_and_real_headline() -> None:
    url = "https://f.com/world/opposition-claims-narrow-win-national-vote"
    item = _r("Photos: scenes from the vote", url)  # a gallery title, not a headline
    html = (
        '<meta property="article:published_time" content="2026-10-27T10:00:00Z">'
        '<meta property="og:title" content="Opposition claims narrow win in national vote">'
    )
    report = await collect_news(
        FakeBackend({"news": [item]}, {url: Page(html=html)}), "news", TODAY
    )
    assert [(r.title, r.date) for r in report.items] == [
        ("Opposition claims narrow win in national vote", "2026-10-27")
    ]


@pytest.mark.asyncio
async def test_hubs_are_expanded_into_articles() -> None:
    hub = _r(
        "AP News: Breaking News, Latest Headlines",
        "https://apnews.com/",
        content=(
            "## Israeli exit polls: Netanyahu bloc loses its majority\n"
            "## Trump praises Canadian separatists amid trade talks\n"
            "[Ceasefire takes effect in eastern border region](https://apnews.com/article/ceasefire-takes-effect-border-region-0a1b2c3d4e5f)\n"
        ),
    )
    backend = FakeBackend(
        {
            "Israeli exit polls": [
                _r(
                    "Israeli exit polls: Netanyahu bloc loses its majority",
                    "https://www.axios.com/2026/10/27/israel-election-exit-polls",
                    "2026-10-27",
                )
            ],
            "Trump praises": [
                _r(
                    "Trump praises Canadian separatists amid trade talks - Reuters",
                    "https://www.reuters.com/world/trump-praises-canadian-separatists-trade-talks-2026-10-27/",
                )
            ],
            "news": [hub],
        },
        {
            "https://apnews.com/article/ceasefire-takes-effect-border-region-0a1b2c3d4e5f": Page(
                html='<meta name="pubdate" content="2026-10-27">'
            )
        },
    )
    report = await collect_news(backend, "today's top news", TODAY)
    urls = [r.url for r in report.items]
    assert "https://apnews.com/" not in urls
    assert "https://www.axios.com/2026/10/27/israel-election-exit-polls" in urls
    assert (
        "https://www.reuters.com/world/trump-praises-canadian-separatists-trade-talks-2026-10-27/"
        in urls
    )
    assert "https://apnews.com/article/ceasefire-takes-effect-border-region-0a1b2c3d4e5f" in urls
    assert len({r.source for r in report.items}) == 3
    assert report.stats["hub"] >= 1


@pytest.mark.asyncio
async def test_five_to_ten_headlines_across_outlets() -> None:
    topics = [
        "Parliament passes new budget bill",
        "Storm hits northern coast overnight",
        "Central bank holds interest rates",
        "Council approves city transit plan",
        "Ceasefire takes effect in border region",
        "Tech giant unveils new chip design",
        "Drought forces water limits across farms",
        "Striking nurses reach pay agreement",
        "Scientists detect signal from distant galaxy",
        "Champions win final in extra time",
        "Wildfire smoke closes schools downtown",
        "Museum returns looted ancient statues",
    ]
    outlets = ["a", "b", "c", "d", "e", "f"]
    results = [
        _r(t, f"https://{outlets[i % 6]}.com/news/{t.lower().replace(' ', '-')}", "2026-10-27")
        for i, t in enumerate(topics)
    ]
    report = await collect_news(
        FakeBackend({"news": results}), "today's top news", TODAY, limit=10
    )
    assert 5 <= len(report.items) <= 10
    assert len({r.source for r in report.items}) >= 3
    assert report.note == ""


def test_acronym_hosts_read_as_initials() -> None:
    from jarvis.services.search_grounding import source_name

    assert source_name("https://www.wcvb.com/article/x") == "WCVB"
    assert source_name("https://www.democracynow.org/x") == "Democracy Now!"


@pytest.mark.asyncio
async def test_rate_limited_search_is_retried_then_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    from jarvis.services import news_search

    monkeypatch.setattr(news_search, "_RATE_LIMIT_BACKOFF", (0.0,))

    class Limited(FakeBackend):
        async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
            self.queries.append(query)
            req = httpx.Request("POST", "https://ollama.com/api/web_search")
            raise httpx.HTTPStatusError(
                "429", request=req, response=httpx.Response(429, request=req)
            )

    backend = Limited({})
    report = await collect_news(backend, "news", TODAY)
    assert report.items == []
    # First query tried twice, then the collector stops calling the provider.
    assert len(backend.queries) == 2
    assert "rate-limited" in report.note


@pytest.mark.asyncio
async def test_reports_are_cached_briefly() -> None:
    item = _r(
        "Council approves city transit plan", "https://c.com/news/transit-plan", "2026-10-27"
    )
    backend = FakeBackend({"news": [item]})
    first = await collect_news(backend, "news", TODAY)
    calls = len(backend.queries)
    second = await collect_news(backend, "News ", TODAY)
    assert second is first
    assert len(backend.queries) == calls


@pytest.mark.asyncio
async def test_cache_is_per_backend() -> None:
    a = FakeBackend(
        {
            "news": [
                _r(
                    "Council approves transit plan",
                    "https://c.com/news/council-approves-transit-plan",
                    "2026-10-27",
                )
            ]
        }
    )
    b = FakeBackend(
        {
            "news": [
                _r(
                    "Storm hits the northern coast",
                    "https://b.com/world/storm-hits-northern-coast",
                    "2026-10-27",
                )
            ]
        }
    )
    first = await collect_news(a, "news", TODAY)
    second = await collect_news(b, "news", TODAY)
    assert second is not first
    assert [r.url for r in second.items] == ["https://b.com/world/storm-hits-northern-coast"]


@pytest.mark.asyncio
async def test_hourly_quota_stops_at_once_and_says_when(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    from jarvis.services import news_search

    slept: list[float] = []

    async def fake_sleep(t: float) -> None:
        slept.append(t)

    monkeypatch.setattr(news_search.asyncio, "sleep", fake_sleep)

    class OverQuota(FakeBackend):
        async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
            self.queries.append(query)
            req = httpx.Request("POST", "https://ollama.com/api/web_search")
            resp = httpx.Response(429, request=req, headers={"retry-after": "1084"})
            raise httpx.HTTPStatusError("429", request=req, response=resp)

    backend = OverQuota({})
    report = await collect_news(backend, "news", TODAY)
    assert backend.queries == ["news"]  # no retries, no second query
    assert slept == []
    assert "limit for this hour" in report.note and "18 min" in report.note
