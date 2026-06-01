"""Retrieve real scholarly papers from multiple academic APIs.

Sources are tried in order (OpenAlex, Semantic Scholar, CrossRef by default).
The first source that returns results is used. Failures are logged with request
URL, HTTP status, and error detail.
"""
import logging
import threading
import time

import requests
from flask import current_app

_log = logging.getLogger(__name__)

_rate_lock = threading.Lock()
_last_request_time = 0.0

DEFAULT_HEADERS = {
    "Accept": "application/json",
}

SOURCE_OPENALEX = "OpenAlex"
SOURCE_SEMANTIC_SCHOLAR = "Semantic Scholar"
SOURCE_CROSSREF = "CrossRef"

DEFAULT_SOURCE_ORDER = (
    SOURCE_OPENALEX,
    SOURCE_SEMANTIC_SCHOLAR,
    SOURCE_CROSSREF,
)

S2_FIELDS = "title,authors,year,abstract,url,paperId,externalIds"


def _logger():
    try:
        return current_app.logger
    except RuntimeError:
        return _log


def _cfg(name, default):
    try:
        return current_app.config.get(name, default)
    except RuntimeError:
        return default


def _contact_email():
    return _cfg("RESEARCH_CONTACT_EMAIL", "admin@aula.test")


def _user_agent():
    return f"TrustLed-Aula/1.0 (mailto:{_contact_email()})"


def _wait_for_rate_limit(min_interval):
    global _last_request_time
    with _rate_lock:
        now = time.monotonic()
        elapsed = now - _last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _last_request_time = time.monotonic()


def _doi_url(doi):
    if not doi:
        return ""
    doi = str(doi).strip()
    if doi.startswith("http"):
        return doi
    if doi.lower().startswith("doi:"):
        doi = doi[4:].strip()
    return f"https://doi.org/{doi}"


def _normalize_paper(title, authors, year, abstract, doi, verification_url, source):
    verify = _doi_url(doi) or (verification_url or "").strip()
    return {
        "title": title or "Untitled",
        "authors": authors or "Unknown authors",
        "year": year or "n.d.",
        "abstract": (abstract or "").strip(),
        "doi": (doi or "").replace("https://doi.org/", "").strip(),
        "verification_url": verify,
        "url": verify,
        "source": source,
    }


def _reconstruct_openalex_abstract(inverted_index):
    if not inverted_index:
        return ""
    word_positions = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    word_positions.sort()
    return " ".join(word for _, word in word_positions)


def _http_get(url, params, headers, source_name, timeout=15):
    """GET JSON with logging. Returns (data, error)."""
    log = _logger()
    prepared = requests.Request("GET", url, params=params, headers=headers).prepare()
    request_url = prepared.url
    log.info("%s request: %s", source_name, request_url)
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        log.error("%s request exception url=%s error=%s", source_name, request_url, exc)
        return None, str(exc)

    log.info("%s response status=%s url=%s", source_name, resp.status_code, request_url)
    if resp.status_code == 429:
        log.warning(
            "%s rate limited (429) url=%s body=%s",
            source_name,
            request_url,
            resp.text[:240],
        )
        return None, f"429 Too Many Requests: {resp.text[:240]}"
    if not resp.ok:
        log.error(
            "%s HTTP error status=%s url=%s body=%s",
            source_name,
            resp.status_code,
            request_url,
            resp.text[:300],
        )
        return None, f"{resp.status_code}: {resp.text[:240]}"
    try:
        return resp.json(), None
    except ValueError as exc:
        log.error(
            "%s invalid JSON url=%s error=%s body=%s",
            source_name,
            request_url,
            exc,
            resp.text[:300],
        )
        return None, f"Invalid JSON: {exc}"


def _search_openalex(query, limit):
    base = _cfg("OPENALEX_BASE_URL", "https://api.openalex.org").rstrip("/")
    params = {
        "search": query,
        "per_page": min(limit, 10),
        "mailto": _contact_email(),
    }
    headers = {**DEFAULT_HEADERS, "User-Agent": _user_agent()}
    data, error = _http_get(f"{base}/works", params, headers, SOURCE_OPENALEX)
    if error:
        return [], error

    papers = []
    for item in data.get("results") or []:
        names = []
        for authorship in item.get("authorships") or []:
            author = authorship.get("author") or {}
            name = author.get("display_name")
            if name:
                names.append(name)
        abstract = _reconstruct_openalex_abstract(item.get("abstract_inverted_index"))
        doi = item.get("doi") or ""
        landing = (item.get("primary_location") or {}).get("landing_page_url") or ""
        verify = _doi_url(doi) or landing or item.get("id") or ""
        papers.append(_normalize_paper(
            item.get("display_name"),
            ", ".join(names),
            item.get("publication_year"),
            abstract,
            doi,
            verify,
            SOURCE_OPENALEX,
        ))
    return papers, None


