"""Keep web-search answers tied to what the search actually returned.

Three jobs, all deterministic so they can be tested without a model:

* **Dating** - find an absolute publication date for a result (backend field,
  URL, title or text). Relative phrases like "5 mins ago" are ignored on
  purpose: hub pages keep saying "5 mins ago" in stale snapshots.
* **Freshness** - for news / "today" questions keep only results dated today or
  yesterday (always < 48h old). Undated results are dropped.
* **Grounding** - after the model writes its answer, check every line against
  the snippet it cites and remove lines that add words or numbers the source
  doesn't contain. Each kept list line ends with "— [Source](url)".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

# --------------------------------------------------------------------------- dates

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}  # fmt: skip
_MONTH = (
    r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?"
    r"|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_ORD = r"(?:st|nd|rd|th)?"
_ISO_RE = re.compile(r"(?<!\d)(20\d\d)[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)")
# "Oct. 27, 2026", "October 27", "Tuesday Oct. 27"
_MDY = r"\b" + _MONTH + r"\.?\s+(\d{1,2})" + _ORD + r"(?!\d)(?:,?\s+(20\d\d))?"
# "27 October 2026", "27th Oct"
_DMY = r"\b(\d{1,2})" + _ORD + r"\s+" + _MONTH + r"\.?(?:,?\s+(20\d\d))?\b"
# In prose, months must be capitalised ("may", "march" are also verbs).
_TEXT_MDY = re.compile(_MDY)
_TEXT_DMY = re.compile(_DMY)
_URL_MDY = re.compile(_MDY, re.IGNORECASE)
_URL_DMY = re.compile(_DMY, re.IGNORECASE)


def _mk(year: int | None, month: int, day: int, today: date) -> date | None:
    try:
        if year is not None:
            return date(year, month, day)
        # No year: assume the most recent occurrence.
        d = date(today.year, month, day)
        return d if d <= today + timedelta(days=1) else date(today.year - 1, month, day)
    except ValueError:
        return None


def _scan(text: str, today: date, *, url: bool) -> list[date]:
    found: list[date] = []
    for m in _ISO_RE.finditer(text):
        d = _mk(int(m.group(1)), int(m.group(2)), int(m.group(3)), today)
        if d:
            found.append(d)
    mdy, dmy = (_URL_MDY, _URL_DMY) if url else (_TEXT_MDY, _TEXT_DMY)
    for m in mdy.finditer(text):
        month = _MONTHS[m.group(1)[:3].lower()]
        d = _mk(int(m.group(3)) if m.group(3) else None, month, int(m.group(2)), today)
        if d:
            found.append(d)
    for m in dmy.finditer(text):
        month = _MONTHS[m.group(2)[:3].lower()]
        d = _mk(int(m.group(3)) if m.group(3) else None, month, int(m.group(1)), today)
        if d:
            found.append(d)
    return found


def parse_published(value: str) -> date | None:
    """Parse a backend-supplied publication timestamp (ISO 8601 or RFC 2822)."""
    value = value.strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(value).date()
    except (TypeError, ValueError, IndexError):
        return None


def extract_date(
    url: str, title: str, text: str, published: str = "", *, today: date
) -> date | None:
    """Best absolute publication date for a result, or None if there isn't one.

    A backend ``published`` field wins. Otherwise take the newest date found in
    the URL, title or text that isn't in the future (hub pages list many
    stories; the newest one is what the page currently shows).
    """
    if published:
        d = parse_published(published)
        if d is not None:
            return d
    path = urlparse(url).path
    url_text = re.sub(r"[-_/]+", " ", path)
    candidates = (
        _scan(path, today, url=True)
        + _scan(url_text, today, url=True)
        + _scan(title, today, url=False)
        + _scan(text, today, url=False)
    )
    candidates = [d for d in candidates if d <= today + timedelta(days=1)]
    return max(candidates) if candidates else None


_TIME_SENSITIVE_RE = re.compile(
    r"\b(news|headlines?|today'?s?|tonight|yesterday|this (?:morning|afternoon|evening|week)"
    r"|breaking|current events?|right now)\b",
    re.IGNORECASE,
)


def is_time_sensitive(text: str) -> bool:
    """True for news / "today" style questions, which only fresh results can answer."""
    return bool(_TIME_SENSITIVE_RE.search(text))


def fresh_cutoff(today: date) -> date:
    """Oldest publication date still accepted for time-sensitive questions.

    Dates are day-granular, so "within 48h" is enforced as today or yesterday:
    anything dated yesterday is at most 48h old.
    """
    return today - timedelta(days=1)


# ----------------------------------------------------------------------- sources

_KNOWN_SOURCES = {
    "apnews.com": "AP News", "reuters.com": "Reuters", "axios.com": "Axios",
    "bbc.co.uk": "BBC", "bbc.com": "BBC", "cnn.com": "CNN", "npr.org": "NPR",
    "nytimes.com": "The New York Times", "washingtonpost.com": "The Washington Post",
    "theguardian.com": "The Guardian", "wsj.com": "The Wall Street Journal",
    "bloomberg.com": "Bloomberg", "ft.com": "Financial Times", "upi.com": "UPI",
    "aljazeera.com": "Al Jazeera", "nbcnews.com": "NBC News", "cbsnews.com": "CBS News",
    "abcnews.go.com": "ABC News", "foxnews.com": "Fox News", "politico.com": "Politico",
    "thehill.com": "The Hill", "news.google.com": "Google News", "aa.com.tr": "Anadolu",
    "economist.com": "The Economist", "cnbc.com": "CNBC", "time.com": "TIME",
    "democracynow.org": "Democracy Now!", "techcrunch.com": "TechCrunch",
    "theverge.com": "The Verge", "wikipedia.org": "Wikipedia",
}  # fmt: skip


def source_name(url: str, title: str = "") -> str:
    """Human name for a result's publisher, e.g. "AP News" for apnews.com."""
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    for domain, name in _KNOWN_SOURCES.items():
        if host == domain or host.endswith("." + domain):
            return name
    # "Story headline | Publisher" / "Story headline - Publisher"
    for sep in (" | ", " - ", " — ", " – "):
        if sep in title:
            tail = title.rsplit(sep, 1)[1].strip()
            if 1 <= len(tail) <= 40:
                return tail
    parts = host.split(".")
    base = parts[-2] if len(parts) >= 2 else host
    if not base:
        return "Source"
    # Call-sign / acronym hosts (wcvb, kxan, bbc) read as initials.
    return base.upper() if len(base) <= 4 else base.capitalize()


