#!/usr/bin/env python3
"""Discover and validate public ATS job boards without third-party API keys."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = ROOT / "employer_sources.json"
RETENTION_DAYS = 90

PROVIDERS = {
    "greenhouse": {
        "query": '"boards.greenhouse.io/" in:file',
        "patterns": (
            re.compile(r"(?:boards|job-boards)\.greenhouse\.io/([A-Za-z0-9_-]+)", re.I),
            re.compile(r"boards-api\.greenhouse\.io/v1/boards/([A-Za-z0-9_-]+)", re.I),
        ),
    },
    "lever": {
        "query": '"jobs.lever.co/" in:file',
        "patterns": (
            re.compile(r"jobs\.lever\.co/([A-Za-z0-9_-]+)", re.I),
            re.compile(r"api\.lever\.co/v0/postings/([A-Za-z0-9_-]+)", re.I),
        ),
    },
    "ashby": {
        "query": '"jobs.ashbyhq.com/" in:file',
        "patterns": (
            re.compile(r"jobs\.ashbyhq\.com/([A-Za-z0-9_-]+)", re.I),
            re.compile(r"api\.ashbyhq\.com/posting-api/job-board/([A-Za-z0-9_-]+)", re.I),
        ),
    },
}

ROLE_PATTERN = re.compile(
    r"\b(?:software|backend|back-end|platform|infrastructure|systems?|site reliability|sre|"
    r"developer experience|developer productivity|distributed systems?|machine learning|ml)\b.*\b"
    r"(?:engineer|developer|architect)\b|\b(?:engineer|developer|architect)\b.*\b"
    r"(?:software|backend|back-end|platform|infrastructure|systems?|site reliability|sre|"
    r"developer experience|developer productivity|distributed systems?|machine learning|ml)\b",
    re.I,
)

INVALID_SLUGS = {
    "api",
    "embed",
    "job",
    "jobs",
    "job-board",
    "postings",
    "search",
    "v0",
    "v1",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def isoformat(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def request_json(url: str, token: str | None = None) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "job-search-source-cache/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def github_file_text(item_url: str, token: str) -> str:
    payload = request_json(item_url, token)
    if not isinstance(payload, dict) or payload.get("encoding") != "base64":
        return ""
    content = payload.get("content")
    if not isinstance(content, str):
        return ""
    return base64.b64decode(content).decode("utf-8", errors="ignore")


def discover_candidates(token: str, pages: int = 1) -> set[tuple[str, str]]:
    candidates: set[tuple[str, str]] = set()
    for provider, config in PROVIDERS.items():
        for page in range(1, pages + 1):
            query = urllib.parse.urlencode(
                {"q": config["query"], "per_page": 50, "page": page}
            )
            payload = request_json(f"https://api.github.com/search/code?{query}", token)
            if not isinstance(payload, dict):
                continue
            items = payload.get("items", [])
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict) or not isinstance(item.get("url"), str):
                    continue
                try:
                    text = github_file_text(item["url"], token)
                except (OSError, ValueError, urllib.error.HTTPError) as exc:
                    print(f"warning: could not read GitHub search result: {exc}", file=sys.stderr)
                    continue
                for pattern in config["patterns"]:
                    for match in pattern.finditer(text):
                        slug = match.group(1).strip().lower()
                        if slug and slug not in INVALID_SLUGS:
                            candidates.add((provider, slug))
    return candidates


def feed_url(provider: str, slug: str) -> str:
    if provider == "greenhouse":
        return f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=false"
    if provider == "lever":
        return f"https://api.lever.co/v0/postings/{slug}?mode=json"
    if provider == "ashby":
        return f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    raise ValueError(f"unsupported provider: {provider}")


def job_titles(provider: str, payload: object) -> list[str]:
    if provider == "lever":
        jobs = payload if isinstance(payload, list) else []
        key = "text"
    else:
        jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
        key = "title"
    return [job[key] for job in jobs if isinstance(job, dict) and isinstance(job.get(key), str)]


def source_key(source: dict[str, object]) -> tuple[str, str]:
    provider = str(source["type"])
    identifier = source.get("site") if provider == "lever" else source.get("board")
    return provider, str(identifier).lower()


def company_name(slug: str) -> str:
    return re.sub(r"[-_]+", " ", slug).strip().title()


def load_cache(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"schema_version": 1, "updated_at": None, "retention_days": RETENTION_DAYS, "sources": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("sources"), list):
        raise ValueError(f"invalid cache structure: {path}")
    return payload


def refresh(cache: dict[str, object], candidates: set[tuple[str, str]], now: datetime) -> dict[str, object]:
    existing = {
        source_key(source): dict(source)
        for source in cache.get("sources", [])
        if isinstance(source, dict)
    }
    keys = set(existing) | candidates
    refreshed: list[dict[str, object]] = []

    for provider, slug in sorted(keys):
        prior = existing.get((provider, slug))
        try:
            titles = job_titles(provider, request_json(feed_url(provider, slug)))
        except (OSError, ValueError, urllib.error.HTTPError) as exc:
            if prior:
                prior["consecutive_failures"] = int(prior.get("consecutive_failures", 0)) + 1
                if datetime.fromisoformat(str(prior["active_until"]).replace("Z", "+00:00")) > now:
                    refreshed.append(prior)
            print(f"warning: {provider}/{slug}: {exc}", file=sys.stderr)
            continue

        relevant = any(ROLE_PATTERN.search(title) for title in titles)
        if not prior and not relevant:
            continue

        source = prior or {
            "company": company_name(slug),
            "type": provider,
            "first_discovered_at": isoformat(now),
            "last_relevant_listing_at": isoformat(now),
            "active_until": isoformat(now + timedelta(days=RETENTION_DAYS)),
        }
        source["last_checked_at"] = isoformat(now)
        source["consecutive_failures"] = 0
        source["site" if provider == "lever" else "board"] = slug
        if relevant:
            source["last_relevant_listing_at"] = isoformat(now)
            source["active_until"] = isoformat(now + timedelta(days=RETENTION_DAYS))
        if datetime.fromisoformat(str(source["active_until"]).replace("Z", "+00:00")) > now:
            refreshed.append(source)

    return {
        "schema_version": 1,
        "updated_at": isoformat(now),
        "retention_days": RETENTION_DAYS,
        "sources": refreshed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--discovery-pages", type=int, default=1)
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        parser.error("GITHUB_TOKEN is required for GitHub code search")
    cache = load_cache(args.cache)
    candidates = discover_candidates(token, max(1, min(args.discovery_pages, 3)))
    print(f"discovered {len(candidates)} candidate ATS boards")
    updated = refresh(cache, candidates, utc_now())
    args.cache.write_text(json.dumps(updated, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"retained {len(updated['sources'])} active sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