def _parse_semantic_scholar(data):
    papers = []
    for item in data.get("data") or []:
        authors = []
        for author in item.get("authors") or []:
            if isinstance(author, dict):
                name = author.get("name") or author.get("authorId")
                if name:
                    authors.append(str(name))
        ext = item.get("externalIds") or {}
        doi = ext.get("DOI") or ""
        url = (item.get("url") or "").strip()
        if not url and item.get("paperId"):
            url = f"https://www.semanticscholar.org/paper/{item['paperId']}"
        verify = _doi_url(doi) or url
        papers.append(_normalize_paper(
            item.get("title"),
            ", ".join(authors),
            item.get("year"),
            item.get("abstract"),
            doi,
            verify,
            SOURCE_SEMANTIC_SCHOLAR,
        ))
    return papers


def _fetch_semantic_scholar(base, params, headers, max_retries, base_delay, min_interval):
    url = f"{base.rstrip('/')}/paper/search"
    log = _logger()

    for attempt in range(max_retries + 1):
        _wait_for_rate_limit(min_interval)
        prepared = requests.Request("GET", url, params=params, headers=headers).prepare()
        request_url = prepared.url
        log.info(
            "Semantic Scholar search attempt %d/%d: %s",
            attempt + 1,
            max_retries + 1,
            request_url,
        )
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=15)
        except requests.RequestException as exc:
            log.error("Semantic Scholar exception url=%s error=%s", request_url, exc)
            if attempt >= max_retries:
                return None, str(exc)
            time.sleep(base_delay * (2 ** attempt))
            continue

        log.info("Semantic Scholar response status=%s url=%s", resp.status_code, request_url)
        if resp.status_code == 429:
            retry_after = 0.0
            if resp.headers.get("Retry-After"):
                try:
                    retry_after = float(resp.headers["Retry-After"])
                except ValueError:
                    retry_after = 0.0
            wait = max(retry_after, base_delay * (2 ** attempt))
            log.warning(
                "Semantic Scholar rate limited (429) url=%s wait=%.1fs body=%s",
                request_url,
                wait,
                resp.text[:240],
            )
            if attempt >= max_retries:
                return None, f"429 Too Many Requests: {resp.text[:240]}"
            time.sleep(wait)
            continue

        if not resp.ok:
            log.error(
                "Semantic Scholar HTTP error status=%s url=%s body=%s",
                resp.status_code,
                request_url,
                resp.text[:300],
            )
            return None, f"{resp.status_code}: {resp.text[:240]}"
        try:
            return resp.json(), None
        except ValueError as exc:
            return None, f"Invalid JSON: {exc}"

    return None, "Semantic Scholar search failed after retries"


def _search_semantic_scholar(query, limit):
    base = _cfg("SEMANTIC_SCHOLAR_BASE_URL", "https://api.semanticscholar.org/graph/v1")
    api_key = _cfg("SEMANTIC_SCHOLAR_API_KEY", "")
    max_retries = int(_cfg("SEMANTIC_SCHOLAR_MAX_RETRIES", 2))
    base_delay = float(_cfg("SEMANTIC_SCHOLAR_RETRY_BASE_SECONDS", 2.0))
    min_interval = float(_cfg("SEMANTIC_SCHOLAR_MIN_INTERVAL", 1.05))

    headers = {**DEFAULT_HEADERS, "User-Agent": _user_agent()}
    if api_key:
        headers["x-api-key"] = api_key

    params = {"query": query, "limit": min(limit, 10), "fields": S2_FIELDS}
    data, error = _fetch_semantic_scholar(
        base, params, headers, max_retries, base_delay, min_interval
    )
    if error:
        return [], error
    papers = _parse_semantic_scholar(data)
    if not papers:
        return [], "Semantic Scholar returned no papers"
    return papers, None


def _crossref_year(item):
    for key in ("published-print", "published-online", "created"):
        block = item.get(key) or {}
        parts = block.get("date-parts") or [[]]
        if parts and parts[0]:
            return str(parts[0][0])
    return "n.d."


