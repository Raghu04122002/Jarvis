"""Tests for search grounding: dates, freshness and claim checking."""

from datetime import date

from jarvis.services.search_grounding import (
    GroundedResult,
    coverage_line,
    extract_date,
    fresh_cutoff,
    ground_answer,
    is_time_sensitive,
    source_name,
)

TODAY = date(2026, 10, 27)

AXIOS = GroundedResult(
    title="Israel election: Netanyahu bloc falls short of majority",
    url="https://www.axios.com/2026/10/27/israel-election-exit-polls",
    snippet="Exit polls show Netanyahu's bloc falls short of a 61-seat majority.",
    source="Axios",
    date="2026-10-27",
)
AP = GroundedResult(
    title="Zelensky in Washington",
    url="https://apnews.com/article/zelensky-trump",
    snippet="Zelensky brings backing to the White House as Trump aligns more closely with Putin.",
    source="AP News",
    date="2026-10-26",
)


# --- grounding -------------------------------------------------------------------


def test_added_conclusion_is_removed() -> None:
    answer = "1. Netanyahu's bloc falls short of a majority, but Netanyahu remains in power."
    report = ground_answer(answer, [AXIOS, AP], "today's top news")
    assert report.answer == ""
    assert len(report.removed) == 1


def test_supported_line_is_kept_and_attributed_by_name() -> None:
    answer = "1. Exit polls show Netanyahu's bloc fell short of a 61-seat majority (source)"
    report = ground_answer(answer, [AXIOS, AP], "today's top news")
    assert report.answer == (
        "1. Exit polls show Netanyahu's bloc fell short of a 61-seat majority"
        f" — [Axios]({AXIOS.url})"
    )


def test_wrong_number_is_removed() -> None:
    report = ground_answer("- Netanyahu's bloc falls short of a 62-seat majority", [AXIOS], "")
    assert report.answer == ""


def test_unchecked_framing_claim_is_removed() -> None:
    answer = (
        "Here are today's headlines:\n\n"
        "- Zelensky brings backing to the White House\n"
        "These are the most widely reported stories across major outlets."
    )
    report = ground_answer(answer, [AXIOS, AP], "today's top news")
    assert "widely reported" not in report.answer
    assert report.answer.startswith("Here are today's headlines:")
    assert f"— [AP News]({AP.url})" in report.answer


def test_cited_line_is_checked_against_its_own_source_only() -> None:
    # True according to AP, but the line cites Axios.
    answer = f"- Zelensky brings backing to the White House [Axios]({AXIOS.url})"
    assert ground_answer(answer, [AXIOS, AP]).answer == ""


def test_link_only_item_keeps_its_text() -> None:
    answer = f"- [Zelensky in Washington]({AP.url})"
    assert ground_answer(answer, [AP]).answer == f"- Zelensky in Washington — [AP News]({AP.url})"


def test_removed_items_are_renumbered() -> None:
    answer = (
        "1. Exit polls show Netanyahu's bloc falls short of a majority\n"
        "2. Aliens landed in Paris\n"
        "3. Zelensky brings backing to the White House"
    )
    lines = ground_answer(answer, [AXIOS, AP]).answer.splitlines()
    assert [ln[:3] for ln in lines] == ["1. ", "2. "]
    assert "Zelensky" in lines[1]


def test_code_blocks_are_untouched() -> None:
    answer = "```python\nprint('anything at all')\n```"
    assert ground_answer(answer, [AXIOS]).answer == answer


# --- dates & freshness ---------------------------------------------------------------


def test_extract_date_prefers_backend_field() -> None:
    d = extract_date("https://x.com/2020/01/01/a", "", "", "2026-10-27T09:00:00Z", today=TODAY)
    assert d == date(2026, 10, 27)


def test_extract_date_from_url_and_text() -> None:
    assert extract_date(AXIOS.url, "", "", today=TODAY) == date(2026, 10, 27)
    assert extract_date("https://x.com/a", "", "Updated Oct. 26, 2026", today=TODAY) == date(
        2026, 10, 26
    )


def test_relative_and_missing_dates_are_none() -> None:
    assert extract_date("https://x.com/live", "Live", "Updated 5 mins ago", today=TODAY) is None


def test_future_dates_are_ignored() -> None:
    assert extract_date("https://x.com/a", "", "Event on Dec 3, 2026", today=TODAY) is None


def test_fresh_cutoff_is_48h() -> None:
    assert fresh_cutoff(TODAY) == date(2026, 10, 26)


def test_time_sensitive_detection() -> None:
    assert is_time_sensitive("what's today's top news")
    assert is_time_sensitive("latest headlines")
    assert not is_time_sensitive("explain python decorators")


def test_source_name() -> None:
    assert source_name("https://www.apnews.com/x") == "AP News"
    assert source_name("https://blog.example.org/x", "Post title | Example Blog") == "Example Blog"
    assert source_name("https://foo.example.org/x") == "Example"


def test_coverage_line() -> None:
    line = coverage_line([AXIOS, AP])
    assert line.startswith("*Covers Mon 26 Oct – Tue 27 Oct 2026")
    assert coverage_line([AXIOS]).startswith("*Covers Tue 27 Oct 2026")


# --- verbatim fallback -----------------------------------------------------------------

from jarvis.services.search_grounding import verbatim_headlines  # noqa: E402


def _r(snippet: str, title: str = "Page", source: str = "Src") -> GroundedResult:
    return GroundedResult(title, f"https://{source.lower()}.com/x", snippet, source, "2026-10-27")


def test_headlines_from_markdown_headings() -> None:
    r = _r("Barak Ravid  Updated 4 mins ago  ## Netanyahu bloc loses its majority  Photo text")
    assert verbatim_headlines([r]) == f"- Netanyahu bloc loses its majority — [Src]({r.url})"


def test_headlines_from_colon_list_skip_cut_off_tail() -> None:
    r = _r(
        "Here's the latest for Tuesday Oct. 27: Polls open for Israel's election; "
        "Trump campaigned in Mississippi ahead"
    )
    lines = verbatim_headlines([r]).splitlines()
    assert lines == [f"- Polls open for Israel's election — [Src]({r.url})"]


def test_abbreviations_do_not_split_sentences() -> None:
    r = _r("The U.S. Senate passed the budget bill on Oct. 26 after a long night of votes.")
    assert "on Oct. 26 after a long night of votes." in verbatim_headlines([r])


def test_generic_titles_and_noise_are_skipped() -> None:
    r = _r("Listen · 12:13", title="Morning Briefing: Oct. 27, 2026")
    assert verbatim_headlines([r]) == ""


def test_every_fallback_line_is_in_its_snippet() -> None:
    rs = [
        _r("## Storm hits the northern coast overnight  more", source="A"),
        _r("A ceasefire took effect in the region on Tuesday morning.", source="B"),
    ]
    for line in verbatim_headlines(rs).splitlines():
        text, _, link = line[2:].rpartition(" — ")
        assert any(text in r.snippet and r.url in link for r in rs)
