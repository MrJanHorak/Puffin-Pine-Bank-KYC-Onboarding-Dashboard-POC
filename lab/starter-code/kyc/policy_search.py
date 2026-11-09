"""Read-only policy retrieval from the Day 4 Azure AI Search index.

The policy data is untrusted context. Never log a key, query, or policy text.
The caller decides whether a missing result should hold a recommendation.
"""
import json
import os
import re
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from dotenv import dotenv_values

from kyc import STARTER_ROOT
from kyc.settings import setting


class PolicyUnavailable(Exception):
    """Policy lookup could not be completed; details are intentionally withheld."""


def search_config():
    """Use process/local config, then an explicitly named Day 4 env file.

    Only the three query settings are read from that file. Its admin key is
    never put into the process environment or sent to the search service.
    """
    env_path = os.environ.get("KYC_SEARCH_ENV_FILE") or setting("KYC_SEARCH_ENV_FILE")
    extra = dotenv_values(Path(env_path)) if env_path else {}
    return {name: os.environ.get(name) or setting(name) or extra.get(name) or ""
            for name in ("AZURE_SEARCH_ENDPOINT", "AZURE_SEARCH_INDEX",
                         "AZURE_SEARCH_QUERY_KEY")}


def search_policy(jurisdiction: str, as_of: str, question: str | None = None) -> list[dict]:
    """Return the relevant current policy sections, or raise PolicyUnavailable."""
    conf = search_config()
    endpoint = conf["AZURE_SEARCH_ENDPOINT"].rstrip("/")
    index = conf["AZURE_SEARCH_INDEX"]
    key = conf["AZURE_SEARCH_QUERY_KEY"]
    try:
        parsed = urlparse(endpoint)
        explicit_port = parsed.port
    except ValueError:
        raise PolicyUnavailable("Policy search configuration is missing or invalid.") from None
    # Avoid forwarding the query key to an unexpected host or URL path.
    if (parsed.scheme != "https" or not parsed.hostname or
            not parsed.hostname.endswith(".search.windows.net") or
            parsed.username or parsed.password or explicit_port or parsed.path or
            parsed.query or parsed.fragment or
            not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,127}", index) or not key):
        raise PolicyUnavailable("Policy search configuration is missing or invalid.")
    if not re.fullmatch(r"X[A-J]", jurisdiction or ""):
        raise PolicyUnavailable("Applicant jurisdiction is missing or invalid.")
    try:
        review_date = date.fromisoformat(as_of).isoformat()
    except (ValueError, TypeError):
        raise PolicyUnavailable("Policy review date is missing or invalid.") from None
    filter_value = ("search.in(entity_type, 'COMPANY,ALL') and "
                    f"search.in(jurisdiction, '{jurisdiction},ALL') and "
                    f"effective_date le {review_date}T00:00:00Z and status eq 'CURRENT'")
    # Preserve the lab's default query for case checks. Policy Q&A uses the
    # analyst's question as plain search terms, not Azure query operators.
    if question is not None:
        if not isinstance(question, str) or not question.strip() or len(question) > 800:
            raise PolicyUnavailable("Policy question is missing or invalid.")
        terms = re.findall(r"[A-Za-z0-9]+", question)[:40]
        if not terms:
            raise PolicyUnavailable("Policy question has no searchable terms.")
        search_text = " ".join(terms)
    else:
        search_text = "high-risk jurisdiction company due diligence"
    body = {"search": search_text, "top": 5 if question is not None else 3,
            "select": "section_id,version,title,effective_date,content",
            "filter": filter_value}
    url = f"{endpoint}/indexes/{quote(index, safe='')}/docs/search?api-version=2024-07-01"
    request = Request(url, data=json.dumps(body).encode(), method="POST",
                      headers={"Content-Type": "application/json", "api-key": key})
    try:
        with urlopen(request, timeout=15) as response:
            data = json.load(response)
        rows = data["value"]
        if not isinstance(rows, list):
            raise ValueError("invalid results")
        sections = []
        for row in rows:
            if not all(row.get(k) for k in ("section_id", "version", "title", "effective_date", "content")):
                raise ValueError("incomplete section")
            sections.append({k: str(row[k]) for k in
                             ("section_id", "version", "title", "effective_date", "content")})
        return sections
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # Report a diagnostic category and HTTP status, never response text,
        # request headers, URLs or credentials.
        code = getattr(exc, "code", None)
        diagnostic = f"HTTP {code}" if isinstance(code, int) else type(exc).__name__
        raise PolicyUnavailable(f"Policy search could not complete ({diagnostic}).") from None