# --------------------------------------------------------------------- grounding


@dataclass(frozen=True)
class GroundedResult:
    title: str
    url: str
    snippet: str
    source: str
    date: str | None  # ISO date, or None if undated
    headline: bool = False  # title is a vetted article headline (news search)


_STOPWORDS = frozenset(
    """a an the and or but nor so yet of in on at to for from by with without into onto
    over under after before about as is are was were be been being am do does did done
    has have had having it its it's this that these those there here their them they he
    she his her him we our us you your i me my not no yes than then also just very more
    most less least much many some any all each every both either neither other such only
    own same too can could will would shall should may might must new says said say
    according amid while during against between through per via who whom whose which
    what when where why how if up down out off again further once""".split()
)

# Words that frame an answer rather than claim anything about the world.
_FRAMING = frozenset(
    """here top today today's headlines headline news stories story latest following
    source sources result results search searched found link links date title summary
    item items key update updates report reports current currently based returned
    available""".split()
)

_WORD_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
_NUM_RE = re.compile(r"(?<![\w.])\d[\d,.]*%?")


# Irregular verb forms common in news copy ("fell short" vs "falls short").
_IRREGULAR = {
    "fell": "fall", "fallen": "fall", "said": "say", "won": "win", "lost": "lose",
    "rose": "rise", "risen": "rise", "met": "meet", "led": "lead", "held": "hold",
    "took": "take", "taken": "take", "gave": "give", "given": "give", "made": "make",
    "struck": "strike", "sent": "send", "told": "tell", "left": "leave", "ran": "run",
    "came": "come", "went": "go", "gone": "go", "saw": "see", "seen": "see",
    "began": "begin", "begun": "begin", "became": "become", "spoke": "speak",
    "spoken": "speak", "sold": "sell", "bought": "buy", "brought": "bring",
    "fought": "fight", "thought": "think", "kept": "keep", "found": "find",
    "chose": "choose", "chosen": "choose", "drew": "draw", "grew": "grow",
    "knew": "know", "known": "know", "shot": "shoot", "stood": "stand", "sought": "seek",
    "wrote": "write", "written": "write", "flew": "fly", "fled": "flee", "hid": "hide",
}  # fmt: skip