def _search_crossref(query, limit):
    base = _cfg("CROSSREF_BASE_URL", "https://api.crossref.org").rstrip("/")
    params = {
        "query": query,
        "rows": min(limit, 10),
        "select": "DOI,title,author,published-print,published-online,abstract,URL",
    }
    headers = {**DEFAULT_HEADERS, "User-Agent": _user_agent()}
    data, error = _http_get(f"{base}/works", params, headers, SOURCE_CROSSREF)
    if error:
        return [], error

    papers = []
    for item in (data.get("message") or {}).get("items") or []:
        title_parts = item.get("title") or []
        title = title_parts[0] if title_parts else "Untitled"
        names = []
        for author in item.get("author") or []:
            parts = [author.get("given"), author.get("family")]
            name = " ".join(p for p in parts if p)
            if name:
                names.append(name)
        doi = item.get("DOI") or ""
        verify = _doi_url(doi) or (item.get("URL") or "")
        papers.append(_normalize_paper(
            title,
            ", ".join(names),
            _crossref_year(item),
            item.get("abstract") or "",
            doi,
            verify,
            SOURCE_CROSSREF,
        ))
    if not papers:
        return [], "CrossRef returned no papers"
    return papers, None


_SOURCE_SEARCHERS = {
    SOURCE_OPENALEX: _search_openalex,
    SOURCE_SEMANTIC_SCHOLAR: _search_semantic_scholar,
    SOURCE_CROSSREF: _search_crossref,
}


def _configured_source_order():
    raw = _cfg("RESEARCH_SOURCE_ORDER", ",".join(DEFAULT_SOURCE_ORDER))
    order = []
    for name in raw.split(","):
        key = name.strip()
        if not key:
            continue
        for canonical in DEFAULT_SOURCE_ORDER:
            if key.lower() == canonical.lower():
                if canonical not in order:
                    order.append(canonical)
                break
    return order or list(DEFAULT_SOURCE_ORDER)


def search_papers(query, limit=5):
    """Search for papers across configured scholarly sources.

    Returns ``(papers, api_used, source)`` where *papers* is a list of dicts
    with ``title``, ``authors``, ``year``, ``abstract``, ``verification_url``,
    ``doi``, and ``source``. On total failure *papers* is empty, *api_used* is
    False, and *source* is None.
    """
    query = (query or "").strip()
    if not query:
        return [], False, None

    limit = min(limit, 10)
    log = _logger()
    errors = []

    for source_name in _configured_source_order():
        searcher = _SOURCE_SEARCHERS.get(source_name)
        if not searcher:
            continue
        log.info("Trying scholarly source %s for query=%r", source_name, query)
        papers, error = searcher(query, limit)
        if papers:
            log.info(
                "%s returned %d paper(s) for query=%r",
                source_name,
                len(papers),
                query,
            )
            return papers, True, source_name
        if error:
            errors.append(f"{source_name}: {error}")
            log.warning("%s failed for query=%r: %s", source_name, query, error)

    log.error(
        "All scholarly sources failed for query=%r: %s",
        query,
        "; ".join(errors) if errors else "no results",
    )
    return [], False, None


def all_sources_unavailable_message():
    """Plain message when every scholarly source failed."""
    names = ", ".join(_configured_source_order())
    return (
        f"All scholarly search sources ({names}) were unavailable or returned no "
        "results. References below are illustrative only and must be verified "
        "independently before use."
    )


def format_papers_for_prompt(papers):
    """Format retrieved papers as context for the LLM prompt."""
    if not papers:
        return ""

    blocks = []
    for i, p in enumerate(papers, 1):
        abstract = p["abstract"] or "(No abstract available.)"
        if len(abstract) > 800:
            abstract = abstract[:800] + "…"
        verify = p.get("verification_url") or p.get("url") or "N/A"
        blocks.append(
            f"[REAL RETRIEVED SOURCE {i} — verify at: {verify}]\n"
            f"Source database: {p.get('source', 'Unknown')}\n"
            f"Title: {p['title']}\n"
            f"Authors: {p['authors']}\n"
            f"Year: {p['year']}\n"
            f"DOI: {p.get('doi') or 'N/A'}\n"
            f"Verification link (click to confirm original): {verify}\n"
            f"Abstract: {abstract}"
        )
    return "\n\n".join(blocks)


def format_papers_bibliography(papers, style="APA"):
    """Human-readable list of real retrieved sources with verification links."""
    if not papers:
        return ""

    source = papers[0].get("source", "scholarly database")
    lines = [
        f"REAL RETRIEVED SOURCES (from {source} — click links to verify originals, "
        f"formatted in {style} style):",
    ]
    for i, p in enumerate(papers, 1):
        verify = p.get("verification_url") or p.get("url") or ""
        verify_part = f" Verify: {verify}" if verify else ""
        lines.append(
            f"{i}. {p['authors']} ({p['year']}). {p['title']}.{verify_part}"
        )
    return "\n".join(lines)