def _stem(w: str) -> str:
    w = w.removesuffix("'s").removesuffix("’s")
    if w in _IRREGULAR:
        w = _IRREGULAR[w]
    for suf in ("ing", "ed", "es", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _tokens(text: str) -> set[str]:
    text = text.lower().replace("’", "'")
    return {_stem(w) for w in _WORD_RE.findall(text) if w not in _STOPWORDS and len(w) > 2}


def _numbers(text: str) -> set[str]:
    return {n.rstrip(".,").replace(",", "") for n in _NUM_RE.findall(text)}


_LINK_RE = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)\)")
_BARE_URL_RE = re.compile(r"https?://[^\s)\]]+")
_LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")
_REMOVED_MARK = "*(unverified source removed)*"


def _norm_url(u: str) -> str:
    return u.rstrip("/.,")


@dataclass
class GroundingReport:
    answer: str
    removed: list[str]


def _support(claim: str, evidence: str, ignore: set[str]) -> tuple[float, set[str]]:
    """Fraction of the claim's content words found in the evidence, plus the misses."""
    words = _tokens(claim) - {_stem(w) for w in _FRAMING} - ignore
    if not words:
        return 1.0, set()
    have = _tokens(evidence)
    missing = {w for w in words if w not in have}
    return 1 - len(missing) / len(words), missing


def ground_answer(
    answer: str,
    results: list[GroundedResult],
    question: str = "",
    *,
    threshold: float = 0.9,
    label_dates: bool = False,
) -> GroundingReport:
    """Drop lines the search results don't support and attribute the rest.

    * A line citing a result is checked against *that* result only.
    * An uncited list/table line is matched to its best-supporting result and
      gets that result's attribution; if none supports it, it's removed.
    * Uncited prose is checked against all results together.
    * Any number in a line must appear in the evidence verbatim.
    Words from the user's own question are allowed (restating it is not a claim).
    """
    by_url = {_norm_url(r.url): r for r in results}
    union = "\n".join(f"{r.title}\n{r.snippet}" for r in results)
    ignore = _tokens(question)
    out: list[str] = []
    removed: list[str] = []
    in_fence = False

    for line in answer.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence or not stripped or _TABLE_SEP_RE.match(stripped):
            out.append(line)
            continue

        cited: list[GroundedResult] = []
        for m in _LINK_RE.finditer(line):
            r = by_url.get(_norm_url(m.group(2)))
            if r is not None and r not in cited:
                cited.append(r)
        for u in _BARE_URL_RE.findall(_LINK_RE.sub("", line)):
            r = by_url.get(_norm_url(u))
            if r is not None and r not in cited:
                cited.append(r)

        is_item = bool(_LIST_RE.match(line)) or stripped.startswith("|")
        # The claim is the line minus links, URLs and attribution dashes.
        # List markers ("2.", "-") are formatting, not claims.
        claim = _LINK_RE.sub(" ", _LIST_RE.sub("", line, count=1))
        claim = _BARE_URL_RE.sub(" ", claim).replace(_REMOVED_MARK, " ")
        # Source names in the line are attribution, not claims.
        names = {w for r in results for w in _tokens(r.source)}

        def ok(evidence: str) -> bool:
            score, _ = _support(claim, evidence, ignore | names)
            nums = _numbers(claim) - _numbers(question)
            return score >= threshold and nums <= _numbers(evidence)

        if _REMOVED_MARK in line and not cited:
            removed.append(stripped)
            continue

        if cited:
            evidence = "\n".join(f"{r.title}\n{r.snippet}" for r in cited)
            if not ok(evidence):
                removed.append(stripped)
                continue
            out.append(_attribute(line, cited, label_dates) if is_item else line)
            continue

        if is_item:
            best = None
            best_score = -1.0
            for r in results:
                score, _ = _support(claim, f"{r.title}\n{r.snippet}", ignore | names)
                if score > best_score:
                    best, best_score = r, score
            if best is not None and ok(f"{best.title}\n{best.snippet}"):
                # Table header rows have no content words; leave them alone.
                if _tokens(claim) - {_stem(w) for w in _FRAMING} - ignore - names:
                    out.append(_attribute(line, [best], label_dates))
                else:
                    out.append(line)
                continue
            removed.append(stripped)
            continue

        # Prose (lead-in, headings, closing remarks).
        if ok(union):
            out.append(line)
        else:
            removed.append(stripped)

    text = re.sub(r"\n{3,}", "\n\n", "\n".join(_renumber(out))).strip()
    return GroundingReport(answer=text, removed=removed)


_NUMBERED_RE = re.compile(r"^(\s*)\d+([.)]\s+)")


def _renumber(lines: list[str]) -> list[str]:
    """Renumber ordered lists so removed items don't leave gaps (1, 3, 4 -> 1, 2, 3)."""
    out: list[str] = []
    n = 0
    for line in lines:
        m = _NUMBERED_RE.match(line)
        if m and not m.group(1):
            n += 1
            line = f"{n}{m.group(2)}{line[m.end() :]}"
        elif line.strip() and not line.startswith((" ", "\t")):
            n = 0  # any other top-level text ends the list
        out.append(line)
    return out


def _cite(r: GroundedResult, label_dates: bool = False) -> str:
    """ "[Source](url)", plus " · date unknown" for undated news sources."""
    unknown = " · date unknown" if label_dates and not r.date else ""
    return f"[{r.source}]({r.url}){unknown}"


def _attribute(line: str, cited: list[GroundedResult], label_dates: bool = False) -> str:
    """Rewrite a list/table line so it ends with "— [Source](url)" for each source."""
    attribution = ", ".join(_cite(r, label_dates) for r in cited)
    if line.strip().startswith("|"):
        # Tables: replace link text in place with the source name.
        def fix(m: re.Match[str]) -> str:
            for r in cited:
                if _norm_url(m.group(2)) == _norm_url(r.url):
                    return f"[{r.source}]({r.url})"
            return m.group(0)

        fixed = _LINK_RE.sub(fix, line)
        if not any(r.url in fixed for r in cited):
            cells = fixed.rstrip().rstrip("|").rstrip()
            fixed = f"{cells} — {attribution} |"
        return fixed
    line = line.replace(_REMOVED_MARK, "")
    outside = _tokens(_LIST_RE.sub("", _LINK_RE.sub(" ", line), count=1))

    def unlink(m: re.Match[str]) -> str:
        # "Story [AP](url)": a short label next to other text is just attribution.
        # "- [Real headline](url)": the link text *is* the item, so keep it.
        text = m.group(1).strip()
        if outside and len(text.split()) <= 3:
            return ""
        return text

    body = _LINK_RE.sub(unlink, line)
    body = _BARE_URL_RE.sub("", body)
    # Drop empty leftovers like "()", "( )", trailing dashes or "Source:".
    body = re.sub(r"\(\s*[,;]?\s*\)", "", body)
    body = re.sub(r"\s*\((?:source|sources|link|via [^)]*)\)", "", body, flags=re.I)
    body = re.sub(r"[\s—–\-:;,]*(?:source|sources|via)?[\s:]*$", "", body, flags=re.I)
    return f"{body.rstrip()} — {attribution}"


def coverage_line(results: list[GroundedResult]) -> str:
    """One line saying which days the answer's sources cover."""
    days = sorted({date.fromisoformat(r.date) for r in results if r.date})
    unknown = sum(1 for r in results if not r.date)
    tail = f" · {unknown} with date unknown" if unknown else ""
    if not days:
        return f"*All {unknown} sources have no findable date.*" if unknown else ""
    fmt = "%a %-d %b %Y"
    span = (
        days[0].strftime(fmt)
        if days[0] == days[-1]
        else f"{days[0].strftime('%a %-d %b')} – {days[-1].strftime(fmt)}"
    )
    return f"*Covers {span} · sources published in the last 48 hours{tail}.*"


# --- verbatim fallback ---------------------------------------------------------------

_HEADING_RE = re.compile(r"#{2,4}\s+(.+?)(?=\s{2,}|\s#{2,4}\s|$)")
# "  - Israel Exit polls suggest no clear victor in Israeli election Netanyahu has..."
_BULLET_RE = re.compile(r"(?:^|\s{2,})-\s+([^-#].+?)(?=\s{2,}|$)")
# "Here's the latest for Tuesday Oct. 27: Polls open for X; Trump campaigned in Y"
_COLON_LIST_RE = re.compile(r"(?:latest|headlines|top stories)[^:]{0,40}:\s*(.+)", re.I)
# "Here's a rundown of all the news you need..., including X, Y and Z"
_INCLUDING_RE = re.compile(r"(?:rundown|recap|roundup|briefing)[^.]{0,80}?including\s+(.+)", re.I)
_ABBREV_RE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|Mr|Mrs|Ms|Dr|St|Gen|Sen|Rep|"
    r"Gov|Jr|Sr|vs|No|U\.S|U\.K|U\.N|E\.U)\.$"
)
_NOISE_RE = re.compile(
    r"\b(listen|hide caption|updated \d+|\d+ (?:min|mins|hours?) ago|click|subscribe|"
    r"sign up|newsletter|cookies?)\b",
    re.I,
)


def _sentences(text: str) -> list[str]:
    """Split on sentence ends, not on abbreviations like "Oct." or "U.S."."""
    out: list[str] = []
    buf = ""
    for part in re.split(r"(?<=[.!?])\s+", text):
        buf = f"{buf} {part}".strip()
        if _ABBREV_RE.search(buf) or re.search(r"\b[A-Z]\.$", buf):
            continue
        out.append(buf)
        buf = ""
    if buf:
        out.append(buf)
    return out


def _complete(text: str, snippet: str) -> bool:
    """False if ``text`` runs into the end of a (probably truncated) snippet.

    Backends cut page text at a fixed length, so a candidate that ends exactly
    where the snippet ends - without closing punctuation - is likely cut mid-word.
    """
    if text.endswith("…"):
        return False
    body = " ".join(snippet.split()).rstrip(" …")
    if body.endswith(" ".join(text.split()).rstrip(" …")):
        return text.rstrip()[-1:] in ".!?\"'”’)"
    return True


# Page titles that are just a date or a section name, not a story.
_GENERIC_TITLE_RE = re.compile(
    r"^(?:(?:morning|evening|daily|news|top|latest|world)\s*)+(?:briefing|news|stories|"
    r"headlines|edition|digest|update)?\b[\s:,-]*[\w.,\s]*\d{4}$|\btop stories\b",
    re.I,
)


def _clean(h: str) -> str:
    return " ".join(h.split()).strip(" -–—#;:,")


def _headlines_in(result: GroundedResult) -> list[str]:
    """Headlines that appear word-for-word in one result, best guess first."""
    snip = result.snippet

    def ok(h: str, lo: int = 4, hi: int = 30) -> bool:
        return lo <= len(h.split()) <= hi and not _NOISE_RE.search(h) and _complete(h, snip)

    found = [_clean(h) for h in _HEADING_RE.findall(snip)]
    found = [h for h in found if ok(h)]
    if found:
        return found
    flat = " ".join(snip.split())
    m = _COLON_LIST_RE.search(flat) or _INCLUDING_RE.search(flat)
    if m:
        parts = [_clean(p) for p in re.split(r";|, and |, including ", m.group(1))]
        parts = [p for p in parts if ok(p, 3)]
        if parts:
            return [p[0].upper() + p[1:] for p in parts]
    bullets = []
    for b in _BULLET_RE.findall(snip):
        first = _clean(_sentences(b)[0])
        if ok(first, 4, 25):
            bullets.append(first)
    if bullets:
        return bullets
    for sent in _sentences(" ".join(snip.split())):
        sent = _clean(sent)
        if ok(sent, 6, 40):
            return [sent]
    title = _clean(re.split(r"\s+[|:–—-]\s+", result.title)[0])
    return [title] if ok(title) and not _GENERIC_TITLE_RE.search(title) else []


def verbatim_headlines(results: list[GroundedResult], limit: int = 8) -> str:
    """A list of headlines copied exactly from the results, each with its source.

    Used when the model's own summary mostly failed grounding: nothing here is
    paraphrased, so every line traces straight back to a snippet.
    """
    lines: list[str] = []
    per_source = max(1, limit // max(1, len(results)))
    for r in results:
        heads = [r.title] if r.headline else _headlines_in(r)[: per_source + 1]
        for h in heads:
            lines.append(f"- {h} — {_cite(r, label_dates=True)}")
    return "\n".join(lines[:limit])
